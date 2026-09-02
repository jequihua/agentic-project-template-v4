"""Bounded PyYAML adapter for OKF frontmatter and framework-profile checks.

This is the single owned OKF/profile parsing boundary. It uses the pure-Python
``yaml.SafeLoader`` for YAML *syntax and representation* and keeps all producer
policy (Markdown framing, resource limits, duplicate-key rejection, canonical
scalar/style rules, OKF/profile results) in project code. It never constructs
arbitrary Python objects (only standard scalar keys, for semantic identity), never
mutates global loader state or the recursion limit, never decides execution
eligibility, and never mutates its input.

Layer results (never inferred from one another):
- ``okf_concept``: pass / fail / unverified / not_evaluated + an ``OKF_*`` reason
  or ``None``.
- ``framework_profile``: pass / fail / not_applicable + a ``PROFILE_*`` reason or
  ``None``.
- ``execution_eligibility``: always ``not_evaluated``.
"""

from __future__ import annotations

import re

import yaml  # mandatory dependency; a missing install surfaces as ImportError

PROFILE_SCHEMA_VERSION = "template.okf_profile_check.v2"
PINNED_FRAMEWORK_PROFILE = "0.1-rc.1"

# Shared type registry (profile section 5.2), including tool-owned reserved types.
PROFILE_TYPE_REGISTRY = frozenset({
    "brief", "constraint", "decision", "analysis", "coding_prompt", "review_prompt",
    "self_report", "review_report", "verdict_record", "delivery_plan", "framework_doc",
    "source", "claim", "entity", "page", "milestone", "slice",
})

# Total-input ceiling for profile mode: enforced on raw bytes before UTF-8 decode,
# Markdown line materialization, or PyYAML. ~25x the largest observed artifact.
MAX_ARTIFACT_BYTES = 1_048_576
# Frontmatter-block limits (a much smaller inner boundary), enforced before PyYAML.
MAX_FRONTMATTER_BYTES = 65_536
MAX_FRONTMATTER_LINES = 500
MAX_LINE_LEN = 8_192
# Parse/graph limits.
MAX_TOKENS = 10_000
MAX_NODES = 2_000
MAX_DEPTH = 32
MAX_SCALAR_LEN = 16_384
MAX_MAPPING_ITEMS = 500
MAX_SEQUENCE_ITEMS = 1_000
MAX_ALIASES = 50

INT_CANONICAL_RE = re.compile(r"^(?:0|-?[1-9][0-9]*)$")
# A plain lexeme that looks numeric (exponent, underscore, sexagesimal, or decimal
# groupings) but that PyYAML left as a string is a cross-parser hazard.
NUMERIC_LIKE_RE = re.compile(r"^[+-]?[0-9][0-9_]*([.:][0-9_]+)*([eE][+-]?[0-9]+)?$")

_STR_TAG = "tag:yaml.org,2002:str"
_INT_TAG = "tag:yaml.org,2002:int"
_BOOL_TAG = "tag:yaml.org,2002:bool"
_NULL_TAG = "tag:yaml.org,2002:null"
_MERGE_TAG = "tag:yaml.org,2002:merge"


def _record(okf_result, okf_reason, profile_result, profile_reason):
    return {
        "okf_concept": {"result": okf_result, "reason": okf_reason},
        "framework_profile": {"result": profile_result, "reason": profile_reason},
        "execution_eligibility": "not_evaluated",
    }


def limit_exceeded_record() -> dict:
    """A bounded resource refusal: OKF ``unverified`` (not invalid)."""
    return _record("unverified", "OKF_PARSE_LIMIT_EXCEEDED", "fail", "PROFILE_YAML_OUT_OF_SUBSET")


def not_evaluated_record() -> dict:
    """A pre-L1 input failure (e.g. malformed UTF-8): nothing was evaluated."""
    return _record("not_evaluated", None, "not_applicable", None)


class _ResourceRefusal(Exception):
    """A finite parse limit was exceeded (not proof of invalid YAML)."""


def read_bounded(path) -> tuple[str | None, str | None]:
    """Read at most ``MAX_ARTIFACT_BYTES + 1`` bytes and decode UTF-8 once.

    Returns ``(text, None)`` on success, ``(None, "oversize")`` when the raw input
    exceeds the total-input ceiling (refused before decode), or ``(None, "decode")``
    for invalid UTF-8. One open/read/decode snapshot; no unbounded read.
    """
    with open(path, "rb") as handle:
        data = handle.read(MAX_ARTIFACT_BYTES + 1)
    if len(data) > MAX_ARTIFACT_BYTES:
        return None, "oversize"
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, "decode"


def _frame_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_text, status) using the exact `---` framing contract.

    status is "ok", "legacy" (no opening delimiter), or "unterminated". LF and CRLF
    are both accepted (``splitlines`` removes either).
    """
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return "", "legacy"
    for idx in range(1, len(lines)):
        if lines[idx] == "---":
            return "\n".join(lines[1:idx]), "ok"
    return "", "unterminated"


def _scan_features(frontmatter: str) -> set[str]:
    """Collect producer-profile feature flags and enforce token/alias bounds.

    Raises yaml.YAMLError on a syntax error, RecursionError on pathological depth,
    and _ResourceRefusal on a bound.
    """
    features: set[str] = set()
    tokens = 0
    aliases = 0
    for token in yaml.scan(frontmatter, Loader=yaml.SafeLoader):
        tokens += 1
        if tokens > MAX_TOKENS:
            raise _ResourceRefusal("token count")
        if isinstance(token, (yaml.AnchorToken, yaml.AliasToken)):
            features.add("anchor_alias")
            if isinstance(token, yaml.AliasToken):
                aliases += 1
                if aliases > MAX_ALIASES:
                    raise _ResourceRefusal("alias count")
        elif isinstance(token, yaml.TagToken):
            features.add("explicit_tag")
        elif isinstance(token, (yaml.FlowMappingStartToken, yaml.FlowSequenceStartToken)):
            features.add("flow")
        elif isinstance(token, yaml.ScalarToken):
            if token.style == "'":
                features.add("single_quote")
            elif token.style in ("|", ">"):
                features.add("block_scalar")
    return features


def _canonical_scalar_ok(node) -> bool:
    """Whether a scalar VALUE node obeys the canonical producer subset (section 6.3),
    using PyYAML's resolved tag plus the original lexeme."""
    style = node.style
    if style == '"':
        return True                       # a double-quoted string is canonical
    if style in ("'", "|", ">"):
        return False                      # single-quote / block scalar out of subset
    lexeme = node.value
    if node.tag == _STR_TAG:
        # A plain string that resolves as str but looks numeric is out of subset.
        return not NUMERIC_LIKE_RE.match(lexeme)
    if node.tag == _INT_TAG:
        return bool(INT_CANONICAL_RE.match(lexeme))
    if node.tag == _BOOL_TAG:
        return lexeme in ("true", "false")
    if node.tag == _NULL_TAG:
        return lexeme in ("null", "~", "")
    return False                          # float, timestamp, or any other typed tag


def _key_identity(loader, key_node) -> tuple[object | None, bool]:
    """Semantic identity of a mapping key and whether it is a YAML string scalar.

    The identity is ``(resolved_tag, constructed_scalar_value)`` from PyYAML's own
    scalar resolution, so ``1``/``01``, ``60``/``1:0``, ``yes``/``on``/``true``,
    and ``null``/``~`` collapse to one key while an integer ``1`` and string ``"1"``
    stay distinct. Returns ``(None, False)`` for a complex/unconstructable key,
    where equality cannot be established safely.
    """
    if not isinstance(key_node, yaml.ScalarNode):
        return None, False
    tag = key_node.tag
    try:
        value = loader.construct_object(key_node, deep=True)
    except (yaml.YAMLError, RecursionError, ValueError, TypeError):
        return None, False
    try:
        identity = (tag, value)
        hash(identity)
    except TypeError:
        identity = (tag, repr(value))
    return identity, tag == _STR_TAG


def _walk(node, depth, loader, state) -> None:
    """Bounded, cycle-safe traversal. Unique nodes are counted by identity (a
    shared alias target is counted and inspected once); the active stack detects
    cycles. Collects duplicate-key, non-string-key, complex-key, feature, and
    scalar-canonical evidence."""
    if depth > MAX_DEPTH:
        raise _ResourceRefusal("nesting depth")
    node_id = id(node)
    if node_id in state["active"]:
        raise _ResourceRefusal("alias cycle")
    if node_id in state["visited"]:
        return                            # shared node already inspected
    state["visited"].add(node_id)
    if len(state["visited"]) > MAX_NODES:
        raise _ResourceRefusal("node count")

    if isinstance(node, yaml.ScalarNode):
        if len(node.value) > MAX_SCALAR_LEN:
            raise _ResourceRefusal("scalar length")
        return

    state["active"].add(node_id)
    if isinstance(node, yaml.MappingNode):
        if node.flow_style:
            state["features"].add("flow")
        if len(node.value) > MAX_MAPPING_ITEMS:
            raise _ResourceRefusal("mapping size")
        seen: set[object] = set()
        for key_node, value_node in node.value:
            if isinstance(key_node, yaml.ScalarNode) and key_node.tag == _MERGE_TAG:
                # A merge key is a producer-profile feature AND participates in
                # duplicate detection: its identity is a fixed sentinel derived from
                # the merge tag (distinct from a quoted string key "<<"), so two
                # `<<` keys at the same source mapping are a duplicate.
                state["features"].add("merge")
                identity = (_MERGE_TAG, None)
                if identity in seen:
                    state["duplicate"] = True
                seen.add(identity)
            else:
                identity, is_string = _key_identity(loader, key_node)
                if identity is None:
                    state["complex_key"] = True
                else:
                    if identity in seen:
                        state["duplicate"] = True
                    seen.add(identity)
                    if not is_string:
                        state["nonstring_key"] = True
            _walk(key_node, depth + 1, loader, state)
            _walk(value_node, depth + 1, loader, state)
            if isinstance(value_node, yaml.ScalarNode) and not _canonical_scalar_ok(value_node):
                state["noncanonical"] = True
    elif isinstance(node, yaml.SequenceNode):
        if node.flow_style:
            state["features"].add("flow")
        if len(node.value) > MAX_SEQUENCE_ITEMS:
            raise _ResourceRefusal("sequence size")
        for item in node.value:
            _walk(item, depth + 1, loader, state)
            if isinstance(item, yaml.ScalarNode) and not _canonical_scalar_ok(item):
                state["noncanonical"] = True
    state["active"].discard(node_id)


def _top_level_scalar(root, key: str) -> tuple[bool, str | None]:
    """Return (present, lexeme) for a top-level scalar-keyed field of a mapping."""
    if not isinstance(root, yaml.MappingNode):
        return False, None
    for key_node, value_node in root.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.tag == _STR_TAG and key_node.value == key:
            if isinstance(value_node, yaml.ScalarNode):
                return True, value_node.value
            return True, None
    return False, None


def evaluate_profile(text: str) -> dict:
    """Evaluate one artifact's OKF-concept and framework-profile results from an
    already-decoded string (the caller owns the total-input byte bound)."""
    # 1. Markdown framing (owned outside YAML).
    frontmatter, status = _frame_frontmatter(text)
    if status == "legacy":
        return _record("not_evaluated", None, "not_applicable", None)
    if status == "unterminated":
        return _record("fail", "OKF_FRONTMATTER_MISSING", "not_applicable", None)

    # 2. Frontmatter-block resource limits (before PyYAML).
    if (
        len(frontmatter.encode("utf-8", "surrogatepass")) > MAX_FRONTMATTER_BYTES
        or frontmatter.count("\n") + 1 > MAX_FRONTMATTER_LINES
        or any(len(line) > MAX_LINE_LEN for line in frontmatter.splitlines())
    ):
        return limit_exceeded_record()

    # 3. Syntax scan + producer-feature detection + token/alias bounds.
    try:
        features = _scan_features(frontmatter)
    except (_ResourceRefusal, RecursionError):
        return limit_exceeded_record()
    except yaml.YAMLError:
        return _record("fail", "OKF_YAML_INVALID", "fail", "PROFILE_YAML_OUT_OF_SUBSET")

    # 4. Compose exactly one document's node graph (also enables scalar construction).
    loader = yaml.SafeLoader(frontmatter)
    try:
        try:
            root = loader.get_single_node()  # raises on multiple documents
        except yaml.YAMLError:
            return _record("fail", "OKF_YAML_INVALID", "fail", "PROFILE_YAML_OUT_OF_SUBSET")
        except RecursionError:
            return limit_exceeded_record()

        state = {
            "active": set(), "visited": set(), "features": set(features),
            "duplicate": False, "complex_key": False, "nonstring_key": False,
            "noncanonical": False,
        }
        if root is not None:
            try:
                _walk(root, 0, loader, state)
            except (_ResourceRefusal, RecursionError):
                return limit_exceeded_record()

        # 5. Duplicate keys (semantic) are a conclusive YAML/OKF failure.
        if state["duplicate"]:
            return _record("fail", "OKF_YAML_INVALID", "fail", "PROFILE_YAML_OUT_OF_SUBSET")

        # 6. OKF concept: a non-empty top-level string-keyed `type`.
        present, type_value = _top_level_scalar(root, "type")
        if not present or not type_value:
            return _record("fail", "OKF_TYPE_MISSING", "not_applicable", None)

        # 7. Framework producer-profile evaluation (independent of OKF pass).
        out_of_subset = (
            bool(state["features"]) or state["noncanonical"]
            or state["complex_key"] or state["nonstring_key"]
        )
        if out_of_subset:
            return _record("pass", None, "fail", "PROFILE_YAML_OUT_OF_SUBSET")
        if type_value not in PROFILE_TYPE_REGISTRY:
            return _record("pass", None, "fail", "PROFILE_TYPE_UNSUPPORTED")
        present_fp, fp_value = _top_level_scalar(root, "framework_profile")
        if not present_fp or fp_value is None:
            return _record("pass", None, "not_applicable", None)  # not opted into the profile
        if fp_value != PINNED_FRAMEWORK_PROFILE:
            return _record("pass", None, "fail", "PROFILE_VERSION_UNSUPPORTED")
        return _record("pass", None, "pass", None)
    finally:
        loader.dispose()

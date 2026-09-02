"""Compose the opted-in fixture project for the old-consumer fence proof (stdlib).

    python tests/fixtures/slice_contract/optin_project_for_old_consumer/compose.py \
        --template <template checkout> --out <empty or absent directory>

Copies the template checkout (minus .git and governed local surfaces), installs
this directory's prose roadmaps and sidecars under 03_experiments/, and switches
the layout's configured coding template to the contract-v1 scaffold - the exact
two effects of opt-in. It never runs the legacy consumer; run it yourself:

    <python with frutlups 0.1.8> -m frutlups make-coding-prompt <out> --dry-run --json

Expected against released frutlups 0.1.8 (tag object
f370e0743acf6f73ad08eaa13b755c87d41c5628, peeled commit
2d4f1c1ff76b057c79a106d6b586d4949110ed31): exit code 1, would_write false, the
nine diagnostics in expected_refusal.txt, and no file under
prompts/for_coding_agent/. The refusal keys on the v1 scaffold's slots not
matching the legacy slot forms, not on an unconsumed-TBD diagnostic.
"""
import argparse, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "local_state", ".frutlups_drive", "__pycache__", ".venv", "node_modules"}


def compose(template: Path, out: Path) -> None:
    template, out = template.resolve(), out.resolve()
    if out.exists() and any(out.iterdir()):
        sys.exit(f"output directory is not empty: {out}")
    shutil.copytree(
        template, out, dirs_exist_ok=True,
        ignore=lambda d, names: [n for n in names if n in SKIP_DIRS or n.endswith((".pyc", ".pyo"))],
    )
    roadmaps = out / "03_experiments"
    for name in ("active_roadmap.md", "development_roadmap.md", "active_roadmap.slices.yaml", "development_roadmap.slices.yaml"):
        shutil.copyfile(HERE / name, roadmaps / name)
    layout = out / "frutlups.layout.yaml"
    text = layout.read_text(encoding="utf-8")
    legacy = 'coding_template: "prompts/templates/coding_prompt.md"'
    if text.count(legacy) != 1:
        sys.exit("layout does not carry exactly one legacy coding_template line")
    layout.write_text(text.replace(legacy, 'coding_template: "prompts/templates/coding_prompt_contract_v1.md"'), encoding="utf-8", newline="\n")
    print(f"composed opted-in fixture project at {out}")
    print("run: <python with frutlups 0.1.8> -m frutlups make-coding-prompt", out, "--dry-run --json")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    compose(args.template, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

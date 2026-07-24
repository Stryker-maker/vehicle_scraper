from __future__ import annotations

from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "apply_audit11a_docs.py"
text = SCRIPT.read_text(encoding="utf-8")

readme_fragment = (
    "Do not use `data/<vehicle>/merged/*.csv` as current recommendations.\n''',"
)
readme_replacement = (
    "Do not use `data/<vehicle>/merged/*.csv` as current recommendations. "
    "Historical merged CSVs are disabled legacy output and are deleted for active "
    "vehicles by governed retention with SHA-256 deletion evidence.\n''',"
)
if text.count(readme_fragment) != 2:
    raise RuntimeError(
        f"Unexpected README fragment count: {text.count(readme_fragment)}"
    )
text = text.replace(readme_fragment, readme_replacement)

helper_anchor = (
    '    path.write_text(text.replace(old, new), encoding="utf-8")\n\n\n'
    'readme = ROOT / "README.md"'
)
helper_replacement = '''    path.write_text(text.replace(old, new), encoding="utf-8")


def replace_first(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(
            f"Expected at least one match in {path}; anchor={old.splitlines()[0]!r}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


readme = ROOT / "README.md"'''
if text.count(helper_anchor) != 1:
    raise RuntimeError(f"Unexpected helper anchor count: {text.count(helper_anchor)}")
text = text.replace(helper_anchor, helper_replacement)

authority_call = '''replace_once(
    test,
    '            "AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md",\\n',
    '            "AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md",\\n            "AUDIT_11A_F150_MANUAL_REINTRODUCTION.md",\\n',
)'''
fixed_authority_call = '''replace_first(
    test,
    '            "AUDIT_09_F350_BUYER_INTELLIGENCE.md",\\n            "AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md",\\n',
    '            "AUDIT_09_F350_BUYER_INTELLIGENCE.md",\\n            "AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md",\\n            "AUDIT_11A_F150_MANUAL_REINTRODUCTION.md",\\n',
)'''
if text.count(authority_call) != 1:
    raise RuntimeError(
        f"Unexpected authority-list call count: {text.count(authority_call)}"
    )
text = text.replace(authority_call, fixed_authority_call)

namespace = {"__file__": str(SCRIPT), "__name__": "__main__"}
exec(compile(text, str(SCRIPT), "exec"), namespace)

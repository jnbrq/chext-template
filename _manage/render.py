import re
from pathlib import Path


VAR_RE = re.compile(r"@@@\s*([A-Za-z_][A-Za-z0-9_]*)\s*@@@")


def render_template(template_dir: Path, template_name: str, **context: object) -> str:
    text = (template_dir / template_name).read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in context:
            raise KeyError(f"missing template variable {name!r} in {template_name}")
        return str(context[name])

    return VAR_RE.sub(replace, text)

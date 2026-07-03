import re
from dataclasses import dataclass
from pathlib import Path

from .cmake import TestbenchEntry


PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_][A-Za-z0-9_.]*)", re.MULTILINE)
EMIT_RE = re.compile(r"emit\s*\(\s*new\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
INCLUDE_TEST_MARKER = "// manage: include test"
OBJECT_RE = re.compile(
    r"(?:private\s+)?object\s+([A-Za-z_][A-Za-z0-9_]*)\s+extends\s+chext\.TestBench"
)
DESIRED_NAME_RE = re.compile(
    r"override\s+def\s+desiredName\s*:\s*String\s*=\s*\"([A-Za-z_][A-Za-z0-9_]*)\"",
    re.MULTILINE,
)


@dataclass(frozen=True)
class EmitSite:
    scala_path: Path
    package: str
    object_name: str
    emitted_classes: list[str]
    desired_names: list[str | None]

    @property
    def logical_name(self) -> str:
        return self.object_name.removesuffix("_Tb")

    @property
    def hdl_modules(self) -> list[str]:
        return [
            desired_name or emitted_class
            for emitted_class, desired_name in zip(self.emitted_classes, self.desired_names)
        ]


def _find_desired_name(text: str, emitted_class: str) -> str | None:
    class_pos = text.find(f"class {emitted_class}")
    if class_pos == -1:
        return None
    next_class = text.find("\nclass ", class_pos + 1)
    next_private_class = text.find("\nprivate class ", class_pos + 1)
    candidates = [pos for pos in (next_class, next_private_class) if pos != -1]
    end = min(candidates) if candidates else len(text)
    body = text[class_pos:end]
    match = DESIRED_NAME_RE.search(body)
    return match.group(1) if match else None


def _line_offsets(text: str) -> list[int]:
    offsets = [0]
    for match in re.finditer(r"\n", text):
        offsets.append(match.end())
    return offsets


def _find_object_body(text: str, object_start: int) -> str | None:
    brace_start = text.find("{", object_start)
    if brace_start == -1:
        return None

    depth = 0
    for index in range(brace_start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace_start:index + 1]
    return None


def scan_emits(chisel_root: Path) -> list[EmitSite]:
    sites: list[EmitSite] = []
    for scala_path in sorted(chisel_root.rglob("*.scala")):
        text = scala_path.read_text(encoding="utf-8")
        package_match = PACKAGE_RE.search(text)
        if not package_match:
            continue
        package = package_match.group(1)
        lines = text.splitlines()
        offsets = _line_offsets(text)
        for index, line in enumerate(lines[:-1]):
            if line.strip() != INCLUDE_TEST_MARKER:
                continue
            object_line_start = offsets[index + 1]
            object_match = OBJECT_RE.search(lines[index + 1])
            if not object_match:
                continue
            body = _find_object_body(text, object_line_start)
            if body is None:
                continue
            emitted_classes = [match.group(1) for match in EMIT_RE.finditer(body)]
            sites.append(
                EmitSite(
                    scala_path=scala_path,
                    package=package,
                    object_name=object_match.group(1),
                    emitted_classes=emitted_classes,
                    desired_names=[
                        _find_desired_name(text, emitted_class)
                        for emitted_class in emitted_classes
                    ],
                )
            )
    return sites


def cmake_entries(project_root: Path, sites: list[EmitSite]) -> list[TestbenchEntry]:
    entries: list[TestbenchEntry] = []
    for site in sites:
        package_path = site.package.replace(".", "/")
        logical = site.logical_name
        cpp = project_root / "sysc_tb" / package_path / "src" / f"{logical}.tb.cpp"
        if not cpp.exists() or not site.hdl_modules:
            continue
        entries.append(
            TestbenchEntry(
                target_name=f"{site.package}.{logical}.tb",
                cpp_source=f"src/{logical}.tb.cpp",
                hdl_dir="hdl",
                hdl_modules=site.hdl_modules,
                trace=True,
            )
        )
    return entries

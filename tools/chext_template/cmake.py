from dataclasses import dataclass
from pathlib import Path


BEGIN = "# BEGIN MANAGED TESTBENCHES"
END = "# END MANAGED TESTBENCHES"


@dataclass(frozen=True)
class TestbenchEntry:
    target_name: str
    cpp_source: str
    hdl_module: str
    trace: bool = True


def render_entries(entries: list[TestbenchEntry]) -> str:
    chunks: list[str] = []
    for entry in sorted(entries, key=lambda item: item.target_name):
        lines = [
            "generate_tb(",
            f"    TARGET_NAME {entry.target_name}",
            f"    CPP_SOURCES {entry.cpp_source}",
            f"    HDL_MODULES {entry.hdl_module}",
        ]
        if entry.trace:
            lines.extend(
                [
                    "    VERILATOR_ARGS",
                    '        "--trace"',
                    "    CPP_DEFS",
                    "        VERILATED_TRACE_ENABLED",
                ]
            )
        lines.append(")")
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks)


def update_managed_region(cmake_path: Path, entries: list[TestbenchEntry]) -> None:
    text = cmake_path.read_text(encoding="utf-8")
    begin = text.find(BEGIN)
    end = text.find(END)
    if begin == -1 or end == -1 or end < begin:
        raise ValueError(f"managed testbench markers are missing or malformed in {cmake_path}")

    before = text[: begin + len(BEGIN)]
    after = text[end:]
    body = render_entries(entries)
    cmake_path.write_text(f"{before}\n{body}\n{after}", encoding="utf-8")

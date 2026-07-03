from dataclasses import dataclass
from pathlib import Path


BEGIN = "# BEGIN MANAGED TESTBENCHES"
END = "# END MANAGED TESTBENCHES"
PKG_BEGIN = "# BEGIN MANAGED PACKAGES"
PKG_END = "# END MANAGED PACKAGES"


@dataclass(frozen=True)
class TestbenchEntry:
    target_name: str
    cpp_source: str
    hdl_dir: str
    hdl_modules: list[str]
    trace: bool = True


def render_entries(entries: list[TestbenchEntry]) -> str:
    chunks: list[str] = []
    for entry in sorted(entries, key=lambda item: item.target_name):
        lines = [
            "generate_tb(",
            f"    TARGET_NAME {entry.target_name}",
            f"    CPP_SOURCES {entry.cpp_source}",
            f"    HDL_DIR {entry.hdl_dir}",
            f"    HDL_MODULES {' '.join(entry.hdl_modules)}",
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


def package_cmake_text() -> str:
    return f"{BEGIN}\n\n{END}\n"


def ensure_package_cmake(cmake_path: Path) -> None:
    if not cmake_path.exists():
        cmake_path.parent.mkdir(parents=True, exist_ok=True)
        cmake_path.write_text(package_cmake_text(), encoding="utf-8")


def update_managed_packages(cmake_path: Path, package_paths: list[str]) -> None:
    text = cmake_path.read_text(encoding="utf-8")
    begin = text.find(PKG_BEGIN)
    end = text.find(PKG_END)
    if begin == -1 or end == -1 or end < begin:
        raise ValueError(f"managed package markers are missing or malformed in {cmake_path}")

    body = "\n".join(
        f"add_subdirectory({package_path})"
        for package_path in sorted(package_paths)
    )
    before = text[: begin + len(PKG_BEGIN)]
    after = text[end:]
    cmake_path.write_text(f"{before}\n{body}\n{after}", encoding="utf-8")

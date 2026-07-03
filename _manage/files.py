from pathlib import Path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replace_text(path: Path, old: str, new: str) -> None:
    text = read_text(path)
    if old not in text:
        raise ValueError(f"marker/text not found in {path}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")

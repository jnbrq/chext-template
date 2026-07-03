import re


MODULE_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
PROJECT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PACKAGE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


def require_project_name(name: str) -> str:
    if not PROJECT_RE.match(name):
        raise ValueError(f"invalid project name: {name!r}")
    return name


def require_module_name(name: str) -> str:
    if not MODULE_RE.match(name):
        raise ValueError(
            f"invalid module name: {name!r}; use a Scala class-style name such as FooBar"
        )
    return name


def require_package_name(name: str) -> str:
    if not PACKAGE_RE.match(name):
        raise ValueError(f"invalid package name: {name!r}")
    return name


def package_from_project(name: str) -> str:
    package = re.sub(r"[^A-Za-z0-9_]", "_", name).lower()
    if not IDENT_RE.match(package):
        package = f"p_{package}"
    return package


def package_path(package: str) -> str:
    return package.replace(".", "/")

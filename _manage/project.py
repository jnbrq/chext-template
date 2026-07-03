import json
import re
import subprocess
from pathlib import Path

from . import cmake, names, scanner
from .files import read_text, replace_text, write_text
from .render import render_template


class Project:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.manifest_path = self.root / "project.json"
        self.template_dir = self.root / "_manage" / "templates"
        self.data = json.loads(read_text(self.manifest_path))

    @classmethod
    def find(cls, start: Path) -> "Project":
        cur = start.resolve()
        for path in [cur, *cur.parents]:
            if (path / "project.json").exists() and (path / "manage.py").exists():
                return cls(path)
        raise FileNotFoundError("could not find project.json/manage.py")

    @property
    def default_package(self) -> str:
        return self.data.get("default_package", self.data.get("scala_package"))

    @property
    def packages(self) -> list[str]:
        packages = self.data.setdefault("packages", [])
        if self.default_package not in packages:
            packages.insert(0, self.default_package)
        return packages

    def _package_path(self, package: str) -> str:
        return names.package_path(package)

    def _resolve_package(self, package: str | None) -> str:
        resolved = package or self.default_package
        names.require_package_name(resolved)
        if resolved not in self.packages:
            self.add_package(resolved)
        return resolved

    def save(self) -> None:
        self.manifest_path.write_text(
            json.dumps(self.data, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )

    def status(self) -> str:
        modules = self.data.get("modules", [])
        tests = self.data.get("tests", [])
        lines = [
            f"project: {self.data['project_name']}",
            f"default package: {self.default_package}",
            f"packages: {', '.join(self.packages) if self.packages else '(none)'}",
            f"modules: {len(modules)}",
        ]
        for module in modules:
            lines.append(
                f"  - {module.get('package', self.default_package)}.{module['name']} "
                f"({module.get('style', 'unknown')})"
            )
        lines.append(f"tests: {len(tests)}")
        for test in tests:
            lines.append(f"  - {test.get('package', self.default_package)}.{test['name']}")
        return "\n".join(lines)

    def add_package(self, package: str) -> None:
        names.require_package_name(package)
        if package not in self.packages:
            self.data.setdefault("packages", []).append(package)
            self.save()

        package_path = self._package_path(package)
        for rel in [
            f"chisel_rtl/src/main/scala/{package_path}/.gitkeep",
            f"chisel_rtl/tests/{package_path}/.gitkeep",
            f"sysc_tb/{package_path}/src/.gitkeep",
            f"sysc_tb/{package_path}/include/.gitkeep",
            f"sysc_tb/{package_path}/hdl/.gitkeep",
            f"sysc_tb/_common/include/{package_path}/.gitkeep",
        ]:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        cmake.ensure_package_cmake(self.root / "sysc_tb" / package_path / "CMakeLists.txt")
        self._sync_package_subdirectories()

    def module_exists(self, module_name: str, package: str | None = None) -> bool:
        package = package or self.default_package
        return any(
            item["name"] == module_name and item.get("package", self.default_package) == package
            for item in self.data.get("modules", [])
        )

    def add_module(
        self,
        module_name: str,
        style: str,
        with_test: bool = False,
        force: bool = False,
        package: str | None = None,
    ) -> None:
        names.require_module_name(module_name)
        package = self._resolve_package(package)
        if style not in {"plain", "structured"}:
            raise ValueError("style must be plain or structured")
        if self.module_exists(module_name, package) and not force:
            raise ValueError(f"module {package}.{module_name} already exists")

        template = "module_plain.scala.j2" if style == "plain" else "module_structured.scala.j2"
        package_path = self._package_path(package)
        rtl_rel = f"chisel_rtl/src/main/scala/{package_path}/{module_name}.scala"
        rtl_path = self.root / rtl_rel
        write_text(
            rtl_path,
            render_template(
                self.template_dir,
                template,
                scala_package=package,
                module_name=module_name,
            ),
            force=force,
        )

        if not self.module_exists(module_name, package):
            self.data.setdefault("modules", []).append(
                {
                    "name": module_name,
                    "package": package,
                    "style": style,
                    "rtl": rtl_rel,
                    "tests": [],
                }
            )
            self.save()

        if with_test:
            self.add_test(module_name, force=force, package=package)

    def add_test(self, test_name: str, force: bool = False, package: str | None = None) -> None:
        names.require_module_name(test_name)
        package = self._resolve_package(package)
        package_path = self._package_path(package)
        self._ensure_hdl_dir(package)

        scala_rel = f"chisel_rtl/tests/{package_path}/{test_name}.tb.scala"
        cpp_rel = f"sysc_tb/{package_path}/src/{test_name}.tb.cpp"

        write_text(
            self.root / scala_rel,
            render_template(
                self.template_dir,
                "testbench.scala.j2",
                scala_package=package,
                test_name=test_name,
            ),
            force=force,
        )
        write_text(
            self.root / cpp_rel,
            render_template(
                self.template_dir,
                "sysc_tb.cpp.j2",
                cpp_namespace=package,
                module_name=test_name,
            ),
            force=force,
        )

        tests = self.data.setdefault("tests", [])
        if not any(test["name"] == test_name and test.get("package", self.default_package) == package for test in tests):
            tests.append(
                {
                    "name": test_name,
                    "package": package,
                    "scala": scala_rel,
                    "cpp": cpp_rel,
                    "target": f"{package}.{test_name}.tb",
                    "trace": True,
                }
            )
            self.save()

        self.sync()

    def sync(self) -> dict[str, int]:
        discovered_modules = self._discover_modules()
        self.data["modules"] = discovered_modules

        packages = set(self.data.get("packages", []))
        packages.add(self.default_package)
        for module in discovered_modules:
            packages.add(module["package"])

        sites = self.scan_tests()
        tests = []
        for site in sites:
            packages.add(site.package)
            package_path = self._package_path(site.package)
            tests.append(
                {
                    "name": site.logical_name,
                    "package": site.package,
                    "scala": str(site.scala_path.relative_to(self.root)),
                    "cpp": f"sysc_tb/{package_path}/src/{site.logical_name}.tb.cpp",
                    "target": f"{site.package}.{site.logical_name}.tb",
                    "hdl_modules": site.hdl_modules,
                    "trace": True,
                }
            )

        self.data["tests"] = sorted(tests, key=lambda item: (item["package"], item["name"]))
        self.data["packages"] = sorted(packages)
        if self.default_package in self.data["packages"]:
            self.data["packages"].remove(self.default_package)
            self.data["packages"].insert(0, self.default_package)

        for package in self.packages:
            self.add_package(package)

        self.save()
        self._sync_outputs()
        return {
            "modules": len(discovered_modules),
            "tests": len(tests),
            "packages": len(self.packages),
        }

    def _discover_modules(self) -> list[dict[str, object]]:
        scala_root = self.root / "chisel_rtl" / "src" / "main" / "scala"
        discovered: list[dict[str, object]] = []
        if not scala_root.exists():
            return discovered

        package_re = re.compile(r"^\s*package\s+([A-Za-z_][A-Za-z0-9_.]*)", re.MULTILINE)
        module_re = re.compile(
            r"(?m)^\s*(?:private\s+)?class\s+([A-Z][A-Za-z0-9_]*)\b[^{\n]*(?:extends\s+|with\s+)Module\b"
        )

        existing = {
            (module.get("package", self.default_package), module["name"]): module
            for module in self.data.get("modules", [])
        }

        for scala_path in sorted(scala_root.rglob("*.scala")):
            text = scala_path.read_text(encoding="utf-8")
            package_match = package_re.search(text)
            if not package_match:
                continue
            package = package_match.group(1)
            for match in module_re.finditer(text):
                module_name = match.group(1)
                if module_name.endswith("_TbTop") or module_name.endswith("_Tbtop"):
                    continue
                previous = existing.get((package, module_name), {})
                style = previous.get("style")
                if style is None:
                    style = "structured" if f"case class {module_name}_Config" in text else "plain"
                discovered.append(
                    {
                        "name": module_name,
                        "package": package,
                        "style": style,
                        "rtl": str(scala_path.relative_to(self.root)),
                    }
                )

        return sorted(discovered, key=lambda item: (str(item["package"]), str(item["name"])))

    def _sync_outputs(self) -> list[scanner.EmitSite]:
        sites = self.scan_tests()
        for site in sites:
            self._ensure_hdl_dir(site.package)
            cmake.ensure_package_cmake(
                self.root / "sysc_tb" / self._package_path(site.package) / "CMakeLists.txt"
            )
            self._sync_cpp_hdl_includes(site)

        self._sync_package_subdirectories()

        entries_by_package: dict[str, list[cmake.TestbenchEntry]] = {}
        for entry_site in sites:
            entries_by_package.setdefault(entry_site.package, [])
        for entry in scanner.cmake_entries(self.root, sites):
            package = entry.target_name.rsplit(".", 2)[0]
            entries_by_package.setdefault(package, []).append(entry)

        for package in self.packages:
            package_path = self._package_path(package)
            package_cmake = self.root / "sysc_tb" / package_path / "CMakeLists.txt"
            cmake.ensure_package_cmake(package_cmake)
            cmake.update_managed_region(package_cmake, entries_by_package.get(package, []))
        return sites

    def _sync_cpp_hdl_includes(self, site: scanner.EmitSite) -> None:
        package_path = self._package_path(site.package)
        cpp_path = self.root / "sysc_tb" / package_path / "src" / f"{site.logical_name}.tb.cpp"
        if not cpp_path.exists():
            return

        begin = "// BEGIN MANAGED HDL INCLUDES"
        end = "// END MANAGED HDL INCLUDES"
        includes = "\n".join(f"#include <{module}.hpp>" for module in site.hdl_modules)
        block = f"{begin}\n{includes}\n{end}"

        text = cpp_path.read_text(encoding="utf-8")
        begin_pos = text.find(begin)
        end_pos = text.find(end)
        if begin_pos != -1 and end_pos != -1 and end_pos > begin_pos:
            end_pos += len(end)
            text = f"{text[:begin_pos]}{block}{text[end_pos:]}"
        else:
            text = f"{block}\n\n{text}"
        cpp_path.write_text(text, encoding="utf-8")

    def _ensure_hdl_dir(self, package: str) -> None:
        package_path = self._package_path(package)
        for rel in [
            f"sysc_tb/{package_path}/hdl/.gitkeep",
            f"sysc_tb/{package_path}/src/.gitkeep",
            f"sysc_tb/{package_path}/include/.gitkeep",
        ]:
            keep = self.root / rel
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.touch(exist_ok=True)

    def _sync_package_subdirectories(self) -> None:
        package_paths = [self._package_path(package) for package in self.packages]
        cmake.update_managed_packages(self.root / "sysc_tb" / "CMakeLists.txt", package_paths)

    def scan_tests(self) -> list[scanner.EmitSite]:
        return scanner.scan_emits(self.root / "chisel_rtl")

    def list_tests(self, pattern: str | None = None) -> list[scanner.EmitSite]:
        sites = self.scan_tests()
        if pattern is None:
            return sites
        regex = re.compile(pattern)
        return [
            site
            for site in sites
            if regex.search(site.logical_name)
            or regex.search(site.object_name)
            or regex.search(f"{site.package}.{site.logical_name}.tb")
        ]

    def run_tests(
        self,
        pattern: str | None = None,
        emit: bool = False,
        configure: bool = False,
        build: bool = True,
        run: bool = True,
        build_dir: str = "build",
        dry_run: bool = False,
    ) -> None:
        sites = self.list_tests(pattern)
        if not sites:
            raise ValueError("no tests matched")

        self._sync_outputs()
        build_path = self.root / "sysc_tb" / build_dir

        def invoke(cmd: list[str], cwd: Path) -> None:
            print(f"+ cd {cwd.relative_to(self.root)} && {' '.join(cmd)}")
            if not dry_run:
                subprocess.run(cmd, cwd=cwd, check=True)

        if emit:
            for site in sites:
                invoke(["sbt", f"runMain {site.package}.{site.object_name}"], self.root / "chisel_rtl")

        if configure:
            invoke(["cmake", "-S", ".", "-B", build_dir], self.root / "sysc_tb")

        if build:
            for site in sites:
                target = f"{site.package}.{site.logical_name}.tb"
                invoke(["cmake", "--build", build_dir, "--target", target], self.root / "sysc_tb")

        if run:
            for site in sites:
                target = f"{site.package}.{site.logical_name}.tb"
                exe = build_path / self._package_path(site.package) / target
                invoke([str(exe)], self.root / "sysc_tb")

    def check(self) -> list[str]:
        issues: list[str] = []
        required = [
            "chisel_rtl/build.sbt",
            "sysc_tb/CMakeLists.txt",
            "_manage/templates/module_structured.scala.j2",
        ]
        for rel in required:
            if not (self.root / rel).exists():
                issues.append(f"missing {rel}")

        return issues

    def rename(self, new_name: str) -> None:
        names.require_project_name(new_name)
        old_name = self.data["project_name"]

        replace_text(self.root / "chisel_rtl" / "build.sbt", f'name := "{old_name}"', f'name := "{new_name}"')
        old_cmake_project = names.package_from_project(old_name)
        new_cmake_project = names.package_from_project(new_name)
        replace_text(
            self.root / "sysc_tb" / "CMakeLists.txt",
            f"project({old_cmake_project})",
            f"project({new_cmake_project})",
        )

        self.data["project_name"] = new_name
        self.save()
        self.sync()

    def cleanup_template(self) -> None:
        removed = False
        modules = []
        removed_tests: list[dict[str, object]] = []
        for module in self.data.get("modules", []):
            package = module.get("package", self.default_package)
            if module["name"] == "TransformExample" and package == self.default_package:
                for rel in [module.get("rtl", "")]:
                    if rel:
                        (self.root / rel).unlink(missing_ok=True)
                for test in module.get("tests", []):
                    for rel in [test.get("scala", ""), test.get("cpp", "")]:
                        if rel:
                            (self.root / rel).unlink(missing_ok=True)
                removed = True
            else:
                modules.append(module)
        self.data["modules"] = modules
        kept_tests = []
        for test in self.data.get("tests", []):
            if (
                test["name"] == "TransformExample"
                and test.get("package", self.default_package) == self.default_package
            ):
                removed_tests.append(test)
            else:
                kept_tests.append(test)
        for test in removed_tests:
            for rel in [test.get("scala", ""), test.get("cpp", "")]:
                if rel:
                    (self.root / str(rel)).unlink(missing_ok=True)
        self.data["tests"] = kept_tests
        self.save()
        self.sync()
        if not removed:
            raise ValueError("no default-package TransformExample module was found")

    def _get_module(self, module_name: str, package: str | None = None) -> dict:
        package = package or self.default_package
        for module in self.data.get("modules", []):
            if module["name"] == module_name and module.get("package", self.default_package) == package:
                return module
        raise ValueError(f"module {package}.{module_name} is not known; run add-module first")

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
        self.template_dir = self.root / "tools" / "chext_template" / "templates"
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
            f"sysc_tb/src/{package_path}/.gitkeep",
            f"sysc_tb/common/include/{package_path}/.gitkeep",
        ]:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)

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

    def add_test(self, module_name: str, force: bool = False, package: str | None = None) -> None:
        names.require_module_name(module_name)
        package = self._resolve_package(package)
        module = self._get_module(module_name, package)
        kind = "elastic" if module.get("style") == "structured" else "plain"
        package_path = self._package_path(package)

        scala_rel = f"chisel_rtl/tests/{package_path}/{module_name}.tb.scala"
        cpp_rel = f"sysc_tb/src/{package_path}/{module_name}.tb.cpp"

        write_text(
            self.root / scala_rel,
            render_template(
                self.template_dir,
                f"tb_{kind}.scala.j2",
                scala_package=package,
                module_name=module_name,
            ),
            force=force,
        )
        write_text(
            self.root / cpp_rel,
            render_template(
                self.template_dir,
                "sysc_tb.cpp.j2",
                cpp_namespace=package,
                module_name=module_name,
            ),
            force=force,
        )

        tests = module.setdefault("tests", [])
        if not any(test["name"] == module_name for test in tests):
            tests.append(
                {
                    "name": module_name,
                    "kind": kind,
                    "scala": scala_rel,
                    "cpp": cpp_rel,
                    "target": f"{package}.{module_name}.tb",
                    "trace": True,
                }
            )
            self.save()

        self.sync_tests()

    def sync_tests(self) -> list[scanner.EmitSite]:
        sites = self.scan_tests()
        entries = scanner.cmake_entries(self.root, sites)
        cmake.update_managed_region(self.root / "sysc_tb" / "CMakeLists.txt", entries)
        return sites

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

        self.sync_tests()
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
                exe = build_path / target
                invoke([str(exe)], self.root / "sysc_tb")

    def check(self) -> list[str]:
        issues: list[str] = []
        required = [
            "chisel_rtl/build.sbt",
            "sysc_tb/CMakeLists.txt",
            "tools/chext_template/templates/module_structured.scala.j2",
        ]
        for rel in required:
            if not (self.root / rel).exists():
                issues.append(f"missing {rel}")

        sites = self.scan_tests()
        for site in sites:
            if site.desired_name is None:
                issues.append(
                    f"{site.scala_path.relative_to(self.root)} emits {site.emitted_class} "
                    "without a literal override def desiredName"
                )

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
        self.sync_tests()

    def cleanup_template(self) -> None:
        removed = False
        modules = []
        for module in self.data.get("modules", []):
            package = module.get("package", self.default_package)
            if module["name"] == "Example" and package == self.default_package:
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
        self.save()
        self.sync_tests()
        if not removed:
            raise ValueError("no default-package Example module was found")

    def _get_module(self, module_name: str, package: str | None = None) -> dict:
        package = package or self.default_package
        for module in self.data.get("modules", []):
            if module["name"] == module_name and module.get("package", self.default_package) == package:
                return module
        raise ValueError(f"module {package}.{module_name} is not known; run add-module first")

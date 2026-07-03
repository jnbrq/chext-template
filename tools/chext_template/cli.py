import argparse
from pathlib import Path

from .project import Project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a Chisel/Chext template project")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")
    sub.add_parser("list")
    sub.add_parser("check")
    sub.add_parser("sync-tests")
    sub.add_parser("list-packages")
    sub.add_parser("cleanup-template")

    add_package = sub.add_parser("add-package")
    add_package.add_argument("package")

    list_tests = sub.add_parser("list-tests")
    list_tests.add_argument("pattern", nargs="?")

    run_tests = sub.add_parser("run-tests")
    run_tests.add_argument("pattern", nargs="?")
    run_tests.add_argument("--emit", action="store_true", help="run selected Chisel TestBench objects")
    run_tests.add_argument("--configure", action="store_true", help="configure sysc_tb with CMake")
    run_tests.add_argument("--no-build", action="store_true", help="skip C++ build")
    run_tests.add_argument("--no-run", action="store_true", help="skip executing built test binaries")
    run_tests.add_argument("--build-dir", default="build")
    run_tests.add_argument("--dry-run", action="store_true")

    rename = sub.add_parser("rename")
    rename.add_argument("new_name")

    add_module = sub.add_parser("add-module")
    add_module.add_argument("module_name")
    style = add_module.add_mutually_exclusive_group()
    style.add_argument("--plain", action="store_true")
    style.add_argument("--structured", action="store_true")
    add_module.add_argument("--with-test", action="store_true")
    add_module.add_argument("--package")
    add_module.add_argument("--force", action="store_true")

    add_test = sub.add_parser("add-test")
    add_test.add_argument("module_name")
    add_test.add_argument("--package")
    add_test.add_argument("--force", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project = Project.find(Path.cwd())

    try:
        if args.command in {"status", "list"}:
            print(project.status())
        elif args.command == "check":
            issues = project.check()
            if issues:
                print("Issues:")
                for issue in issues:
                    print(f"  - {issue}")
                return 1
            print("OK")
        elif args.command == "sync-tests":
            sites = project.sync_tests()
            print(f"scanned {len(sites)} emit site(s)")
        elif args.command == "list-packages":
            for package in project.packages:
                suffix = " (default)" if package == project.default_package else ""
                print(f"{package}{suffix}")
        elif args.command == "add-package":
            project.add_package(args.package)
            print(f"added package {args.package}")
        elif args.command == "cleanup-template":
            project.cleanup_template()
            print("removed default Example module/test")
        elif args.command == "list-tests":
            sites = project.list_tests(args.pattern)
            for site in sites:
                target = f"{site.package}.{site.logical_name}.tb"
                hdl = site.desired_name or site.emitted_class
                print(f"{target}  object={site.package}.{site.object_name}  hdl={hdl}")
        elif args.command == "run-tests":
            project.run_tests(
                args.pattern,
                emit=args.emit,
                configure=args.configure,
                build=not args.no_build,
                run=not args.no_run,
                build_dir=args.build_dir,
                dry_run=args.dry_run,
            )
        elif args.command == "rename":
            project.rename(args.new_name)
            print(f"renamed project to {args.new_name}")
        elif args.command == "add-module":
            style = "plain" if args.plain else "structured"
            project.add_module(
                args.module_name,
                style,
                args.with_test,
                args.force,
                package=args.package,
            )
            package = args.package or project.default_package
            print(f"added {style} module {package}.{args.module_name}")
        elif args.command == "add-test":
            project.add_test(args.module_name, args.force, package=args.package)
            package = args.package or project.default_package
            print(f"added test for {package}.{args.module_name}")
        else:
            raise AssertionError(args.command)
    except Exception as exc:
        print(f"error: {exc}")
        return 1

    return 0

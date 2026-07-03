import argparse
from pathlib import Path

from .project import Project


FORMATTER = argparse.RawDescriptionHelpFormatter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage a Chisel/Chext project with SystemC testbenches.",
        formatter_class=FORMATTER,
        epilog="""examples:
  ./manage.py status
  ./manage.py add-package alpha.beta
  ./manage.py add-module PacketPipe --structured --package alpha.beta
  ./manage.py add-test Smoke --package alpha.beta
  ./manage.py sync
  ./manage.py list-tests 'Packet|Smoke'
  ./manage.py run-tests Packet --emit --configure --dry-run
  ./manage.py cleanup-template

notes:
  Package names use Scala dotted form and map to directory trees.
  Test inclusion is controlled by '// manage: include test' before a TestBench object.
""",
    )
    sub = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="command",
        title="commands",
    )

    sub.add_parser(
        "status",
        aliases=["list"],
        help="show project metadata, packages, and known modules",
        description="Show project metadata, configured packages, and known modules.",
    )
    sub.add_parser(
        "check",
        help="validate template structure and managed testbench declarations",
        description=(
            "Validate required files and managed testbench declarations. Non-literal "
            "desiredName overrides are allowed; sync falls back to emitted class names."
        ),
    )
    sub.add_parser(
        "sync",
        help="reconcile project.json and regenerate managed CMake",
        description=(
            "Discover Scala modules, packages, and managed tests; update project.json; "
            "ensure package directories exist; refresh C++ HDL include blocks; and "
            "regenerate root/package CMake files."
        ),
    )
    sub.add_parser(
        "list-packages",
        help="list known Scala/C++ package trees",
        description="List packages tracked in project.json. The default package is marked.",
    )
    sub.add_parser(
        "cleanup-template",
        help="remove the starter TransformExample module/test from the default package",
        description=(
            "Remove the starter TransformExample RTL, Scala testbench, and SystemC testbench "
            "from the default package, then resync CMake. .gitkeep files are left behind."
        ),
    )

    add_package = sub.add_parser(
        "add-package",
        help="create/register a package tree such as alpha.beta",
        description=(
            "Register a package and create matching directory trees under Chisel RTL, "
            "Chisel tests, SystemC sources, package-local emitted HDL, and _common include."
        ),
    )
    add_package.add_argument("package", help="Scala dotted package name, e.g. alpha.beta")

    list_tests = sub.add_parser(
        "list-tests",
        help="list managed tests, optionally filtered by regex",
        description=(
            "List tests discovered from managed Scala TestBench objects. The optional "
            "regex is matched against logical test name, object name, and CMake target."
        ),
    )
    list_tests.add_argument("pattern", nargs="?", help="optional Python regex filter")

    run_tests = sub.add_parser(
        "run-tests",
        help="emit/build/run tests selected by regex",
        description=(
            "Run selected tests. By default this builds and executes matching SystemC "
            "test binaries from sysc_tb/build. Use --emit to rerun Chisel TestBench "
            "objects first and --configure to rerun CMake configure."
        ),
    )
    run_tests.add_argument(
        "pattern",
        nargs="?",
        help="optional Python regex matched against logical name, object, or target",
    )
    run_tests.add_argument(
        "--emit",
        action="store_true",
        help="run selected Chisel TestBench objects with sbt runMain before CMake build",
    )
    run_tests.add_argument(
        "--configure",
        action="store_true",
        help="run 'cmake -S . -B BUILD_DIR' in sysc_tb before building",
    )
    run_tests.add_argument("--no-build", action="store_true", help="skip C++ build")
    run_tests.add_argument("--no-run", action="store_true", help="skip executing test binaries")
    run_tests.add_argument(
        "--build-dir",
        default="build",
        help="CMake build directory relative to sysc_tb (default: build)",
    )
    run_tests.add_argument(
        "--dry-run",
        action="store_true",
        help="print commands without executing them",
    )

    rename = sub.add_parser(
        "rename",
        help="rename project identity without moving package trees",
        description=(
            "Rename the project in build.sbt, project.json, and sysc_tb/CMakeLists.txt. "
            "This intentionally does not move or rewrite package directories."
        ),
    )
    rename.add_argument("new_name", help="new project name, e.g. my-accelerator")

    add_module = sub.add_parser(
        "add-module",
        help="create a Chisel module, optionally with a same-named test scaffold",
        description=(
            "Create a Chisel module in the selected package. Structured modules follow "
            "the Chext dataflow style with Foo_Config, val genPacket, desiredName, "
            "and elastic source/sink IO. Plain modules use a small ordinary Chisel IO. "
            "--with-test creates only a test scaffold; you still write the TestBenchTop "
            "classes and emit(...) calls yourself."
        ),
    )
    add_module.add_argument("module_name", help="Scala class-style module name, e.g. PacketPipe")
    style = add_module.add_mutually_exclusive_group()
    style.add_argument("--plain", action="store_true", help="generate a minimal plain Chisel module")
    style.add_argument(
        "--structured",
        action="store_true",
        help="generate a Chext structured module (default)",
    )
    add_module.add_argument("--with-test", action="store_true", help="also generate a same-named test scaffold")
    add_module.add_argument(
        "--package",
        help="target package; created if missing (default: project default package)",
    )
    add_module.add_argument("--force", action="store_true", help="overwrite generated files if present")

    add_test = sub.add_parser(
        "add-test",
        help="create Scala/SystemC test scaffold files for a named test",
        description=(
            "Create chisel_rtl/tests/<package>/<TestName>.tb.scala and "
            "sysc_tb/<package>/src/<TestName>.tb.cpp, plus the package-local "
            "sysc_tb/<package>/hdl directory. This command does not create or choose "
            "emitted hardware modules; edit the Scala test file and add emit(...) "
            "calls inside the marked TestBench object."
        ),
    )
    add_test.add_argument("test_name", help="Scala object stem for the test, e.g. Smoke")
    add_test.add_argument(
        "--package",
        help="test package; created if missing (default: project default package)",
    )
    add_test.add_argument("--force", action="store_true", help="overwrite generated test files if present")

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
        elif args.command == "sync":
            counts = project.sync()
            print(
                f"synced {counts['packages']} package(s), "
                f"{counts['modules']} module(s), {counts['tests']} test(s)"
            )
        elif args.command == "list-packages":
            for package in project.packages:
                suffix = " (default)" if package == project.default_package else ""
                print(f"{package}{suffix}")
        elif args.command == "add-package":
            project.add_package(args.package)
            print(f"added package {args.package}")
        elif args.command == "cleanup-template":
            project.cleanup_template()
            print("removed default TransformExample module/test")
        elif args.command == "list-tests":
            sites = project.list_tests(args.pattern)
            for site in sites:
                target = f"{site.package}.{site.logical_name}.tb"
                hdl = " ".join(site.hdl_modules)
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
            project.add_test(args.test_name, args.force, package=args.package)
            package = args.package or project.default_package
            print(f"added test scaffold {package}.{args.test_name}")
        else:
            raise AssertionError(args.command)
    except Exception as exc:
        print(f"error: {exc}")
        return 1

    return 0

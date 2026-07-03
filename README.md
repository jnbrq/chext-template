# chext-template

Minimal Chisel/Chext project template with SystemC testbench wiring.

Useful commands:

```sh
./manage.py --help
./manage.py add-module --help
./manage.py status
./manage.py check
./manage.py add-package alpha.beta
./manage.py list-packages
./manage.py add-module Foo --structured
./manage.py add-module Bar --plain --package alpha.beta
./manage.py add-test Smoke
./manage.py add-test PacketSmoke --package alpha.beta
./manage.py sync
./manage.py list-tests
./manage.py run-tests Foo --emit --configure
./manage.py rename my_project
./manage.py cleanup-template
```

The same manager is available from `chisel_rtl/` through a symlink:

```sh
cd chisel_rtl
./manage.py status
./manage.py sync
```

`rename` changes the project identity in `build.sbt`, `project.json`, and
`sysc_tb/CMakeLists.txt`. It does not move or rewrite package trees. Packages are explicit:
use `add-package <name>` or pass `--package <name>` when adding a module/test. Package
names map to directories in the usual Scala way, so `alpha.beta` becomes `alpha/beta`
under Chisel sources, Chisel tests, SystemC sources, package-local emitted HDL, and
`_common` includes.

Package-local emitted HDL is expected under:

```text
sysc_tb/<package-path>/
  CMakeLists.txt
  src/
  include/
  hdl/
```

For example, package `alpha.beta` uses `sysc_tb/alpha/beta/hdl/`. `add-package`,
`add-test`, and `sync` create these HDL directories with `.gitkeep` files. Managed
CMake entries use the matching `HDL_DIR`, so generated `.sv` and `.hdlinfo.json` files
are picked up from the same package tree where Chisel emits them.

Shared SystemC/C++/Verilog support lives under:

```text
sysc_tb/_common/
  src/
  include/
  verilog/
```

The template includes `chext_mem_1w1r.sv` and `chext_syncmem_1w1r.sv` in
`sysc_tb/_common/verilog/`.

Scala testbench sources live under `chisel_rtl/tests/<package>/` with the suffix
`.tb.scala`. `sync` scans Scala sources for this exact marker and parses the
object on the following line:

```scala
// manage: include test
object TransformExample_Tb extends chext.TestBench {
  emit(new TransformExample_TbTop)
}
```

`add-test <TestName>` creates only a named Scala/SystemC test scaffold. You write the
`TestBenchTop` classes and emission calls yourself. `sync` uses the
test object name for the CMake target and the matching SystemC source file, and uses the
emitted tops as `HDL_MODULES`. If an emitted testbench top defines a literal
`override def desiredName`, that emitted module name is used for CMake. Entries that no
longer have a matching marker-plus-emit pair are removed from CMake, but source files are
never deleted by `sync`.

`sync` also discovers manually added Chisel modules under `chisel_rtl/src/main/scala` and
updates `project.json` so the manifest stays aligned with the tree.

`run-tests` selects tests by regex against the logical name, object name, or CMake target.
By default it builds and runs matching SystemC tests from `sysc_tb/build`. Use `--emit`
to rerun the Chisel testbench objects first, and `--configure` to rerun CMake configure.

`cleanup-template` removes the starter `TransformExample` RTL/test files from the default package
and regenerates the managed CMake testbench region. It leaves `.gitkeep` files behind so
the empty package directories remain visible.

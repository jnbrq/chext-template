# Manager Reference

`manage.py` is the project-local automation entry point. It can be run from the
repository root or from `chisel_rtl/` through the symlink there.

```sh
./manage.py --help
./manage.py <command> --help
```

## Layout

Chisel/Chext sources live under:

```text
chisel_rtl/src/main/scala/<package-path>/
chisel_rtl/tests/<package-path>/
```

SystemC testbench files and emitted HDL live under matching package-local trees:

```text
sysc_tb/<package-path>/
  CMakeLists.txt
  src/
  include/
  hdl/
```

Shared C++/SystemC/Verilog support lives under:

```text
sysc_tb/_common/
  src/
  include/
  verilog/
```

Packages use Scala dotted names. For example, `alpha.beta` maps to
`alpha/beta` in the Chisel and SystemC trees.

## Commands

### `status`

Show project metadata, configured packages, and known modules.

```sh
./manage.py status
```

`list` is an alias for `status`.

### `check`

Validate the template structure and managed testbench declarations.

```sh
./manage.py check
```

### `sync`

Reconcile the filesystem with `project.json` and regenerate managed CMake.

```sh
./manage.py sync
```

`sync` discovers Scala modules, packages, and managed tests; updates
`project.json`; ensures package directories exist; refreshes C++ HDL include
blocks; and regenerates root/package CMake files.

### `add-package`

Register a package and create the corresponding Chisel/SystemC directory trees.

```sh
./manage.py add-package alpha.beta
```

### `list-packages`

List packages tracked in `project.json`.

```sh
./manage.py list-packages
```

The default package is marked in the output.

### `add-module`

Create a Chisel module in the selected package.

```sh
./manage.py add-module PacketPipe --structured
./manage.py add-module CounterCore --plain --package alpha.beta
./manage.py add-module PacketPipe --structured --with-test
```

Structured modules follow the Chext dataflow style described in
`doc/chext-dataflow-rulebook.md`. They define a `Foo_Config` case class, carry
an optional `desiredName`, use `val genPacket`, and import `cfg._` in both the
bundle and module.

Plain modules are intentionally small ordinary Chisel modules.

`--with-test` creates a same-named test scaffold. You still write the
testbench top classes and `emit(...)` calls yourself.

### `add-test`

Create Scala and SystemC test scaffold files for a named test.

```sh
./manage.py add-test Smoke
./manage.py add-test PacketSmoke --package alpha.beta
```

This command creates:

```text
chisel_rtl/tests/<package-path>/<TestName>.tb.scala
sysc_tb/<package-path>/src/<TestName>.tb.cpp
sysc_tb/<package-path>/hdl/.gitkeep
```

It does not choose emitted modules. Edit the Scala test file and add one or more
`emit(...)` calls inside the managed test object.

### `list-tests`

List managed tests, optionally filtered by Python regex.

```sh
./manage.py list-tests
./manage.py list-tests 'Packet|Smoke'
```

The regex is matched against the logical test name, Scala object name, and CMake
target.

### `run-tests`

Emit, configure, build, and run selected tests.

```sh
./manage.py run-tests
./manage.py run-tests Packet --emit --configure
./manage.py run-tests Smoke --emit --configure --dry-run
```

By default this builds and executes matching SystemC tests from `sysc_tb/build`.
Useful options:

- `--emit`: run selected Chisel `TestBench` objects with `sbt runMain` first.
- `--configure`: run `cmake -S . -B <build-dir>` in `sysc_tb` first.
- `--no-build`: skip the C++ build.
- `--no-run`: skip executing test binaries.
- `--build-dir DIR`: choose a CMake build directory relative to `sysc_tb`.
- `--dry-run`: print commands without executing them.

### `rename`

Rename the project identity.

```sh
./manage.py rename my_project
```

This updates `build.sbt`, `project.json`, `sysc_tb/CMakeLists.txt`, and the
workspace window titles. It intentionally does not move or rewrite package
directories.

### `cleanup-template`

Remove the starter `TransformExample` RTL/test files from the default package.

```sh
./manage.py cleanup-template
```

The command resyncs managed CMake afterward and leaves `.gitkeep` files behind
so empty package directories remain visible.

## Managed Tests

Scala testbench sources live under `chisel_rtl/tests/<package>/` and use the
suffix `.tb.scala`.

`sync` only treats a test as managed when it sees this exact marker immediately
before a `chext.TestBench` object:

```scala
// manage: include test
object Smoke_Tb extends chext.TestBench {
  emit(new Smoke_TbTop)
}
```

A single test object may contain multiple `emit(...)` calls. The matching CMake
target receives all emitted HDL modules through `HDL_MODULES`.

If an emitted top defines a literal `override def desiredName`, `sync` uses that
name in CMake. Otherwise it uses the emitted class name.

`sync` may remove stale CMake entries for tests whose marker or emits vanished,
but it does not delete Scala or C++ source files.

## C++ HDL Includes

SystemC testbench sources can contain this managed include block:

```cpp
// BEGIN MANAGED HDL INCLUDES
#include <Smoke_TbTop.hpp>
// END MANAGED HDL INCLUDES
```

`sync` updates the block from the Scala `emit(...)` calls for the corresponding
test. This is useful when a test emits multiple hardware tops.

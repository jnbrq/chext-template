# chext-template

Minimal Chisel/Chext project template with SystemC testbench wiring.

Useful commands:

```sh
./manage.py status
./manage.py check
./manage.py add-package alpha.beta
./manage.py list-packages
./manage.py add-module Foo --structured --with-test
./manage.py add-module Bar --plain --with-test --package alpha.beta
./manage.py add-test Foo
./manage.py sync-tests
./manage.py list-tests
./manage.py run-tests Foo --emit --configure
./manage.py rename my_project
./manage.py cleanup-template
```

`rename` changes the project identity in `build.sbt`, `project.json`, and
`sysc_tb/CMakeLists.txt`. It does not move or rewrite package trees. Packages are explicit:
use `add-package <name>` or pass `--package <name>` when adding a module/test. Package
names map to directories in the usual Scala way, so `alpha.beta` becomes `alpha/beta`
under Chisel sources, Chisel tests, SystemC sources, and common includes.

Scala testbench sources live under `chisel_rtl/tests/<package>/` with the suffix
`.tb.scala`. `sync-tests` scans Scala sources for this exact marker and parses the
object on the following line:

```scala
// manage: include test
object Example_Tb extends chext.TestBench {
  emit(new Example_TbTop)
}
```

It then regenerates the managed testbench section in `sysc_tb/CMakeLists.txt`. If a
testbench top defines a literal `override def desiredName`, that emitted module name is
used for CMake. Entries that no longer have a matching marker-plus-emit pair are removed
from CMake, but source files are never deleted by `sync-tests`.

`run-tests` selects tests by regex against the logical name, object name, or CMake target.
By default it builds and runs matching SystemC tests from `sysc_tb/build`. Use `--emit`
to rerun the Chisel testbench objects first, and `--configure` to rerun CMake configure.

`cleanup-template` removes the starter `Example` RTL/test files from the default package
and regenerates the managed CMake testbench region. It leaves `.gitkeep` files behind so
the empty package directories remain visible.

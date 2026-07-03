# chext-template

Minimal Chisel/Chext project template with SystemC testbench wiring.

This repository is meant to be copied or renamed into a real project. It keeps
the Chisel/Chext RTL under `chisel_rtl/`, the SystemC testbench tree under
`sysc_tb/`, and project-management helpers in `_manage/` behind the top-level
`manage.py` command.

Start with:

```sh
./manage.py status
./manage.py check
./manage.py add-module PacketPipe --structured
./manage.py add-test Smoke
./manage.py sync
```

The same manager is available from `chisel_rtl/`:

```sh
cd chisel_rtl
./manage.py status
./manage.py sync
```

Documentation lives under `doc/`:

- `doc/manage.md`: project manager commands, package layout, sync behavior, and
  test-running workflow.
- `doc/chext-dataflow-rulebook.md`: Chext dataflow style rules used by the
  structured module templates.

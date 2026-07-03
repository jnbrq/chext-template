# Chext Dataflow Rulebook for AI

## 1. Imports

Always use the elastic alias:

```scala
import chisel3._
import chisel3.util._
import chisel3.experimental.prefix

import chext.{elastic => e}
import e.ConnectOp._
```

`import e.ConnectOp._` is required for elastic connections:

```scala
source :=> sink
```

Use `:=>` for elastic stream connections. Avoid manual `$valid`, `$ready`, and `$bits` wiring unless implementing a primitive or integrating with non-elastic logic.

For AXI code:

```scala
import chext.amba.{axi4 => a4}
import chext.{elastic => e}
import e.ConnectOp._

import a4.Casts._
import a4.Ops._
import a4.{full => a4f}
import a4.{lite => a4l}
import a4f.{components => a4fc}
import a4l.{components => a4lc}
```

Do not directly import everything from the `axi4` package. Prefer the aliases above so AXI full, AXI-lite, components, casts, and ops stay visually distinct.

For load/store and streaming memory movers:

```scala
import chext.{ldstr, stream}
import chext.amba.{axi4 => a4}
import chext.{elastic => e}
import e.ConnectOp._
import a4.Ops._
```

For memory modules:

```scala
import chext.memory
import chext.memory.ConnectOp._
import chext.{elastic => e}
import e.ConnectOp._
```

For floating point modules:

```scala
import chext.float
import chext.{elastic => e}
import e.ConnectOp._
```

---

## 2. Naming Convention

Always instantiate elastic components like this:

```scala
val transform0 = new e.Transform(source, sink) { ... }
val fork0 = new e.Fork(source) { ... }
val join0 = new e.Join(sink) { ... }
val demux0 = new e.Demux(source, sinks, select) { ... }
val demuxNs0 = new e.DemuxNs(source, sinks) { ... }
val mux0 = new e.Mux(sources, sink, select) { ... }
val arbiterNs0 = new e.ArbiterNs(sources, sink, e.Chooser.rr) { ... }
val queue0 = new e.Queue(source, sink, count = 4) { ... }
val drop0 = new e.Drop(source, sink) { ... }
val repeat0 = new e.Repeat(source, sink, wIndex = 5) { ... }
val count0 = new e.Count(source, sink, genState) { ... }
val counter0 = new e.Counter(sink) { ... }
val transducer0 = new e.Transducer(source, sink) { ... }
val const0 = new e.Const(sink) { ... }
```

Rule:

```text
transform0  -> Transform
fork0       -> Fork
join0       -> Join
demux0      -> Demux
demuxNs0    -> DemuxNs
mux0        -> Mux
arbiterNs0  -> ArbiterNs
queue0      -> Queue
drop0       -> Drop
repeat0     -> Repeat
count0      -> Count
counter0    -> Counter
transducer0 -> Transducer
const0      -> Const
```

---

## 3. Interfaces and Wires

```scala
val source = IO(e.Source(genPacket))
val sink = IO(e.Sink(genPacket))

val ewire0 = e.EWire(genPacket)
val ewire1 = e.EWire.like(source)
```

Prefer `EWire.like(...)` when preserving an existing stream type.

Every variable assigned from `e.EWire(...)` or `e.EWire.like(...)` must start with `ewire`. Do not use names such as `tmp`, `wire`, `chosen`, `transformed`, or `sinks` for elastic wires. Use names such as `ewireChosen`, `ewireTransformed`, or `ewireSinks`.

---

## 4. Transform

Use `Transform` for one-input / one-output combinational mapping.

```scala
val transform0 = new e.Transform(source, sink) {
  out := in
  out.data := in.data + 1.U
}
```

Rules:

- No registers.
- No packet dropping.
- No packet expansion.
- Assign every output field.
- Use `out := in` first for pass-through bundles, then override fields.

---

## 5. Queue

Prefer the direct source/sink API:

```scala
val queue0 = new e.Queue(
  source,
  sink,
  count = 8,
  pipe = true,
  flow = true
)
```

With output transformation:

```scala
val queue0 = new e.Queue(source, sink, count = 4, pipe = true, flow = true) {
  out { in =>
    val result = Wire(chiselTypeOf(sink.$bits))
    result := in
    result.data := in.data + 1.U
    result
  }
}
```

Use queues to:

- break timing paths,
- avoid ready/valid cycles,
- decouple pipeline stages,
- buffer side metadata.

Elastic stream buffer helpers:

```scala
val ewireAfterSource = e.SourceBuffer(source, count = 2)
ewireAfterSource :=> sink

val ewireBeforeSink = e.SinkBuffer(sink, count = 2)
source :=> ewireBeforeSink

val ewireAfterLeft = e.LeftBuffer(source, count = 2)
ewireAfterLeft :=> sink

val ewireBeforeRight = e.RightBuffer(sink, count = 2)
source :=> ewireBeforeRight
```

Rules:

- `e.SourceBuffer` and `e.LeftBuffer` are equivalent helpers that place a queue after a source-like stream and return the buffered stream.
- `e.SinkBuffer` and `e.RightBuffer` are equivalent helpers that place a queue before a sink-like stream and return the buffered stream.
- Use `SourceBuffer` / `SinkBuffer` when thinking in source/sink direction.
- Use `LeftBuffer` / `RightBuffer` when thinking in left-to-right pipeline direction.

---

## 6. Fork

Use `fork()` for full-packet forwarding.

```scala
val fork0 = new e.Fork(source) {
  fork() :=> sink0
  fork() :=> sink1
}
```

Use `fork { ... }` for derived values from `in`.

```scala
val fork0 = new e.Fork(source) {
  fork { in.payload } :=> payloadSink
  fork { in.meta } :=> metaSink
}
```

Do not write `fork(in.x)`. Prefer either:

```scala
fork()
```

or:

```scala
fork { in.x }
```

---

## 7. Join

Use `join(source)` when directly joining a full source.

```scala
val join0 = new e.Join(sink) {
  out.payload := join(payloadSource)
  out.meta := join(metaSource)
}
```

Use local values when deriving from joined sources.

```scala
val join0 = new e.Join(sink) {
  val a = join(sourceA)
  val b = join(sourceB)

  out.sum := a.value + b.value
  out.last := a.last && b.last
}
```

Keep joins explicit and aligned. Do not manually inspect multiple `$valid`s.

---

## 8. Zip

Use `Zip` for tuple-style synchronization.

```scala
val zipped = e.Zip(sourceA, sourceB)

val transform0 = new e.Transform(zipped, sink) {
  out.a := in._1
  out.b := in._2
}
```

Use `Join` when constructing a named output bundle. Use `Zip` when tuple form is simpler.

---

## 9. Demux

Use `Demux` when the select value is a separate elastic stream.

```scala
val demux0 = new e.Demux(source, sinks, select)
```

For multi-beat packets, use `last { ... }` so one select token routes a whole packet.

```scala
val demux0 = new e.Demux(source, sinks, select) {
  last { in =>
    in.last
  }
}
```

With payload transformation:

```scala
val demux0 = new e.Demux(source, sinks, select) {
  last { in =>
    in.last
  }

  outExplicit { (in, out) =>
    out.data := in.data
    out.last := in.last
  }
}
```

Rules:

- Use `Demux` when selection and payload are separate streams.
- Use `last { in => in.last }` for burst-like or multi-beat streams.
- The select stream should advance only at packet boundaries.

---

## 10. DemuxNs

Use `DemuxNs` when the destination is computed from the current input token.

```scala
val demuxNs0 = new e.DemuxNs(source, sinks) {
  select { in =>
    in.sel
  }
}
```

Use `out { ... }` when changing the payload:

```scala
val demuxNs0 = new e.DemuxNs(source, sinks) {
  select { in =>
    in.sel
  }

  out { in =>
    in.payload
  }
}
```

Use `outExplicit { ... }` for multi-field assignment:

```scala
val demuxNs0 = new e.DemuxNs(source, sinks) {
  select { in =>
    in.sel
  }

  outExplicit { (in, out) =>
    out.data := in.data
    out.last := in.last
  }
}
```

Rules:

- `DemuxNs`: select is computed from `in`.
- `Demux`: select comes from another elastic stream.
- For multi-beat packets that must stay on the same route, use `Demux` with a queued select stream, not per-beat `DemuxNs`.

---

## 11. Mux

Use `Mux` when a select stream chooses the input.

```scala
val mux0 = new e.Mux(sources, sink, select)
```

For multi-beat packets, use `last { ... }` so one select token chooses a whole packet.

```scala
val mux0 = new e.Mux(sources, sink, select) {
  last { in =>
    in.last
  }
}
```

With payload transformation:

```scala
val mux0 = new e.Mux(sources, sink, select) {
  last { in =>
    in.last
  }

  outExplicit { (in, out) =>
    out.data := in.data
    out.last := in.last
  }
}
```

Rules:

- Use `Mux` when the selected source is driven by an elastic select stream.
- Use `last { in => in.last }` for packet/burst boundaries.
- Use `Arbiter` instead when the choice should be policy-driven.

---

## 12. Arbiter

Use `Arbiter` when choice is policy-driven.

```scala
val arbiter0 = new e.Arbiter(
  sources,
  sink,
  e.Chooser.rr
)
```

This form is the normal rulebook spelling for policy-driven many-to-one merging. In the implementation, the helper without a select stream constructs `ArbiterNs`.

Use `ArbiterNs` directly when you specifically want the code to say that there is **no selected-index output stream**.

```scala
val arbiterNs0 = new e.ArbiterNs(
  sources,
  sink,
  e.Chooser.rr
)
```

With payload transformation:

```scala
val arbiterNs0 = new e.ArbiterNs(sources, sink, e.Chooser.rr) {
  out { in =>
    in.payload
  }
}
```

With explicit multi-field assignment:

```scala
val arbiterNs0 = new e.ArbiterNs(sources, sink, e.Chooser.rr) {
  outExplicit { (in, out) =>
    out.data := in.data
    out.last := in.last
  }
}
```

Use `Arbiter` with an explicit select output when downstream logic needs to know which source was chosen.

```scala
val ewireChosen = e.EWire(UInt(log2Ceil(sources.length).W))

val arbiter0 = new e.Arbiter(
  sources,
  sink,
  ewireChosen,
  e.Chooser.rr
)
```

Rules:

- `ArbiterNs`: policy-driven many-to-one merge with no selected-index output.
- `Arbiter`: policy-driven many-to-one merge with selected-index output.
- `e.Arbiter(sources, sink, chooser)` is a convenience form that resolves to `ArbiterNs`.
- Use `e.Chooser.rr` for round-robin arbitration when fairness matters.
- Use `e.Chooser.priority` when lower-index sources should intentionally have priority.
- Prefer `e.Chooser.rr` as the default unless source order encodes priority.
- Use `Mux` instead when an external select stream chooses the input.
- Plain arbitration may interleave beats unless the surrounding protocol or a side mechanism prevents it.

---

## 13. Stall

Use `Stall` for conditional backpressure.

```scala
val stall0 = new e.Stall(source, sink) {
  out := in

  cond {
    !canAccept
  }

  fire {
    accepted := true.B
  }
}
```

`cond { ... }` means stall while true. `fire { ... }` runs on successful transfer.

---

## 14. Drop

Use `Drop` for conditional token removal.

```scala
val drop0 = new e.Drop(source, sink) {
  out := in

  cond {
    shouldDrop
  }

  fire {
    forwarded := true.B
  }
}
```

`cond { ... }` means drop while true. When the condition is true, the input token is consumed and no output token is produced. When the condition is false, the token is forwarded normally.

Rules:

- Use `Drop` when filtering tokens out of a stream.
- Use `Stall` when a token must be preserved until a condition clears.
- Assign `out` exactly as in `Transform`; commonly start with `out := in` and then override fields.
- Keep the drop condition stable for the current token. If the condition can change while a token is waiting downstream, insert a buffer or compute the decision earlier.

---

## 15. Repeat

Use `Repeat` for one packet producing multiple packets.

```scala
val repeat0 = new e.Repeat(source, sink, wIndex = 5) {
  len { in =>
    in.count
  }

  outExplicit { (in, index, first, last, out) =>
    out.data := in.data
    out.index := index
    out.first := first
    out.last := last
  }
}
```

`wIndex` is the bit width of the generated repeat index. It is not the maximum repeat length itself. The maximum representable index is determined by `wIndex`.

Use `Repeat` for regular expansion. Use `Transducer` only when expansion/control is stateful or irregular.

---

## 16. Count

Use `Count` when one input token should drive a counted sequence of output tokens using explicit state.

```scala
val count0 = new e.Count(source, sink, UInt(8.W)) {
  init { in =>
    in.count
  }

  cond { (in, state) =>
    state =/= 0.U
  }

  next { (in, state) =>
    state - 1.U
  }

  outExplicit { (in, state, first, last, out) =>
    out.data := in.data
    out.index := in.count - state
    out.first := first
    out.last := last
  }
}
```

Rules:

- `init { in => ... }` computes the initial state for the current input token.
- `cond { (in, state) => ... }` decides whether the current state should produce an output token.
- `next { (in, state) => ... }` computes the next state after a successful output transfer.
- `out { ... }` or `outExplicit { ... }` generates the output token and receives `first` / `last` flags.
- Use `Count` for structured iterative expansion where `Repeat` is too simple but `Transducer` would be unnecessarily manual.

---

## 17. Counter

Use `Counter` to generate a monotonically increasing `UInt` elastic stream.

```scala
val counter0 = new e.Counter(
  sink,
  maxValueExclusive = 16,
  start = 0
)
```

Default form:

```scala
val counter0 = new e.Counter(sink)
```

Helper forms:

```scala
val ewireCounter0 = e.Counter(maxValueExclusive = 16, start = 0)
val ewireCounter1 = e.Counter.fromWidth(width = 4, start = 0)
```

Rules:

- The constructor form is `new e.Counter(sink, maxValueExclusive = -1, start = 0)`.
- `sink` must be an elastic `Interface[UInt]` with known width.
- The counter emits the current count into `sink` and increments when `sink.fire`.
- `maxValueExclusive = -1` means use the full range implied by `sink.$bits.getWidth`.
- If `maxValueExclusive` is positive, the counter wraps to zero after `maxValueExclusive - 1`.
- `start` sets the reset value and must be less than the effective maximum.

---

## 18. Transducer

Use `Transducer` only for stateful consume/produce behavior.

Actions:

- `accept`: consume input and produce output.
- `consume`: consume input only.
- `produce`: produce output only.
- `stall`: consume nothing and produce nothing.

```scala
val transducer0 = new e.Transducer(source, sink) {
  val acc = RegInit(0.U(32.W))
  val active = RegInit(false.B)

  out := in
  out.data := acc + in.data

  packet {
    when(!active) {
      when(in.last) {
        accept {
          acc := 0.U
        }
      }.otherwise {
        consume {
          acc := in.data
          active := true.B
        }
      }
    }.otherwise {
      when(in.last) {
        accept {
          acc := 0.U
          active := false.B
        }
      }.otherwise {
        consume {
          acc := acc + in.data
        }
      }
    }
  }
}
```

Rules:

- Put state updates inside actions.
- Select exactly one action per packet step.
- Prefer simpler elastic components when possible.

---

## 19. AXI Basics

Use AXI components to build functional designs instead of manually rebuilding AXI protocol behavior.

Typical config:

```scala
val axiCfg = a4.Config(
  wId = 4,
  wAddr = 32,
  wData = 256,
  read = true,
  write = true,
  lite = false
)
```

Typical IO:

```scala
val s_axi = IO(a4.full.Slave(axiCfg))
val m_axi = IO(a4.full.Master(axiCfg))
```

Connect:

```scala
s_axi :=> m_axi
```

Boundary buffering:

```scala
val s_axi_ = a4f.SlaveBuffer(s_axi, a4.BufferConfig.all(2))
val m_axi_ = a4f.MasterBuffer(m_axi, a4.BufferConfig.all(2))
```

`SlaveBuffer` and `MasterBuffer` are the preferred AXI boundary names. Use the left/right aliases only when the surrounding code is organized as a left-to-right pipeline.

Channel transform:

```scala
val transform0 = new e.Transform(s_axi_.ar, m_axi_.ar) {
  out := in
  out.addr := in.addr + offset
}
```

AXI rules:

- Treat each AXI channel as an elastic stream.
- Read path: `ar` and `r`.
- Write path: `aw`, `w`, and `b`.
- Preserve `id`, `last`, `resp`, `user`, `len`, `size`, and `burst` unless intentionally changing them.
- Use buffers at component boundaries.
- Use side queues when one channel determines later routing of another channel.
- Use `last { in => in.last }` for burst-carrying elastic channels.
- Do not mix full AXI and AXI-lite casually.

---

## 20. AXI Component Reference

### BufferConfig

```scala
a4.BufferConfig(
  aw = 2,
  w  = 2,
  b  = 2,
  ar = 2,
  r  = 2
)

a4.BufferConfig.all(2)
```

### SlaveBuffer / MasterBuffer

```scala
val s_axi_ = a4f.SlaveBuffer(
  s_axi,
  cfg = a4.BufferConfig.all(2),
  name = "slaveBuffer"
)

val m_axi_ = a4f.MasterBuffer(
  m_axi,
  cfg = a4.BufferConfig.all(2),
  name = "masterBuffer"
)
```

Use `a4f.SlaveBuffer` on incoming slave-side ports and `a4f.MasterBuffer` on outgoing master-side ports. Keep `SlaveBuffer` / `MasterBuffer` as the preferred AXI boundary names.

There are also buffer components for `a4l` and `a4`. Use them appropriately with compatible interface types.

Equivalent left-to-right naming aliases:

```scala
val s_axi_left_ = a4f.LeftBuffer(s_axi, a4.BufferConfig.all(2))
val m_axi_right_ = a4f.RightBuffer(m_axi, a4.BufferConfig.all(2))

val s_axil_left_ = a4l.LeftBuffer(s_axil, a4.BufferConfig.all(2))
val m_axil_right_ = a4l.RightBuffer(m_axil, a4.BufferConfig.all(2))

val s_axi_raw_left_ = a4.LeftBuffer(s_axi_raw, a4.BufferConfig.all(2))
val m_axi_raw_right_ = a4.RightBuffer(m_axi_raw, a4.BufferConfig.all(2))
```

Rules:

- `a4f.LeftBuffer` is equivalent to `a4f.SlaveBuffer`; `a4f.RightBuffer` is equivalent to `a4f.MasterBuffer`.
- `a4l.LeftBuffer` is equivalent to `a4l.SlaveBuffer`; `a4l.RightBuffer` is equivalent to `a4l.MasterBuffer`.
- `a4.LeftBuffer` is equivalent to `a4.SlaveBuffer`; `a4.RightBuffer` is equivalent to `a4.MasterBuffer`.
- Prefer `SlaveBuffer` / `MasterBuffer` for AXI interface boundaries. Use `LeftBuffer` / `RightBuffer` only as left-to-right naming aliases.

---

### AXI Mux

Many AXI slave ports to one AXI master.

```scala
val mux0 = Module(new a4fc.Mux(
  a4fc.MuxConfig(
    axiSlaveCfg = axiCfg,
    numSlaves = 4,
    slaveBuffers = a4.BufferConfig.all(0),
    masterBuffers = a4.BufferConfig.all(2),
    arbiterPolicy = e.Chooser.rr
  )
))
```

Ports:

```scala
mux0.s_axi  // Vec(numSlaves, a4.full.Slave(axiSlaveCfg))
mux0.m_axi  // a4.full.Master(axiMasterCfg)
```

Effect:

- Arbitrates `ar` and `aw`.
- Routes `r` and `b` back using extended IDs.
- Routes `w` using a side select queue.

---

### AXI Demux

One AXI slave port to many AXI master ports, selected by address decode.

```scala
val demux0 = Module(new a4fc.Demux(
  a4fc.DemuxConfig(
    axiSlaveCfg = axiCfg,
    numMasters = 4,
    decodeFn = (addr: UInt) => addr(13, 12),
    numIdsTrackedRead = 4,
    numIdsTrackedWrite = 4,
    numOutstandingRead = 16,
    numOutstandingWrite = 16,
    capacityPortQueueW = 8,
    slaveBuffers = a4.BufferConfig.all(2),
    masterBuffers = a4.BufferConfig.all(0),
    arbiterPolicy = e.Chooser.rr
  )
))
```

Ports:

```scala
demux0.s_axi  // a4.full.Slave(axiSlaveCfg)
demux0.m_axi  // Vec(numMasters, a4.full.Master(axiMasterCfg))
```

Effect:

- Decodes `ar.addr` / `aw.addr`.
- Sends requests to selected master.
- Tracks IDs so responses return correctly.
- Uses a queue so `w` follows the selected `aw`.

---

### IdMux

Many AXI slave ports to one AXI master by extending IDs.

```scala
val idMux0 = Module(new a4fc.IdMux(
  a4fc.IdMuxConfig(
    axiSlaveCfg = axiCfg,
    wIdSel = 2,
    arbiterPolicy = e.Chooser.rr
  )
))
```

Ports:

```scala
idMux0.s_axi  // Vec(1 << wIdSel, a4.full.Slave(axiSlaveCfg))
idMux0.m_axi  // a4.full.Master(axiMasterCfg)
```

Effect:

- Adds source-port bits into the AXI ID.
- Arbitrates requests.
- Demuxes responses using high ID bits.

---

### IdDemux

One AXI slave port to many AXI master ports by stripping low ID bits.

```scala
val idDemux0 = Module(new a4fc.IdDemux(
  a4fc.IdDemuxConfig(
    axiSlaveCfg = axiCfg,
    wIdSel = 2,
    capacityPortQueueW = 8,
    arbiterPolicy = e.Chooser.rr
  )
))
```

Ports:

```scala
idDemux0.s_axi  // a4.full.Slave(axiSlaveCfg)
idDemux0.m_axi  // Vec(1 << wIdSel, a4.full.Master(axiMasterCfg))
```

Effect:

- Uses low ID bits as destination select.
- Removes those bits before forwarding.
- Reattaches ID bits on responses.

---

### IdSerialize

Serializes transactions to ID zero.

```scala
val idSerialize0 = Module(new a4fc.IdSerialize(
  a4fc.IdSerializeConfig(
    axiSlaveCfg = axiCfg,
    numOutstandingRead = 4,
    numOutstandingWrite = 4,
    wIdSelect = 0
  )
))
```

Ports:

```scala
idSerialize0.s_axi
idSerialize0.m_axi
```

Effect:

- Converts multi-ID traffic into single-ID traffic.
- Saves original IDs in side streams.
- Restores IDs on `r` / `b`.

---

### Upscale

Converts narrow slave data width to wider master data width.

```scala
val upscale0 = Module(new a4fc.Upscale(
  a4fc.UpscaleConfig(
    axiSlaveCfg = axiCfg.copy(wId = 0, wData = 64),
    wDataMaster = 256,
    numOutstandingRead = 32,
    numOutstandingWrite = 32
  )
))
```

Ports:

```scala
upscale0.s_axi
upscale0.m_axi
```

Requires:

- full AXI,
- `axiSlaveCfg.wId == 0`,
- `wDataMaster > axiSlaveCfg.wData`,
- power-of-two data widths.

---

### Downscale

Converts wide slave data width to narrower master data width.

```scala
val downscale0 = Module(new a4fc.Downscale(
  a4fc.DownscaleConfig(
    axiSlaveCfg = axiCfg.copy(wId = 0, wData = 256),
    wDataMaster = 64,
    numOutstandingRead = 32,
    numOutstandingWrite = 32
  )
))
```

Ports:

```scala
downscale0.s_axi
downscale0.m_axi
```

Requires:

- full AXI,
- `axiSlaveCfg.wId == 0`,
- `wDataMaster < axiSlaveCfg.wData`,
- power-of-two data widths.

---

### Unburst

Breaks burst transactions into single-beat transactions.

```scala
val unburst0 = Module(new a4fc.Unburst(
  a4fc.UnburstConfig(
    axiSlaveCfg = axiCfg.copy(wId = 0)
  )
))
```

Ports:

```scala
unburst0.s_axi
unburst0.m_axi
```

Use before components that cannot handle bursts, or before AXI3-compatible constraints when needed.

---

### ResponseBuffer

Buffers response channels with bounded capacity.

```scala
val responseBuffer0 = Module(new a4fc.ResponseBuffer(
  a4fc.ResponseBufferConfig(
    axiCfg = axiCfg,
    bufLengthR = 2,
    bufLengthB = 2,
    writePassThrough = false,
    readPassThrough = false
  )
))
```

Ports:

```scala
responseBuffer0.s_axi
responseBuffer0.m_axi
```

Use for:

- buffering `r`,
- buffering `b`,
- controlling response backpressure.

### WriteBuffer

Buffers the AXI write data path while coupling `aw` admission to completed write-data bursts. Use it when write address and write data backpressure can otherwise form a deadlock, especially around components where read and write channels share downstream resources.

```scala
val writeBuffer0 = Module(new a4fc.WriteBuffer(
  axiCfg = axiCfg,
  cfg = a4fc.WriteBufferConfig(
    bufLengthW = 64,
    bufLengthAW = 2
  )
))

source.aw :=> writeBuffer0.source.aw
source.w  :=> writeBuffer0.source.w
writeBuffer0.sink.aw :=> sink.aw
writeBuffer0.sink.w  :=> sink.w
```

As a full-interface helper:

```scala
a4fc.WriteBuffer(
  master,
  slave,
  a4fc.WriteBufferConfig(
    bufLengthW = 64,
    bufLengthAW = 2
  )
)
```

Rules:

- Use only with full AXI write-capable interfaces.
- `bufLengthW` and `bufLengthAW` must be at least one.
- Use it when `aw` must not outrun available buffered `w` burst completion capacity.
- Do not insert it as a substitute for general boundary buffering; use `a4f.SlaveBuffer` / `a4f.MasterBuffer` for ordinary timing boundaries.

---

### ProtocolConverter

General AXI full protocol converter.

```scala
val protocolConverter0 = Module(new a4fc.ProtocolConverter(
  a4fc.ProtocolConverterConfig(
    axiSlaveCfg = slaveCfg,
    axiMasterCfg = masterCfg,
    slaveNeverBursts = false
  )
))
```

Ports:

```scala
protocolConverter0.s_axi
protocolConverter0.m_axi
```

Internally composes:

- `IdDemux`,
- `IdSerialize`,
- `Upscale`,
- `Unburst`,
- `Downscale`,
- `IdMux`.

Use when adapting:

- data width,
- ID width,
- burst behavior,
- AXI3 compatibility.

---


## 21. Configuration Ownership

Keep all externally meaningful configuration in the parent module config class. Do this for internal submodule configs, AXI configs, memory configs, and Chisel types used by elastic IO.

```scala
case class ParentConfig(
    axiCfg: a4.Config,
    wLength: Int = 32,
    genUser: UInt = UInt(0.W),
    numOutstandingTasks: Int = 8
) {
  require(!axiCfg.lite)
  require(axiCfg.read && axiCfg.write)

  val loadCfg = ldstr.LoadConfig(
    axiCfg = axiCfg,
    genUser = genUser,
    numOutstandingTasks = numOutstandingTasks
  )

  val storeCfg = ldstr.StoreConfig(
    axiCfg = axiCfg,
    genUser = genUser,
    numOutstandingTasks = numOutstandingTasks
  )

  val genTask = loadCfg.genTask
  val genLoadResult = loadCfg.genResult
  val genStoreData = storeCfg.genData
}

class Parent(val cfg: ParentConfig) extends Module {
  import cfg._

  val sourceTask = IO(e.Source(genTask))
  val sinkLoadResult = IO(e.Sink(genLoadResult))
  val sourceStoreData = IO(e.Source(genStoreData))

  private val load0 = Module(new ldstr.Load(loadCfg))
  private val store0 = Module(new ldstr.Store(storeCfg))
}
```

Rules:

- Put `a4.Config`, `memory.RawMemConfig`, `memory.PortConfig`, `ldstr.LoadConfig`, `ldstr.StoreConfig`, `stream.ReadConfig`, `stream.WriteConfig`, and floating point type choices in the parent config when they are part of the module contract.
- Put generated Chisel types in the config: `genTask`, `genResult`, `genData`, `genUser`, `genPacket`, and memory request/response types.
- Derive internal configs from parent config fields instead of recomputing widths inside the module body.
- Use `import cfg._` inside the module and wire IO from `cfg.gen...` values.
- Store only stable type/config information in config classes. Runtime state still belongs in registers, counters, queues, or transducers.

---

## 22. Load/Store API (`chext.ldstr`)

Use `ldstr.Load` and `ldstr.Store` for single-beat AXI full memory operations. They translate task/data streams to AXI `ar/r` or `aw/w/b` channels.

### Load

```scala
val loadCfg = ldstr.LoadConfig(
  axiCfg = axiCfg.copy(read = true, write = false, lite = false),
  genUser = UInt(8.W),
  numOutstandingTasks = 8
)

val load0 = Module(new ldstr.Load(loadCfg))

sourceTask :=> load0.sourceTask
load0.sinkResult :=> sinkResult
load0.m_axi :=> m_axi
```

Task/result shape:

```scala
// task
address: UInt(axiCfg.wAddr.W)
user:    genUser

// result
data: UInt(axiCfg.wData.W)
user: genUser
```

Load rules:

- `axiCfg` must be full AXI and must enable `read`.
- Each task issues one AXI read beat with `len := 0` and `burst := INCR`.
- Use the task `user` field to preserve side metadata across the read response.
- Addresses should be aligned to the AXI data width; the implementation prints an unaligned-access warning when a task fires with a misaligned address.
- If the AXI config also enables write channels, unused write channels are explicitly marked inactive by the module.

### Store

```scala
val storeCfg = ldstr.StoreConfig(
  axiCfg = axiCfg.copy(read = false, write = true, lite = false),
  genUser = UInt(8.W),
  numOutstandingTasks = 8
)

val store0 = Module(new ldstr.Store(storeCfg))

sourceTask :=> store0.sourceTask
sourceData :=> store0.sourceData
store0.sinkResult :=> sinkResult
store0.m_axi :=> m_axi
```

Task/data/result shape:

```scala
// task
address: UInt(axiCfg.wAddr.W)
user:    genUser

// data
UInt(axiCfg.wData.W)

// result
user: genUser
```

Store rules:

- `axiCfg` must be full AXI and must enable `write`.
- Each task issues one AXI write beat with full strobe and `last := true.B`.
- `sourceTask` and `sourceData` are independent elastic streams; make sure their ordering matches.
- Use the result stream as the write-completion signal.
- If the AXI config also enables read channels, unused read channels are explicitly marked inactive by the module.

Use `ldstr` when accesses are scalar or already one beat per task. Use `stream` when a task may cover many beats.

---

## 23. Stream Read/Write API (`chext.stream`)

Use `stream.Read` and `stream.Write` for burst-capable memory movement. A stream task has an address, a length in beats, and a user field. The modules chunk long tasks into AXI bursts using `maxBurstLength`.

### Stream task

```scala
val readCfg = stream.ReadConfig(
  axiCfg = axiCfg.copy(read = true, write = false, lite = false),
  genUser = UInt(8.W),
  resultMode = stream.ReadResultMode.LastAlwaysInvalid,
  maxBurstLength = 256,
  wLength = 32,
  numOutstandingTasks = 8
)

// task fields
address: UInt(axiCfg.wAddr.W)
length:  UInt(wLength.W)
user:    genUser
```

### Stream read

```scala
val read0 = Module(new stream.Read(readCfg))

sourceTask :=> read0.sourceTask
read0.sinkResult :=> sinkResult
read0.m_axi :=> m_axi
```

Read result fields:

```scala
data:  UInt(axiCfg.wData.W)
index: UInt(wLength.W)
last:  Bool()
valid: Bool() // only for LastSometimesInvalid mode
user:  genUser
```

Read result modes:

- `DropEmpty`: empty tasks produce no result tokens.
- `LastAlwaysInvalid`: every task produces a final invalid marker; a task of length `N` produces `N + 1` tokens.
- `LastSometimesInvalid`: non-empty tasks produce valid data tokens; empty tasks produce one invalid last token.

Read rules:

- `axiCfg` must be full AXI and must enable `read`.
- Use `index` to reconstruct beat order within the task.
- Use `last` as the task boundary, not necessarily an AXI burst boundary.
- For empty-task-sensitive pipelines, choose the result mode deliberately and document it in the parent config.
- Addresses should be aligned to the AXI data width.

### Stream write

```scala
val writeCfg = stream.WriteConfig(
  axiCfg = axiCfg.copy(read = false, write = true, lite = false),
  genUser = UInt(8.W),
  resultMode = stream.WriteResultMode.KeepAll,
  maxBurstLength = 256,
  wLength = 32,
  numOutstandingTasks = 8
)

val write0 = Module(new stream.Write(writeCfg))

sourceTask :=> write0.sourceTask
sourceData :=> write0.sourceData
write0.sinkResult :=> sinkResult
write0.m_axi :=> m_axi
```

Write data/result shape:

```scala
// data
UInt(axiCfg.wData.W)

// result
user: genUser
```

Write result modes:

- `KeepAll`: emit a completion result for every task, including empty tasks.
- `DropEmpty`: emit completion results only for non-empty tasks.

Write rules:

- `axiCfg` must be full AXI and must enable `write`.
- `sourceData` must provide exactly `length` data beats for each non-empty task.
- Use `maxBurstLength <= 256` for AXI4 and `<= 16` for AXI3-compatible configs.
- Use completion results to synchronize later metadata/control.
- Use full-width data beats; byte-enable/strobe behavior is handled internally for normal full-beat writes.

---

## 24. Memory Modules (`chext.memory`)

Use `chext.memory` when building memory-backed structures with explicit read/write request-response interfaces, raw memory ports, or AXI bridges. Prefer the memory interfaces over ad hoc `SyncReadMem` wiring when the memory is part of a larger elastic design.

### Interfaces

```scala
val read = IO(new memory.ReadInterface(wAddr, wData))
val write = IO(new memory.WriteInterface(wAddr, wData))
```

Memory read interface:

```scala
read.req   // Source/Sink of UInt(wAddr.W), depending on direction
read.resp  // response data UInt(wData.W)
```

Memory write interface:

```scala
write.req.addr  // UInt(wAddr.W)
write.req.data  // UInt(wData.W)
write.req.strb  // UInt((wData / 8).W)
write.resp      // completion token
```

Use memory connect ops when both sides are memory interfaces:

```scala
import chext.memory.ConnectOp._

readMaster :=> readSlave
writeMaster :=> writeSlave
```

Rules:

- `wAddr` and `wData` must match when connecting memory interfaces.
- Treat `read.req`, `read.resp`, `write.req`, and `write.resp` as elastic streams.
- Buffer responses when needed to avoid ready/valid combinational loops.
- Use byte strobes for partial writes; full-beat writes can use all ones.

### Raw memories

```scala
val rawCfg = memory.RawMemConfig(
  wAddr = 10,
  wData = 256,
  latencyRead = 1,
  latencyWrite = 1
)

val ram0 = Module(new memory.RAM(
  rawMemCfg = rawCfg,
  portCfg = memory.PortConfig(numOutstandingRead = 4)
))
```

Raw-memory rules:

- Use `memory.RawMemConfig` for address width, data width, and read/write latency.
- Use `memory.PortConfig` for the elastic bridge behavior such as outstanding reads.
- Select the target backend explicitly when needed (`memory.chisel.Target`, vendor targets, or project-specific targets).
- Keep raw memory latency in the config and account for it through elastic bridges, not manual shift-register patches in parent logic.

### AXI bridges

Use AXI bridges when exposing a memory read/write interface to AXI or consuming AXI as memory traffic.

```scala
val bridge0 = Module(new memory.Axi4FullToReadWriteBridge(axiCfg))

bridge0.s_axi :=> s_axi
bridge0.read :=> readPort
bridge0.write :=> writePort
```

Rules:

- Full AXI bridge requires full AXI with both read and write enabled.
- AXI-Lite bridge is for register-like memory access and uses AXI-Lite channels.
- Address conversion is word-based: byte address is shifted by `log2Ceil(wData / 8)`.
- For burst traffic, the bridge uses address/strobe generation internally; do not duplicate that logic outside unless implementing a new primitive.

---

## 25. Floating Point API (`chext.float`)

Use `chext.float.FloatingPoint` as the Chisel type for floating point payloads, and use the elastic wrappers when floating point operations participate in elastic pipelines.

### Types

```scala
val genFp = float.FloatingPoint.ieee_fp32

val sourceA = IO(e.Source(genFp))
val sourceB = IO(e.Source(genFp))
val sinkOut = IO(e.Sink(genFp))
```

Available predefined types:

```scala
float.FloatingPoint.ieee_fp16
float.FloatingPoint.ieee_fp32
float.FloatingPoint.ieee_fp64
float.FloatingPoint.fp18
float.FloatingPoint.bfloat16
```

Rules:

- Store the chosen `FloatingPoint` generator in the parent config when it defines the module IO.
- Use `.zero` when a typed floating-point zero is needed.
- Do not treat the fields as raw IEEE bits unless you are intentionally implementing conversion or primitive arithmetic.

### Elastic add/multiply

```scala
val add0 = Module(new float.ElasticAdd(genFp))

sourceA :=> add0.sourceInA
sourceB :=> add0.sourceInB
add0.sinkOut :=> sinkOut
```

```scala
val multiply0 = Module(new float.ElasticMultiply(genFp))

sourceA :=> multiply0.sourceInA
sourceB :=> multiply0.sourceInB
multiply0.sinkOut :=> sinkOut
```

Rules:

- `ElasticAdd` joins `sourceInA` and `sourceInB`; both inputs must provide aligned operands.
- `ElasticMultiply` behaves similarly for multiplication.
- The wrapped operators may be combinational or pipelined; the wrapper preserves elastic backpressure using an internal output queue.
- Do not manually delay metadata next to floating point operators. Put metadata in the same elastic stream, or join/zip it through an explicitly buffered side stream.
- For non-elastic primitive use, instantiate `float.OpAdd` or `float.OpMultiply` directly and handle `delay` correctly.

---

## 26. Generic Module Template

```scala
case class ExampleConfig(
    axiCfg: a4.Config,
    wData: Int,
    depth: Int = 8,
    genUser: UInt = UInt(0.W)
) {
  require(wData > 0)
  require(depth > 0)
  require(axiCfg.read || axiCfg.write)

  val genPacket = new Packet(wData)

  val readCfg = stream.ReadConfig(
    axiCfg = axiCfg.copy(read = true, write = false, lite = false),
    genUser = genUser
  )

  val writeCfg = stream.WriteConfig(
    axiCfg = axiCfg.copy(read = false, write = true, lite = false),
    genUser = genUser
  )
}

class Packet(val wData: Int) extends Bundle {
  val data = UInt(wData.W)
  val sel = UInt(2.W)
  val last = Bool()
}

class Example(val cfg: ExampleConfig) extends Module {
  import cfg._

  val source = IO(e.Source(genPacket))
  val sink = IO(e.Sink(genPacket))

  private def implMain(): Unit = prefix("main") {
    val ewireTransformed = e.EWire(genPacket)
    val ewireSinks = Seq.fill(4)(e.EWire(genPacket))

    val transform0 = new e.Transform(source, ewireTransformed) {
      out := in
      out.data := in.data + 1.U
    }

    val demuxNs0 = new e.DemuxNs(ewireTransformed, ewireSinks) {
      select { in =>
        in.sel
      }
    }

    val arbiter0 = new e.ArbiterNs(
      ewireSinks,
      sink,
      e.Chooser.rr
    )
  }

  implMain()
}
```

---

## 27. Manual Interface Control

Avoid direct `$valid`, `$ready`, and `$bits` assignments unless implementing a primitive, wrapper, or non-elastic integration boundary. When you must manually control an elastic interface, mark the interface role explicitly.

### Consuming from a source-like interface

If code calls `source.deq()`, the interface must also be marked as a source. Initialize the non-dequeue path with `nodeq()` unless another component fully drives readiness.

```scala
source.nodeq()
source.markSource()

when(canConsume && source.$valid) {
  val bits = source.deq()
  // use bits
}
```

Rule:

- `source.deq()` requires `source.markSource()`.
- `source.nodeq()` is the normal default when readiness is conditionally asserted later.

### Producing into a sink-like interface

If code calls `sink.noenq()`, the interface must also be marked as a sink. Initialize the non-enqueue path with `noenq()` unless another component fully drives validity and bits.

```scala
sink.noenq()
sink.markSink()

when(canProduce) {
  sink.enq(payload)
}
```

Rule:

- `sink.noenq()` requires `sink.markSink()`.
- `sink.enq(...)` also belongs on a sink-marked interface.
- Do not mix manual `deq`/`enq` control with `:=>` or component ownership of the same interface. Exactly one owner should drive each interface.

## 28. Avoid

Avoid manual pass-through:

```scala
sink.$valid := source.$valid
source.$ready := sink.$ready
sink.$bits := source.$bits
```

Prefer:

```scala
val transform0 = new e.Transform(source, sink) {
  out := in
}
```

Avoid:

- `fork(in.x)`; use `fork { in.x }`.
- ambiguous join usage; keep joined values explicit.
- manual stream duplication.
- manual stream merging.
- hiding `ArbiterNs` when the no-select behavior matters.
- registers in `Transform`.
- unnecessary `Transducer`.
- missing `import e.ConnectOp._`.
- routing multi-beat packets without a `last` rule.
- calling `source.deq()` without `source.markSource()`.
- calling `sink.noenq()` without `sink.markSink()`.
- assigning `e.EWire(...)` or `e.EWire.like(...)` to a variable that does not start with `ewire`.

---

## 29. Decision Table

```text
Pure packet mapping                  => new e.Transform
One input, many outputs              => new e.Fork
Many aligned inputs, one output      => new e.Join or e.Zip
Selection from separate stream       => new e.Demux
Selection from current input token   => new e.DemuxNs
Many inputs, explicit select         => new e.Mux
Many inputs, arbitration policy, no selected-index output => new e.ArbiterNs or e.Arbiter(..., chooser)
Many inputs, arbitration policy, selected-index output    => new e.Arbiter(..., select, chooser)
Buffer existing interfaces           => new e.Queue(source, sink, ...)
Conditional blocking                 => new e.Stall
Conditional token filtering          => new e.Drop
Regular one-packet-to-N expansion    => new e.Repeat(..., wIndex = ...)
Stateful counted expansion           => new e.Count
Monotonic UInt stream generation     => new e.Counter
Stateful consume/produce             => new e.Transducer
One-shot initialization token        => new e.Once
Constant elastic source              => e.Const / new e.Const
Stream reduction                     => new e.Fold
Single in-flight scoped subgraph     => new e.Scope
Iterative state refinement           => new e.Loop
Merge mutually-exclusive sources     => new e.Merger
Shared elastic resources             => e.ShareD / e.ShareNd
AXI timing boundary                  => a4f.SlaveBuffer / a4f.MasterBuffer
AXI adaptation                       => ProtocolConverter
Single-beat memory load/store        => ldstr.Load / ldstr.Store
Burst stream read/write              => stream.Read / stream.Write
Memory-backed elastic interface      => chext.memory interfaces + bridges
Floating-point elastic arithmetic    => float.ElasticAdd / float.ElasticMultiply
```


---

## 30. Additional Elastic Components

### Once

Use `Once` when a hardware value must be emitted as a one-shot elastic token.

```scala
val ewireInit = e.Once(initValue)
ewireInit :=> sink
```

Or subclass it when the payload needs explicit assignment:

```scala
val once0 = new e.Once(sink) {
  out := initValue
}
```

Rules:

- `Once` emits exactly one token, then holds the sink invalid.
- The value passed to `e.Once(value)` must be hardware, not a Chisel type.
- Use it for initialization tokens and constants that should enter an elastic graph once.
- Do not use `Once` for a constant stream; build an explicit source or generator instead.

---


### Const

Use `Const` when a hardware value must be emitted as an always-available elastic token. Its API is similar to `Once`, but it keeps producing the value on every successful handshake instead of stopping after the first transfer.

```scala
val ewireConst = e.Const(constValue)
ewireConst :=> sink
```

Or subclass it when the payload needs explicit assignment:

```scala
val const0 = new e.Const(sink) {
  out := constValue
}
```

Rules:

- `Const` keeps its output valid and emits the configured payload on every sink handshake.
- The value passed to `e.Const(value)` must be hardware, not a Chisel type.
- Use `Const` for constant elastic streams, default side-channel values, and repeated configuration tokens.
- Use `Once` instead when the value should enter the elastic graph exactly one time.

---

### Fold

Use `Fold` for stream reductions where an initial value and a sequence of operands produce one result at each `last` boundary.

```scala
val fold0 = new e.Fold(source, sourceInit, sink) {
  operand { in =>
    in.data
  }

  last { in =>
    in.last
  }

  val join0 = new e.Join(sourceResult) {
    val acc = join(sinkB)
    val elem = join(sinkA)
    out := acc + elem
  }
}
```

Optional predicates:

```scala
first { in => in.first }
zero  { in => in.skip }
```

Rules:

- Always define exactly one `operand { ... }` or `operandExplicit { ... }`.
- Always define exactly one `last { ... }`.
- Use `first { ... }` when the input already carries group-start information; otherwise `Fold` internally tracks the first element.
- Use `zero { ... }` to skip sparse or irrelevant tokens without changing the accumulated value.
- Drive `sourceResult` with the fold operation, usually by joining `sinkB` as the accumulator and `sinkA` as the newest operand.
- Prefer `Fold` over `Transducer` for reductions; use `Transducer` only when the reduction has irregular consume/produce behavior.

---

### Scope

Use `Scope` to serialize an initialization token through a subgraph and wait for an exit token before accepting the next initialization token.

```scala
val scope0 = new e.Scope(sourceInit, sinkExit) {
  init { in =>
    started := true.B
  }

  exit { out =>
    finished := true.B
  }

  sinkBegin :=> inner.source
  inner.sink :=> sourceEnd
}
```

Rules:

- Use `sinkBegin` as the scoped begin stream and `sourceEnd` as the scoped completion stream.
- `init { ... }` runs when the initial token is accepted.
- `exit { ... }` runs when the completion token exits the scope.
- While a scope is active, the next `sourceInit` token is stalled.
- Use `Scope` when a subgraph must behave like a single in-flight transaction.

---

### Loop

Use `Loop` to repeatedly process a state token until an `end { ... }` predicate is true.

```scala
val loop0 = new e.Loop(sourceInit, sinkExit) {
  end { state =>
    state.done
  }

  val transform0 = new e.Transform(sinkCurrent, sourceNext) {
    out := in
    out.iter := in.iter + 1.U
    out.done := in.iter === limit
  }
}
```

Rules:

- Always define exactly one `end { state => ... }` predicate.
- Use `sinkCurrent` as the current loop-body input.
- Drive `sourceNext` with the next state from the loop body.
- Tokens for which `end` is already true bypass the loop body and exit.
- Tokens from `sourceNext` whose `end` becomes true exit; otherwise they recirculate to `sinkCurrent`.
- Use `Loop` for iterative state refinement; use `Repeat` for fixed expansion and `Fold` for reductions.

---

### Connect

Use `:=>` for ordinary elastic stream connections.

```scala
source :=> sink
```

Use `new e.Connect(source, sink)` only when you need a named component or a `fire { ... }` hook around an otherwise direct connection.

```scala
val connect0 = new e.Connect(source, sink) {
  out := in
  fire {
    accepted := true.B
  }
}
```

Rules:

- Prefer `source :=> sink` for simple same-type pass-through.
- Prefer `Transform` when the payload is changed without needing a fire hook.
- Do not manually write `$valid`, `$ready`, and `$bits` for ordinary pass-through.

---

### Share

Use `ShareD` / `ShareNd` when multiple clients share fewer identical elastic resources.

```scala
val share0 = Module(new e.ShareNd(
  e.ShareConfig(
    genIn = genReq,
    genOut = genResp,
    log2n = 4,
    log2k = 2,
    respQueueLength = 2,
    selQueueLength = 8
  )
) {
  protected def instantiate(
      index: Int,
      source: e.Interface[Req],
      sink: e.Interface[Resp]
  ): Unit = {
    resources(index).source :=> source
    sink :=> resources(index).sink
  }
})
```

Rules:

- `log2n` is the number of client bits; there are `1 << log2n` clients.
- `log2k` is the number of resource bits; there are `1 << log2k` resources.
- `ShareD` is deterministic grouping; `ShareNd` arbitrates within each group.
- Use response queues when requests and responses can otherwise create backpressure cycles.
- Prefer explicit arbitration/muxing when sharing policy or response routing is unusual.

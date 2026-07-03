package chext_template

import chisel3._
import chisel3.util._
import chisel3.experimental.prefix

import chext.{elastic => e}
import e.ConnectOp._

private class Example_TbTop extends Module with chext.TestBenchTop {
  override def desiredName: String = "Example_TbTop"

  val cfg = Example_Config(
    desiredName = Some("Example_Dut")
  )

  val dut = Module(new Example(cfg))

  val source = IO(e.Source(cfg.genPacket))
  val sink = IO(e.Sink(cfg.genPacket))

  source :=> dut.source
  dut.sink :=> sink
}

// manage: include test
object Example_Tb extends chext.TestBench {
  emit(new Example_TbTop)
}

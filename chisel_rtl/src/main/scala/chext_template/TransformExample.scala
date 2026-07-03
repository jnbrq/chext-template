package chext_template

import chisel3._
import chisel3.util._
import chisel3.experimental.prefix

import chext.{elastic => e}
import e.ConnectOp._

case class TransformExample_Config(
    val width: Int = 32,
    val desiredName: Option[String] = Option.empty
) {
  require(width > 0)

  val genPacket = new TransformExample_Packet(this)
}

class TransformExample_Packet(cfg: TransformExample_Config) extends Bundle {
  import cfg._

  val data = UInt(width.W)
}

class TransformExample(val cfg: TransformExample_Config) extends Module with chext.TestBenchTop {
  import cfg._

  override def desiredName: String =
    cfg.desiredName.getOrElse(super.desiredName)

  val source = IO(e.Source(genPacket))
  val sink = IO(e.Sink(genPacket))

  val transform0 = new e.Transform(source, sink) {
    out.data := in.data + 5.U
  }

  declareClock(clock)
  declareReset(reset)
  declareElasticInterface(source, "Input")
  declareElasticInterface(sink," Output")
}

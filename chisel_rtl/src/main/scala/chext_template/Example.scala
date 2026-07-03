package chext_template

import chisel3._
import chisel3.util._
import chisel3.experimental.prefix

import chext.{elastic => e}
import e.ConnectOp._

case class Example_Config(
    val width: Int = 32,
    val desiredName: Option[String] = Option.empty
) {
  require(width > 0)

  val genPacket = new Example_Packet(this)
}

class Example_Packet(cfg: Example_Config) extends Bundle {
  val data = UInt(cfg.width.W)
}

class Example(val cfg: Example_Config) extends Module {
  override def desiredName: String =
    cfg.desiredName.getOrElse(super.desiredName)

  val source = IO(e.Source(cfg.genPacket))
  val sink = IO(e.Sink(cfg.genPacket))

  val transform0 = new e.Transform(source, sink) {
    out := in
  }
}

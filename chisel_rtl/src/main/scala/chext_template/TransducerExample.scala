package chext_template

import chisel3._
import chisel3.util._
import chisel3.experimental.prefix

import chext.{elastic => e}
import e.ConnectOp._

case class TransducerExample_Config(
    val width: Int = 32,
    val desiredName: Option[String] = Option.empty
) {
  require(width > 0)

  val genInput = new TransducerExample_Input(this)
  val genOutput = UInt(width.W)
}

class TransducerExample_Input(cfg: TransducerExample_Config) extends Bundle {
  val data = UInt(cfg.width.W)
  val last = Bool()
}

class TransducerExample(val cfg: TransducerExample_Config) extends Module with chext.TestBenchTop {
  override def desiredName: String =
    cfg.desiredName.getOrElse(super.desiredName)

  import cfg._

  val source = IO(e.Source(genInput))
  val sink = IO(e.Sink(genOutput))

  val transducer0 = new e.Transducer(source, sink) {
    val regSum = RegInit(0.U(cfg.width.W))
    val wireSumNext = Mux(in.last, 0.U, regSum + in.data)

    out := wireSumNext

    packet {
      when(in.last) {
        accept { regSum := wireSumNext }
      }.otherwise {
        consume { regSum := wireSumNext }
      }
    }
  }

  declareClock(clock)
  declareReset(reset)
  declareElasticInterface(source, "Input")
  declareElasticInterface(sink, "Output")
}

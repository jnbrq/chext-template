package chext_template

// manage: include test
object TransducerExample_Tb extends chext.TestBench {
  emit(new TransducerExample(TransducerExample_Config()))
}

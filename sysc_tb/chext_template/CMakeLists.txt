# BEGIN MANAGED TESTBENCHES
generate_tb(
    TARGET_NAME chext_template.TransducerExample.tb
    CPP_SOURCES src/TransducerExample.tb.cpp
    HDL_DIR hdl
    HDL_MODULES TransducerExample
    VERILATOR_ARGS
        "--trace"
    CPP_DEFS
        VERILATED_TRACE_ENABLED
)

generate_tb(
    TARGET_NAME chext_template.TransformExample.tb
    CPP_SOURCES src/TransformExample.tb.cpp
    HDL_DIR hdl
    HDL_MODULES TransformExample
    VERILATOR_ARGS
        "--trace"
    CPP_DEFS
        VERILATED_TRACE_ENABLED
)
# END MANAGED TESTBENCHES

// BEGIN MANAGED HDL INCLUDES
#include <TransformExample.hpp>
// END MANAGED HDL INCLUDES

#include <systemc>

#include <chext_test/chext_test.hpp>

using namespace sc_core;
using namespace sc_dt;
using namespace chext_test;

struct TestBench : TestBenchBase {
    SC_HAS_PROCESS(TestBench);

    TestBench(sc_module_name name)
        : TestBenchBase(name)
        , clock_("clock", 10, SC_NS)
        , reset_("reset")
        , dut("dut") {
        dut.clock(clock_);
        dut.reset(reset_);
    }

protected:
    void entry() override {
        reset();

        wait(10, SC_NS);
        finish();
    }

    void reset() {
        wait(clock_.negedge_event());
        reset_.write(true);

        wait(clock_.negedge_event());
        wait(clock_.negedge_event());

        reset_.write(false);

        wait(clock_.negedge_event());
    }

    sc_clock clock_;
    sc_signal<bool> reset_;
    TransformExample dut;
};

int sc_main(int argc, char** argv) {
    TestBench tb("tb");
    sc_start();
    return 0;
}

module chext_syncmem_1w1r #(
    parameter COUNT = 16,
    parameter ADDR_WIDTH = 4,
    parameter DATA_WIDTH = 16
) (
    input clock,

    // Port A
    input [ADDR_WIDTH-1:0] addrA,
    input writeEnA,
    input [DATA_WIDTH-1:0] dataInA,

    // Port B
    input [ADDR_WIDTH-1:0] addrB,
    output reg [DATA_WIDTH-1:0] dataOutB
);
  reg [DATA_WIDTH-1:0] ram[COUNT-1:0];

  always_ff @(posedge clock) begin
    if (writeEnA) ram[addrA] <= dataInA;
  end

  always_ff @(posedge clock) begin
    dataOutB <= ram[addrB];
  end

endmodule

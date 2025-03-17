from amaranth import *
from amaranth.sim import Simulator, Period
# Import our UART receiver
from uart_receiver import UARTReceiver

# Create our device under test
dut = UARTReceiver(divisor=4)  # Small divisor for faster simulation

async def uart_tx(ctx, byte, divisor):
    """Helper function to transmit a byte over UART."""
    ctx.set(dut.i, 1)  # Idle high
    await ctx.tick()
    
    # Start bit (low)
    ctx.set(dut.i, 0)
    for _ in range(divisor):
        await ctx.tick()
    
    # 8 data bits, LSB first
    for i in range(8):
        bit = (byte >> i) & 1
        ctx.set(dut.i, bit)
        for _ in range(divisor):
            await ctx.tick()
    
    # Stop bit (high)
    ctx.set(dut.i, 1)
    for _ in range(divisor):
        await ctx.tick()
        
async def test_bench(ctx):
    # Initialize signals
    ctx.set(dut.i, 1)    # Idle high
    ctx.set(dut.ack, 0)  # No acknowledgment
    
    # Wait a few cycles
    for _ in range(10):
        await ctx.tick()
    
    # Send byte 0xA5 (10100101)
    await uart_tx(ctx, 0xA5, dut.divisor)
    
    # Wait for ready signal
    for _ in range(10):
        await ctx.tick()
        if ctx.get(dut.rdy):
            break
    
    # Verify received data
    assert ctx.get(dut.rdy), "Ready signal not asserted"
    assert ctx.get(dut.data) == 0xA5, f"Wrong data: {ctx.get(dut.data):02x} (expected 0xA5)"
    
    # Acknowledge reception
    ctx.set(dut.ack, 1)
    await ctx.tick()
    ctx.set(dut.ack, 0)
    
    # Send another byte with a framing error (no stop bit)
    ctx.set(dut.i, 1)  # Idle high
    await ctx.tick()
    
    # Start bit
    ctx.set(dut.i, 0)
    for _ in range(dut.divisor):
        await ctx.tick()
    
    # 8 data bits, all 1s
    for _ in range(8):
        ctx.set(dut.i, 1)
        for _ in range(dut.divisor):
            await ctx.tick()
    
    # Incorrect stop bit (should be 1, sending 0)
    ctx.set(dut.i, 0)
    for _ in range(dut.divisor):
        await ctx.tick()
    
    # Wait a bit and check error flag
    for _ in range(10):
        await ctx.tick()
    
    assert ctx.get(dut.err), "Error flag not asserted on framing error"

# Set up the simulator
sim = Simulator(dut)
sim.add_clock(Period(MHz=1))
sim.add_testbench(test_bench)

# Run simulation
with sim.write_vcd("uart_sim.vcd", "uart_sim.gtkw"):
    sim.run()

print("Simulation complete. View the waveform with 'gtkwave uart_sim.vcd'")
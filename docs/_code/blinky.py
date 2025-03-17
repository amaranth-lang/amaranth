from amaranth import *

class Blinky(Elaboratable):
    def __init__(self):
        # No parameters needed for this simple example
        pass
        
    def elaborate(self, platform):
        # The 'elaborate' method transforms our Python description into a hardware circuit
        
        # Get the LED from the platform (if running on actual hardware)
        if platform is not None:
            led = platform.request("led", 0)
        else:
            # For simulation, create a dummy LED signal
            led = Signal()
        
        # Create a timer (24-bit counter)
        # This will count from 0 to 2^24-1 and then wrap around
        timer = Signal(24)
        
        m = Module()
        
        # Increment timer every clock cycle
        # 'd.sync' means this happens on the rising edge of the clock
        m.d.sync += timer.eq(timer + 1)
        
        # Connect LED to the most significant bit of the timer
        # timer[-1] means "the last bit" (most significant bit)
        # This makes the LED toggle on/off when the timer overflows
        m.d.comb += led.o.eq(timer[-1])
        
        return m

# This lets us run this file directly or include it in other scripts
if __name__ == "__main__":
    from amaranth.sim import Simulator, Period
    
    # Create our circuit
    dut = Blinky()
    
    # Set up a simple simulation to watch the LED blink
    sim = Simulator(dut)
    sim.add_clock(Period(MHz=1))  # 1 MHz clock (1μs period)
    
    # Run simulation and generate a waveform file
    with sim.write_vcd("blinky.vcd"):
        sim.run_until(100 * 1_000_000)  # Run for 100ms of simulated time

# How to run: pdm run python blinky.py
# This will generate blinky.vcd, which you can view with GTKWave
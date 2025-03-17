# Amaranth HDL Tutorial for Beginners

This tutorial will guide you through using Amaranth HDL, starting with simple circuits and progressing to more complex designs.

## 1. Introduction to Amaranth HDL

Amaranth is a Python-based hardware description language (HDL) that allows you to design digital circuits using Python's object-oriented features. It provides a more modern and productive alternative to traditional HDLs like Verilog or VHDL.

### What is HDL?

A Hardware Description Language is a specialized programming language used to describe the structure and behavior of electronic circuits. Unlike software programming, HDL code describes actual physical hardware structures that will be created on an FPGA or ASIC.

### Why Amaranth?

- **Python-based** - Use a familiar language with modern features
- **Object-oriented** - Create reusable components
- **Built-in testing** - Simulate designs without external tools
- **Powerful abstractions** - Simplify common hardware patterns

## 2. Setting Up

### Prerequisites

Before starting, you'll need:
- Python 3.9 or newer installed
- Basic knowledge of Python
- For synthesis to hardware: Yosys (optional, installed automatically with PDM)

### Installation

Install Amaranth using PDM (Python Development Master), which will handle creating a virtual environment for you:

```bash
# Install PDM if you don't have it
pip install pdm

# Clone the repository and navigate to it
git clone https://github.com/amaranth-lang/amaranth.git
cd amaranth

# Install Amaranth and its dependencies in a virtual environment
pdm install
```

To run Amaranth scripts, use PDM to ensure your code runs in the correct environment:

```bash
pdm run python your_script.py
```

## 3. Understanding Digital Logic Basics

### Signals

Signals are the fundamental elements in digital circuits - they represent wires carrying data.

```python
from amaranth import *

# Create a module (a container for your circuit)
m = Module()

# Create signals (these represent wires in your circuit)
a = Signal()       # 1-bit signal (can be 0 or 1)
b = Signal(8)      # 8-bit signal (can be 0-255)
c = Signal(8, init=42)  # 8-bit signal with initial value 42

# Connect signals (using combinational logic)
m.d.comb += c.eq(b + 1)  # c will always equal b + 1
```

### Clock Domains

Digital circuits operate based on clock signals. Amaranth uses clock domains to organize logic:

- **Combinational domain (`m.d.comb`)**: Logic that responds immediately to input changes
- **Synchronous domain (`m.d.sync`)**: Logic that updates only on clock edges

```python
# Combinational assignment (happens continuously)
m.d.comb += output.eq(input_a & input_b)  # output = input_a AND input_b

# Synchronous assignment (happens only on clock edges)
m.d.sync += counter.eq(counter + 1)  # counter increments each clock cycle
```

### Basic Example: AND Gate

Let's create a simple AND gate and save it as `and_gate.py`:

```python
from amaranth import *
from amaranth.back import verilog

class AndGate(Elaboratable):
    def __init__(self):
        # Input ports
        self.a = Signal()
        self.b = Signal()
        # Output port
        self.y = Signal()
        
    def elaborate(self, platform):
        # The 'elaborate' method builds the actual circuit
        m = Module()
        # y = a AND b
        m.d.comb += self.y.eq(self.a & self.b)
        return m

# Create the gate
gate = AndGate()

# Generate Verilog (for viewing or using with other tools)
with open("and_gate.v", "w") as f:
    f.write(verilog.convert(gate, ports=[gate.a, gate.b, gate.y]))

# How to run: pdm run python and_gate.py
# This will generate and_gate.v
```

Viewing the generated Verilog (`and_gate.v`) shows what hardware will be created:

```verilog
module top(a, b, y);
    input a;
    input b;
    output y;
    assign y = (a & b);
endmodule
```

## 4. Your First Circuit: LED Blinker

Now let's create a more practical circuit that blinks an LED. Save this as `blinky.py`:

```python
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
```

### Understanding the Code

- **Elaboratable**: Base class for all Amaranth circuits
- **elaborate(self, platform)**: Method that builds the actual circuit
- **Signal(24)**: Creates a 24-bit counter that can count from 0 to 2^24-1
- **m.d.sync += timer.eq(timer + 1)**: Increments the timer on each clock edge
- **timer[-1]**: Accesses the most significant bit (bit 23) of the timer
- **led.o.eq()**: Connects the output pin of the LED to our signal

### Running on Hardware

To run on actual FPGA hardware, you'd need to specify a platform and call the build method:

```python
# Example for specific hardware (requires amaranth-boards package)
from amaranth_boards.icestick import ICEStickPlatform

if __name__ == "__main__":
    platform = ICEStickPlatform()
    platform.build(Blinky(), do_program=True)
```

### Viewing Simulation Results

The simulation generates a VCD (Value Change Dump) file that you can view with waveform viewer software:

1. Install GTKWave: [http://gtkwave.sourceforge.net/](http://gtkwave.sourceforge.net/)
2. Open the generated VCD file: `gtkwave blinky.vcd`
3. Select signals to view in the waveform

## 5. Components with Interfaces: Up Counter

Now let's create a reusable component with a well-defined interface:

```python
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

class UpCounter(wiring.Component):
    """
    A 16-bit counter with enable input and overflow output.
    
    Inputs:
        en - Enable signal (1 bit)
    
    Outputs:
        ovf - Overflow signal (1 bit), high when count reaches limit
    
    Parameters:
        limit - The value at which the counter will reset to 0
    """
    
    # Define the interface using Python's type annotations
    # but with Amaranth-specific In/Out types
    en: In(1)   # Enable input, 1 bit
    ovf: Out(1) # Overflow output, 1 bit
    
    def __init__(self, limit):
        # Store parameters first
        self.limit = limit
        # Create internal signals
        self.count = Signal(16)
        # Call parent constructor AFTER defining internal signals
        # but BEFORE accessing interface signals
        super().__init__()
        
    def elaborate(self, platform):
        m = Module()
        
        # Set overflow signal when count reaches limit (combinational logic)
        m.d.comb += self.ovf.eq(self.count == self.limit)
        
        # Logic for counting (sequential logic)
        with m.If(self.en):  # Only count when enabled
            with m.If(self.ovf):  # If we've reached the limit
                m.d.sync += self.count.eq(0)  # Reset to 0
            with m.Else():  # Otherwise
                m.d.sync += self.count.eq(self.count + 1)  # Increment
                
        return m

# Example usage
if __name__ == "__main__":
    from amaranth.back import verilog
    
    # Create a counter that overflows at 9999
    counter = UpCounter(9999)
    
    # Generate Verilog
    with open("counter.v", "w") as f:
        f.write(verilog.convert(counter))
    
    print("Generated counter.v")

# How to run: pdm run python up_counter.py
```

### Understanding Component Interfaces

The `wiring.Component` base class provides a structured way to define interfaces:

- `In(width)` and `Out(width)` define input and output ports
- Type annotations (using Python's standard syntax) define the interface
- `super().__init__()` must be called after defining internal signals

## 6. Simulating Your Design

Amaranth has a built-in simulator that allows you to test your designs:

```python
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.sim import Simulator, Period

# Use the UpCounter from the previous example
class UpCounter(wiring.Component):
    en: In(1)
    ovf: Out(1)
    
    def __init__(self, limit):
        self.limit = limit
        self.count = Signal(16)
        super().__init__()
        
    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.ovf.eq(self.count == self.limit)
        with m.If(self.en):
            with m.If(self.ovf):
                m.d.sync += self.count.eq(0)
            with m.Else():
                m.d.sync += self.count.eq(self.count + 1)
        return m

# Create our design with a limit of 25
dut = UpCounter(25)  # DUT = Device Under Test

# Define a test scenario
# This is an async function because simulation is event-driven
async def test_bench(ctx):
    # Test with enable off
    ctx.set(dut.en, 0)  # Set enable to 0
    
    # Run for 10 clock cycles and check overflow never happens
    for _ in range(10):
        await ctx.tick()  # Wait for one clock cycle
        assert not ctx.get(dut.ovf)  # Check that overflow is not asserted
    
    # Test with enable on
    ctx.set(dut.en, 1)  # Set enable to 1
    
    # Run for 30 clock cycles and check behavior
    for i in range(30):
        # Print counter value (for debugging)
        print(f"Cycle {i}: count = {ctx.get(dut.count)}, ovf = {ctx.get(dut.ovf)}")
        
        await ctx.tick()  # Wait for one clock cycle
        
        # On cycle 24, counter should be 25 and overflow should be high
        if i == 24:
            assert ctx.get(dut.ovf), f"Overflow not asserted at count={ctx.get(dut.count)}"
        # On cycle 25, counter should be 0 and overflow should be low
        elif i == 25:
            assert not ctx.get(dut.ovf), f"Overflow still asserted at count={ctx.get(dut.count)}"
            assert ctx.get(dut.count) == 0, f"Counter did not reset, count={ctx.get(dut.count)}"

# Set up the simulator
sim = Simulator(dut)
sim.add_clock(Period(MHz=1))  # 1 MHz clock (1μs period)
sim.add_testbench(test_bench)  # Add our test scenario

# Run simulation and generate waveform
with sim.write_vcd("counter_sim.vcd", "counter_sim.gtkw"):
    sim.run()

print("Simulation complete. View the waveform with 'gtkwave counter_sim.vcd'")

# How to run: pdm run python counter_sim.py
```

### Understanding the Simulation

- **ctx.set(signal, value)**: Sets a signal to a specific value
- **ctx.get(signal)**: Gets the current value of a signal
- **await ctx.tick()**: Advances simulation by one clock cycle
- **sim.add_clock(Period(MHz=1))**: Adds a 1MHz clock to the simulation
- **sim.write_vcd("file.vcd")**: Generates a waveform file for visualization

### Viewing Waveforms

The VCD file contains all signal changes during simulation. To view it:

1. Install GTKWave: [http://gtkwave.sourceforge.net/](http://gtkwave.sourceforge.net/)
2. Open the VCD file: `gtkwave counter_sim.vcd`
3. In GTKWave, select signals in the left panel and add them to the waveform view

## 7. Finite State Machines: UART Receiver

Now let's implement something more complex - a UART receiver using a Finite State Machine:

```python
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

class UARTReceiver(wiring.Component):
    """
    A UART (serial) receiver that converts serial data to parallel.
    
    UART uses start and stop bits to frame each byte:
    - Line is high when idle
    - Start bit is low (0)
    - 8 data bits follow
    - Stop bit is high (1)
    
    Parameters:
        divisor - Clock divisor for baud rate (system_clock / baud_rate)
                  Example: 100MHz system clock, 9600 baud → divisor = 10,417
    
    Inputs:
        i   - Serial input line
        ack - Acknowledgment (read the received byte)
    
    Outputs:
        data - 8-bit received data
        rdy  - Data ready flag (high when byte received)
        err  - Error flag (high on framing error)
    """
    
    # Interface
    i: In(1)     # Input bit (serial line)
    data: Out(8) # Received byte (parallel output)
    rdy: Out(1)  # Data ready flag
    ack: In(1)   # Acknowledgment
    err: Out(1)  # Error flag
    
    def __init__(self, divisor):
        super().__init__()
        self.divisor = divisor  # Clock divisor for baud rate
        
    def elaborate(self, platform):
        m = Module()
        
        # Baud rate generator
        # This creates a "strobe" (stb) that pulses once per bit period
        ctr = Signal(range(self.divisor))  # Counter for clock division
        stb = Signal()  # Strobe signal (pulses when we should sample)
        
        # When counter reaches zero, reset it and pulse the strobe
        with m.If(ctr == 0):
            m.d.sync += ctr.eq(self.divisor - 1)  # Reset counter
            m.d.comb += stb.eq(1)  # Pulse strobe
        with m.Else():
            m.d.sync += ctr.eq(ctr - 1)  # Decrement counter
            
        # Bit counter (counts 8 data bits)
        bit = Signal(3)  # 3 bits to count 0-7
        
        # FSM (Finite State Machine) for UART reception
        with m.FSM() as fsm:
            # Initial state: wait for start bit
            with m.State("START"):
                with m.If(~self.i):  # If input goes low (start bit detected)
                    m.next = "DATA"  # Move to DATA state
                    m.d.sync += [
                        # Sample in middle of bit by setting counter to half divisor
                        ctr.eq(self.divisor // 2),
                        # Prepare to receive 8 bits (bit 7 down to bit 0)
                        bit.eq(7),
                    ]
                    
            # Receiving data bits
            with m.State("DATA"):
                with m.If(stb):  # On each baud strobe (sampling point)
                    m.d.sync += [
                        bit.eq(bit - 1),  # Decrement bit counter
                        # Cat() concatenates bits - this shifts received bit into the data
                        self.data.eq(Cat(self.i, self.data[:-1])),
                    ]
                    with m.If(bit == 0):  # If all bits received
                        m.next = "STOP"  # Move to STOP state
                        
            # Check stop bit
            with m.State("STOP"):
                with m.If(stb):  # On baud strobe
                    with m.If(self.i):  # If input is high (valid stop bit)
                        m.next = "DONE"  # Move to DONE state
                    with m.Else():  # If input is low (invalid stop bit)
                        m.next = "ERROR"  # Move to ERROR state
                        
            # Data ready - wait for acknowledgment
            with m.State("DONE"):
                m.d.comb += self.rdy.eq(1)  # Set ready flag
                with m.If(self.ack):  # When acknowledged
                    m.next = "START"  # Go back to START for next byte
                    
            # Error state - stay here until reset
            # fsm.ongoing() checks if FSM is in a specific state
            m.d.comb += self.err.eq(fsm.ongoing("ERROR"))
            with m.State("ERROR"):
                pass  # Do nothing (stay in error state)
                
        return m

# Example usage
if __name__ == "__main__":
    from amaranth.back import verilog
    
    # Create a UART receiver for 9600 baud with a 1MHz clock
    uart = UARTReceiver(divisor=104)  # 1,000,000 / 9600 ≈ 104
    
    # Generate Verilog
    with open("uart_rx.v", "w") as f:
        f.write(verilog.convert(uart))
    
    print("Generated uart_rx.v")

# How to run: pdm run python uart_receiver.py
```

### Understanding FSMs in Amaranth

- **with m.FSM() as fsm**: Creates a finite state machine
- **with m.State("NAME")**: Defines a state
- **m.next = "STATE"**: Sets the next state
- **fsm.ongoing("STATE")**: Checks if the FSM is in a specific state
- **Cat(bit, data)**: Concatenates bits (used for shifting)

## 8. Simulating the UART Receiver

Let's create a simulation to test our UART receiver:

```python
from amaranth import *
from amaranth.sim import Simulator, Period
# Import our UART receiver (assuming it's in uart_receiver.py)
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

# How to run: pdm run python uart_sim.py
```

## 9. Building a Complete System

Now let's build a system combining multiple components - a blinker that uses our counter:

```python
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

# Import our UpCounter (assuming it's defined in a file called up_counter.py)
from up_counter import UpCounter

class ControlledBlinker(Elaboratable):
    """
    An LED blinker that uses a counter to control blink rate.
    """
    def __init__(self, freq_hz=1):
        """
        Create a blinker with specified frequency.
        
        Args:
            freq_hz: Blink frequency in Hz (defaults to 1Hz)
        """
        self.freq_hz = freq_hz
        
    def elaborate(self, platform):
        m = Module()
        
        # Get system clock frequency (for actual hardware)
        if platform is not None:
            sys_clock_freq = platform.default_clk_frequency
        else:
            # For simulation, assume 1MHz clock
            sys_clock_freq = 1_000_000
        
        # Calculate counter limit based on desired blink frequency
        # The counter will overflow twice per cycle (on-off)
        counter_limit = int(sys_clock_freq / (2 * self.freq_hz)) - 1
        
        # Create our counter submodule
        counter = UpCounter(counter_limit)
        # Add it to our module with a name
        m.submodules.counter = counter
        
        # Create a toggle flip-flop for LED state
        led_state = Signal(1)
        
        # Always enable the counter
        m.d.comb += counter.en.eq(1)
        
        # Toggle LED state on overflow
        with m.If(counter.ovf):
            m.d.sync += led_state.eq(~led_state)
            
        # Connect to the LED if running on hardware
        if platform is not None:
            led = platform.request("led", 0)
            m.d.comb += led.o.eq(led_state)
        
        return m

# Example usage
if __name__ == "__main__":
    from amaranth.sim import Simulator, Period
    
    # Create a 2Hz blinker
    dut = ControlledBlinker(freq_hz=2)
    
    # Basic simulation to observe blinking
    sim = Simulator(dut)
    sim.add_clock(Period(MHz=1))  # 1MHz system clock
    
    # Add a simple test to just run for a while
    def test_bench():
        pass
    
    sim.add_process(test_bench)
    
    # Run for 2 seconds (enough to see multiple blinks at 2Hz)
    with sim.write_vcd("blinker_system.vcd", "blinker_system.gtkw"):
        sim.run_until(2_000_000)  # 2M ns = 2 seconds
        
    print("Simulation complete. View waveform with 'gtkwave blinker_system.vcd'")
    
    # Generate Verilog
    from amaranth.back import verilog
    
    with open("blinker_system.v", "w") as f:
        f.write(verilog.convert(dut))
    
    print("Generated blinker_system.v")

# How to run: pdm run python controlled_blinker.py
```

### Understanding The System Architecture

- **Submodules**: `m.submodules.name = module` adds a submodule to your design
- **Clock Frequency**: Real hardware platforms provide clock frequency info
- **Platform Interface**: `platform.request()` gets hardware I/O pins
- **Hierarchical Design**: Components can contain other components

## 10. Running on Real Hardware

To run your design on actual FPGA hardware, you need:

1. An FPGA board
2. The appropriate platform package (e.g., `amaranth-boards`)
3. A top-level module that interfaces with the hardware

Here's an example for an iCEStick FPGA board:

```python
from amaranth import *
from amaranth_boards.icestick import ICEStickPlatform
from controlled_blinker import ControlledBlinker

# Create a platform for the iCEStick board
platform = ICEStickPlatform()

# Create a 1Hz blinker (adjust frequency as needed)
blinker = ControlledBlinker(freq_hz=1)

# Build and program
platform.build(blinker, do_program=True)

# How to run: pdm run python program_icestick.py
```

### For Other Boards

The process is similar for other boards:

1. Import the appropriate platform
2. Create an instance of your top-level module
3. Call `platform.build(module, do_program=True)`

## 11. Troubleshooting and Common Errors

### TypeErrors or AttributeErrors

```
TypeError: Cannot assign to non-Value
```
- Likely tried to assign to a Python variable instead of a Signal
- Always use `.eq()` for hardware assignments, not Python `=`

```
AttributeError: 'Module' object has no attribute 'domain'
```
- You probably wrote `m.domain.sync` instead of `m.d.sync`

### Runtime or Logic Errors

```
RuntimeError: Cannot add synchronous assignments: no sync domain is currently active
```
- You need to define a clock domain
- For simulation, add `sim.add_clock(Period(MHz=1))`

```
Signal has no timeline
```
- Signal is not being driven or used in the design
- Check for typos or unused signals

### Hardware Deployment Errors

```
OSError: Toolchain binary not found in PATH
```
- The required synthesis tools (like Yosys) are not installed or not in PATH
- Install the required tools or add them to PATH

## 12. Next Steps

This tutorial has covered the basics of Amaranth HDL. To continue learning:

1. **Advanced Components**: Explore memory components in `amaranth.lib.memory`
2. **Stream Processing**: Learn about streaming interfaces in `amaranth.lib.stream`
3. **Clock Domain Crossing**: Study techniques in `amaranth.lib.cdc`
4. **Hardware Platforms**: Experiment with FPGA boards using `amaranth-boards`
5. **Community Resources**:
   - GitHub: [https://github.com/amaranth-lang/amaranth](https://github.com/amaranth-lang/amaranth)
   - Documentation: [https://amaranth-lang.org/docs/](https://amaranth-lang.org/docs/)

## 13. Glossary of Terms

- **HDL**: Hardware Description Language - used to describe electronic circuits
- **FPGA**: Field-Programmable Gate Array - reconfigurable hardware
- **Combinational Logic**: Logic where outputs depend only on current inputs
- **Sequential Logic**: Logic where outputs depend on current inputs and state
- **Clock Domain**: Group of logic synchronized to the same clock
- **Elaboration**: Process of transforming Python code into a hardware netlist
- **Simulation**: Testing hardware designs in software before physical implementation
- **Synthesis**: Process of transforming a hardware design into physical gates
- **VCD**: Value Change Dump - file format for recording signal changes in simulation

Happy hardware designing with Amaranth HDL!
Tutorial
========

This tutorial will guide you through using Amaranth HDL, starting with simple circuits and progressing to more complex designs.

Introduction to Amaranth HDL
----------------------------

Amaranth is a Python-based hardware description language (HDL) that allows you to design digital circuits using Python's object-oriented features. It provides a more modern and productive alternative to traditional HDLs like Verilog or VHDL.

What is HDL?
~~~~~~~~~~~~

A Hardware Description Language is a specialized programming language used to describe the structure and behavior of electronic circuits. Unlike software programming, HDL code describes actual physical hardware structures that will be created on an FPGA or ASIC.

Why Amaranth?
~~~~~~~~~~~~~

- **Python-based** - Use a familiar language with modern features

----------------------------------------------------------------- **Object-oriented** - Create reusable components
------------------------------------------------- **Built-in testing** - Simulate designs without external tools
--------------------------------------------------------------- **Powerful abstractions** - Simplify common hardware patterns

Setting Up
----------

Prerequisites
~~~~~~~~~~~~~

Before starting, you'll need:

- Python 3.9 or newer installed

------------------------------- Basic knowledge of Python
-------------------------- For synthesis to hardware: Yosys (optional, installed automatically with PDM)

Installation
~~~~~~~~~~~~

Install Amaranth using PDM (Python Development Master), which will handle creating a virtual environment for you:

.. code-block:: bash

   # Install PDM if you don't have it
   pip install pdm

   # Clone the repository and navigate to it
   git clone https://github.com/amaranth-lang/amaranth.git
   cd amaranth

   # Install Amaranth and its dependencies in a virtual environment
   pdm install

To run Amaranth scripts, use PDM to ensure your code runs in the correct environment:

.. code-block:: bash

   pdm run python your_script.py

Understanding Digital Logic Basics
----------------------------------

Signals
~~~~~~~

Signals are the fundamental elements in digital circuits - they represent wires carrying data.

.. code-block:: python

   from amaranth import *

   # Create a module (a container for your circuit)
   m = Module()

   # Create signals (these represent wires in your circuit)
   a = Signal()       # 1-bit signal (can be 0 or 1)
   b = Signal(8)      # 8-bit signal (can be 0-255)
   c = Signal(8, init=42)  # 8-bit signal with initial value 42

   # Connect signals (using combinational logic)
   m.d.comb += c.eq(b + 1)  # c will always equal b + 1

Clock Domains
~~~~~~~~~~~~~

Digital circuits operate based on clock signals. Amaranth uses clock domains to organize logic:

- **Combinational domain** (``m.d.comb``): Logic that responds immediately to input changes

------------------------------------------------------------------------------------------- **Synchronous domain** (``m.d.sync``): Logic that updates only on clock edges

.. code-block:: python

   # Combinational assignment (happens continuously)
   m.d.comb += output.eq(input_a & input_b)  # output = input_a AND input_b

   # Synchronous assignment (happens only on clock edges)
   m.d.sync += counter.eq(counter + 1)  # counter increments each clock cycle

Basic Example: AND Gate
~~~~~~~~~~~~~~~~~~~~~~~

Let's create a simple AND gate:

.. literalinclude:: _code/and_gate.py
   :caption: and_gate.py
   :linenos:

Viewing the generated Verilog (``and_gate.v``) shows what hardware will be created:

.. code-block:: verilog

   module top(a, b, y);
       input a;
       input b;
       output y;
       assign y = (a & b);
   endmodule

Your First Circuit: LED Blinker
-------------------------------

Now let's create a more practical circuit that blinks an LED:

.. literalinclude:: _code/blinky.py
   :caption: blinky.py
   :linenos:

Understanding the Code
~~~~~~~~~~~~~~~~~~~~~~

- **Elaboratable**: Base class for all Amaranth circuits

-------------------------------------------------------- **elaborate(self, platform)**: Method that builds the actual circuit
--------------------------------------------------------------------- **Signal(24)**: Creates a 24-bit counter that can count from 0 to 2^24-1
------------------------------------------------------------------------- **m.d.sync += timer.eq(timer + 1)**: Increments the timer on each clock edge
----------------------------------------------------------------------------- **timer[-1]**: Accesses the most significant bit (bit 23) of the timer
----------------------------------------------------------------------- **led.o.eq()**: Connects the output pin of the LED to our signal

Running on Hardware
~~~~~~~~~~~~~~~~~~~

To run on actual FPGA hardware, you'd need to specify a platform and call the build method:

.. code-block:: python

   # Example for specific hardware (requires amaranth-boards package)
   from amaranth_boards.icestick import ICEStickPlatform

   if __name__ == "__main__":
       platform = ICEStickPlatform()
       platform.build(Blinky(), do_program=True)

Viewing Simulation Results
~~~~~~~~~~~~~~~~~~~~~~~~~~

The simulation generates a VCD (Value Change Dump) file that you can view with waveform viewer software:

1. Install GTKWave: http://gtkwave.sourceforge.net/
2. Open the generated VCD file: ``gtkwave blinky.vcd``
3. Select signals to view in the waveform

Components with Interfaces: Up Counter
--------------------------------------

Now let's create a reusable component with a well-defined interface:

.. literalinclude:: _code/up_counter.py
   :caption: up_counter.py
   :linenos:
   :end-before: # --- TEST ---

Understanding Component Interfaces
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``wiring.Component`` base class provides a structured way to define interfaces:

- ``In(width)`` and ``Out(width)`` define input and output ports

---------------------------------------------------------------- Type annotations (using Python's standard syntax) define the interface
----------------------------------------------------------------------- ``super().__init__()`` must be called after defining internal signals

Simulating Your Design
----------------------

Amaranth has a built-in simulator that allows you to test your designs:

.. literalinclude:: _code/up_counter.py
   :caption: up_counter_sim.py
   :linenos:
   :lines: 46-74

Understanding the Simulation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **ctx.set(signal, value)**: Sets a signal to a specific value

--------------------------------------------------------------- **ctx.get(signal)**: Gets the current value of a signal
-------------------------------------------------------- **await ctx.tick()**: Advances simulation by one clock cycle
------------------------------------------------------------- **sim.add_clock(Period(MHz=1))**: Adds a 1MHz clock to the simulation
---------------------------------------------------------------------- **sim.write_vcd("file.vcd")**: Generates a waveform file for visualization

Viewing Waveforms
~~~~~~~~~~~~~~~~~

The VCD file contains all signal changes during simulation. To view it:

1. Install GTKWave: http://gtkwave.sourceforge.net/
2. Open the VCD file: ``gtkwave counter_sim.vcd``
3. In GTKWave, select signals in the left panel and add them to the waveform view

Finite State Machines: UART Receiver
------------------------------------

Now let's implement something more complex - a UART receiver using a Finite State Machine:

.. literalinclude:: _code/uart_receiver.py
   :caption: uart_receiver.py
   :linenos:

Understanding FSMs in Amaranth
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **with m.FSM() as fsm**: Creates a finite state machine

--------------------------------------------------------- **with m.State("NAME")**: Defines a state
------------------------------------------ **m.next = "STATE"**: Sets the next state
------------------------------------------ **fsm.ongoing("STATE")**: Checks if the FSM is in a specific state
------------------------------------------------------------------- **Cat(bit, data)**: Concatenates bits (used for shifting)

Simulating the UART Receiver
----------------------------

Let's create a simulation to test our UART receiver:

.. literalinclude:: _code/uart_sim.py
   :caption: uart_sim.py
   :linenos:

Building a Complete System
--------------------------

Now let's build a system combining multiple components - a blinker that uses our counter:

.. literalinclude:: _code/controlled_blinker.py
   :caption: controlled_blinker.py
   :linenos:

Understanding The System Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Submodules**: ``m.submodules.name = module`` adds a submodule to your design

-------------------------------------------------------------------------------- **Clock Frequency**: Real hardware platforms provide clock frequency info
-------------------------------------------------------------------------- **Platform Interface**: ``platform.request()`` gets hardware I/O pins
---------------------------------------------------------------------- **Hierarchical Design**: Components can contain other components

Running on Real Hardware
------------------------

To run your design on actual FPGA hardware, you need:

1. An FPGA board
2. The appropriate platform package (e.g., ``amaranth-boards``)
3. A top-level module that interfaces with the hardware

Here's an example for an iCEStick FPGA board:

.. literalinclude:: _code/program_icestick.py
   :caption: program_icestick.py
   :linenos:

For Other Boards
~~~~~~~~~~~~~~~~

The process is similar for other boards:

1. Import the appropriate platform
2. Create an instance of your top-level module
3. Call ``platform.build(module, do_program=True)``

Troubleshooting and Common Errors
---------------------------------

TypeErrors or AttributeErrors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block::

   TypeError: Cannot assign to non-Value

- Likely tried to assign to a Python variable instead of a Signal

----------------------------------------------------------------- Always use ``.eq()`` for hardware assignments, not Python ``=``

.. code-block::

   AttributeError: 'Module' object has no attribute 'domain'

- You probably wrote ``m.domain.sync`` instead of ``m.d.sync``

Runtime or Logic Errors
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block::

   RuntimeError: Cannot add synchronous assignments: no sync domain is currently active

- You need to define a clock domain

----------------------------------- For simulation, add ``sim.add_clock(Period(MHz=1))``

.. code-block::

   Signal has no timeline

- Signal is not being driven or used in the design

-------------------------------------------------- Check for typos or unused signals

Hardware Deployment Errors
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block::

   OSError: Toolchain binary not found in PATH

- The required synthesis tools (like Yosys) are not installed or not in PATH

---------------------------------------------------------------------------- Install the required tools or add them to PATH

Next Steps
----------

This tutorial has covered the basics of Amaranth HDL. To continue learning:

1. **Advanced Components**: Explore memory components in ``amaranth.lib.memory``
2. **Stream Processing**: Learn about streaming interfaces in ``amaranth.lib.stream``
3. **Clock Domain Crossing**: Study techniques in ``amaranth.lib.cdc``
4. **Hardware Platforms**: Experiment with FPGA boards using ``amaranth-boards``
5. **Community Resources**:

   - GitHub: https://github.com/amaranth-lang/amaranth
   - Documentation: https://amaranth-lang.org

Glossary of Terms
-----------------

- **HDL**: Hardware Description Language - used to describe electronic circuits

------------------------------------------------------------------------------- **FPGA**: Field-Programmable Gate Array - reconfigurable hardware
------------------------------------------------------------------ **Combinational Logic**: Logic where outputs depend only on current inputs
--------------------------------------------------------------------------- **Sequential Logic**: Logic where outputs depend on current inputs and state
----------------------------------------------------------------------------- **Clock Domain**: Group of logic synchronized to the same clock
---------------------------------------------------------------- **Elaboration**: Process of transforming Python code into a hardware netlist
----------------------------------------------------------------------------- **Simulation**: Testing hardware designs in software before physical implementation
------------------------------------------------------------------------------------ **Synthesis**: Process of transforming a hardware design into physical gates
----------------------------------------------------------------------------- **VCD**: Value Change Dump - file format for recording signal changes in simulation

External Resources
------------------

.. note::
   The following resources from the Amaranth community may also be helpful:

   * `Learning FPGA Design with nMigen <https://vivonomicon.com/2020/04/14/learning-fpga-design-with-nmigen/>`_ by Vivonomicon;
   * `"I want to learn nMigen" <https://github.com/kbob/nmigen-examples>`_ by kbob;
   * `A tutorial for using Amaranth HDL <https://github.com/robertbaruch/amaranth-tutorial>`_ by Robert Baruch.
   * `Graded exercises for Amaranth HDL <https://github.com/robertbaruch/amaranth-exercises>`_ by Robert Baruch.
   * `My journey with the Amaranth HDL <https://medium.com/@sporniket.studio/my-journey-with-the-amaranth-hdl-226b38d0b023>`_ by David Sporn, focussed on setting up the workstation, using formal verification and setting up continuous integration.
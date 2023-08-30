.. glossary::

Glossary 
========

.. _Amaranth:

 **Amaranth**
  An open-source toolchain that uses the Python programming language.

  Amaranth makes developing hardware definitions based on synchronous digital logic more intuitive by using the popular Python programming language. The toolchain consists of the Amaranth language, the standard library, the simulator, and the build system, covering all steps of a typical :abbr:`FPGA(Field Programmable Gate Array)` development workflow.

 **ASIC (Application-specific integrated circuit)**
  A non-standard integrated circuit chip made for a specific task or product.

  The term *application* refers to the function the circuit will perform, not to a software application.

  ASICs can be configured to be more power efficient and have better performance than an off-the-shelf general purpose integrated circuit. However, unlike FPGAs, ASICs cannot be reprogrammed and are expensive to produce so design and testing are critical to the success of ASIC development.

  Rather than designing and building them from the ground up, ASICs can be created by interconnecting functional components from cell libraries. The resulting system can then be verified via simulation.

.. _Bitstream generation:  

 **Bitstream generation**
  The code that configures the flash memomory or external storage device to boot the FPGA at power on.

  The final step in translating requirements into circuits on a chip, the code in the bitstream operationalises requirements into logic blocks and interconnects on the FPGA chip.


 **Block RAM (BRAM)**
  Block RAM is on-chip random access memory that stores large amounts of data and is distributed evenly across a chip.
   
  BRAM, sometimes called embedded RAM, doesn't need refreshing (as DRAM does) and, like SRAM, doesn't need a memory controller. Single-port BRAM can either read or write on the port;  dual-port BRAM supports read and write for any two addresses and both ports can read *and* write.

  BRAM :ref:`FIFO<FIFO>` is used to cross clock domains or to buffer data between two interfaces. 

 **CLB (Configurable logic block)**
  The basic repeating logic block on an FPGA, the purpose of CLBs is to implement combinational and sequential logic on an FPGA.

  Be aware that different FPGA manufacturers use different names for this component. 

  Each FPGA contains many logic blocks that are surrounded by a system of programmable interconnects (I/O blocks), called a fabric, that routes signals between the CLBs. The three essential components of a logic block are flip-flops, LUTs, and multiplexers.

 **Clock signal**
  An electronic logic signal that oscillates between a high and a low state at a constant frequency.

  Used to synchronise the actions of digital circuits, clock signals can be one of two types: primary or derived. Primary clocks are generated using a frequency standard, a stable oscillator that creates a signal with a high degree of accuracy and precision. Derived clocks can be made by dividing another clock signal or using a :ref:`PLL<PLL>`. 

.. _DRAM:

 **DRAM (Dynamic Random Access Memory)**
  DRAM is memory that is stored in capacitors and is constantly refreshed.
  
  Rather than store data in flip-flops, as :ref:`SRAM<SRAM>` does, DRAM constantly reads data into capacitors, row-by-row, in sequence, even when no processing is taking place. Racing the decay of the refresh, the continual refreshing has a negative impact on speed and perforamance and the write process produces extra heat as it uses a strong charge. 
  
  DRAM has a higher storage capacity than other kinds of memory, is cheaper and smaller than SRAM, and memory can be deleted and refreshed while running a program.
  
  DRAM is incompatible with SRAM. To create a :ref:`SoC<SoC>` with DRAM requires the design of capacitors; creating a SoC with SRAM requires the design of flip-flops.

 **DUT (Device under test)**
  A physical chip or logic circuit being tested at simulation.

  The results of the testing can result in a chip being given a grade to represent the extent to which it meets tolerance values. 

 **Elaboration**
  Elaboration is the process of constructing a design hierarchy from pre-built modules.

  Elaboration is the first step in translating requirements into circuits on a chip. In elaboration, the behaviour described in the HDL code is analyzed to produce a netlist that itemizes the required logic elements and interconnects. 

  In the toolchain, elaboration is followed by :ref:`synthesis<Synthesis>`, :ref:`place and route<Place and route>`, and :ref:`bitstream generation<Bitstream generation>`.

.. _FIFO:

 **FIFO (First In First Out)**
  First in, first out is a method for organizing the processing of data, especially in a buffer, where the first (oldest) entry is processed first.  

  An elementary building block of integrated circuits, FIFOs are used when crossing clock domains, buffering data, or storing data for use at a later time.  

 **Finite state machine**
  A mathematical model describing a system with a limited number of conditional states of being.
  
  A finite state machine reads a series of inputs. For each input, it will transition to a different state. Each state specifies which state to transition to next, for the given input. When the processing is complete, a ‘then’ action is taken. The abstract machine can process only one state at a time.

  This approach enables engineers to study and test each input and output scenario.

 **Flip-flop**
  An elementary building block of integrated circuits, flip-flops are the basic memory element for storing a single bit of binary data.

  An edge-triggered device, flip-flops react to the edge of a pulse and have two stable states that they ‘flip’ and ‘flop’ between. 

  Modern digital design centres around the D flip-flop (DFF) with Set, Reset, and Enable inputs. The D stands for data or delay, the signals to be stored. 

.. _FPGA:

 **FPGA (Field Programmable Gate Array)**
  A reconfigurable integrated circuit containing internal hardware blocks with user-programmable interconnects to create a customised application.

  The device’s physical attributes are programmed using a hardware definition language. User-programmable I/O blocks interface between the FPGA and external devices.

  FPGAs combine speed, programmability, and flexibility. In addition, they can process very large volumes of data by duplicating circuits and running them in parallel.

 **Hardware register**
  Circuits, typically composed of D flip-flops (DFF), that hold configuration and status information.

  Written in low level HDL code, a hardware register is a set of DFFs with a shared function. At a higher level, a hardware register can be a specific context for making an SoC a function of a peripheral that is controlled by read and write signals to a memory location. 

 **HDL (Hardware definition language)**
  A hardware definition language, such as :ref:`Amaranth<Amaranth>`, describes the structure and timing of electronic circuits and digital logic circuits.

  Modern HDLs include synthesizable code that characterises the synchronous logic (registers), combinational logic (logic gates), and behavioural code (used in testing) that describe a circuit.    

 **IC (Integrated circuit)**
  An integrated circuit has many electronic components embedded on a single chip.

  The circuit is a small wafer, usually made of semiconducting material, that can hold anywhere from hundreds to millions of transistors and resistors (with possibly a few capacitors). These components can perform calculations and store data using either digital or analog technology.
   
  Digital ICs use logic gates that work only with values of 1s and 0s. 

 **JTAG**
  JTAG (Joint Test Action Group) is an industry standard for verifying designs and testing devices like micro controllers and FPGAs after manufacture. 
  
  JTAG is a hardware interface that provides a way to communicate directly with the microchips on a board. It enables the testing, via software, of all the different interconnects without having to physically probe the connections. 

 **Logic gate**
  An elementary building block of integrated circuits, logic gates perform logical operations on binary inputs and outputs.

  Based on a Boolean function that computes TRUE or FALSE, each output is based on the input or combination of inputs supplied to it.

 **Logic synthesis**
  The process of translating a high-level logic definition to lower-level flip-flops and logic gates.
  
  To achieve this, high-level language, written in a program like Python, is translated to lower-level register transfer level (:ref:`RTL<RTL>`) to simulate the behaviour of the circuit for testing.

 **LUT (Look up table)**
  An elementary building block of integrated circuits, a LUT defines how combinatorial logic behaves: the output for every combination of inputs.

  A single input LUT is made up of two flip-flops and a multiplexer. This structure can be expanded into a tree to provide the required capacity. The larger the number of multiplexers, the longer the associated propagation delay.

  LUTs can be used to implement an arbitrary logic gate with the same or fewer inputs: a 4-LUT can implement 1, 2, 3, or 4 inputs. If five inputs are required, two 4-LUTS can be combined but at the expense of propogation delay.

 **MCU (Microcontroller unit)**
  An integrated circuit designed to govern a specific operation in an embedded system.

  An MCU integrates a CPU, onboard memory (may be volatile, may be non-volatile), peripherals for communication, and, usually, clock functions. A complex MCU can be described as a system on chip :ref:`SoC(<SoC>).

 **Memory-mapped peripheral**
  Hardware devices, mapped to the memory address space of a microprocessor, are known as memory-mapped peripherals. 

  The memory data bus moves information bi-directionally between the CPU and memory via store (write) and retrieve (read) signals. A memory-mapped peripheral behaves like physical memory but isn't physical memory. 

 **Microprocessor**
  A microprocessor is a miniature, programmable digital device — a tiny computer on a chip — that retrieves instructions from memory, decodes and executes them, and returns the output. 

  Microprocessors contain the arithmetic, logic, and control circuitry necessary to perform the functions of a digital computer’s central processing unit.


 **Multiplexer**
  A combinational logic circuit designed to switch one of several control signals to a single common output by the application of a control signal.

  A multiplexer selects between several input signals and forwards the selected input to a single output. 

 **Netlist**
  Netlists describe the components and connectivity of an electronic circuit.

  Netlists can be generated at different points in the toolchain process: after synthesis, where the placement information will not be available; and after place and route, when the placement information will be included. 

.. _PLL:

 **PLL (Phase-locked loop)**
  A phase-locked loop is an electronic circuit with a controllable oscillator that constantly adjusts in response to an input signal.

  Its purpose is to generate a derived clock signal that can be faster or slower than the input signal. The derived clock signal can be the result of dividing an input frequency. PLLs can also increase frequency by a non-integer factor.

  Where multiple clock domains are interacting synchronously, PLLs use a fixed phase relationship.

.. _Place and route:

 **Place and route**
  The process of deciding the placement of components on a chip and the related wiring between those components. 
  
  Place and route routines involve complicated maths problems that require optimization. These routines are usually performed by software and produce a layout schema for a chip. 

 **Propagation delay**
  The time required to change the output from one logic state to another logic state after input is changed.

  In simplified terms, the time it takes for a signal to move from source to destination.

  The maximum speed at which a synchronous logic circuit works can be determined by combining the longest path of propagation delay from input to output with the maximum combined propagation delay. Bear in mind that, alongside logic gates, wires also have propogation delay.

 **Register**
  A memory device that can store a specific number of data bits.

  Made up of a series of flip-flops, a register can temporarily store data or a set of instructions for a processor. A register can enable both serial and parallel data transfers, allowing logic operations to be performed on the data stored in it.

  A number of flip-flops can be combined to store binary words. The length of the stored binary word depends on the number of flip-flops that make up the register. 

.. _RTL:

 **Register transfer level (RTL)**
   RTL, the lowest abstraction level for developing FPGAs, is used to create a representation of synchronous digital circuits between hardware registers.

   Hardware definition language is tranformed to RTL which then defines the circuit at gate level. The representation can be verified via simulation. 

.. _Simulation:

 **Simulation**
  A process in which a model of an electronic circuit is analysed by a computer program to validate its functionality.
  
  Simulation models the behaviour of a circuit; it does not model the hardware components described by the HDL. Despite being written in HDL, the simulator treats the code as event-driven parallel programming language to run programs on a particular operating system  or to port a system that doesn't have an FPGA.  

  Simulation is an invaluable tool for ensuring a circuit works the way it was intended to and enables designers to rapidly iterate designs.

.. _SoC:

 **SoC (System on Chip)**
  An integrated circuit, containing almost all the circuitry and components an electronic system (smartphone, small embedded devices) requires.

  In contrast to a computer system that is made up of many distinct components, an SoC integrates the required resources — CPU, memory interfaces, I/O devices, I/O interfaces — into a single chip. 
  
  SoCs are typically built around a microprocessor, microcontroller, or specialised integrated circuit. This increases performance, reduces power consumption, and requires a smaller footprint on a printed circuit board.

  SoCs are more complex than a microcontroller with a higher degree of integration and a greater variety of perhipherals. 

.. _SRAM:

 **SRAM**
  Static Random Access Memory (SRAM) is volatile memory that stores data whilst power is supplied (if the power is turned off, data is lost).
  
  SRAM uses flip-flops to store bits and holds that value until the opposite value replaces it. SRAM is faster in operation than :ref:`DRAM<DRAM>` as it doesn't require a refresh process. 

  In comparison with DRAM, SRAM has a lower power consumption, is more expensive to purchase, has lower storaage capacity, and is more complex in design. 
  
  SRAM is incompatible with DRAM.


.. _Synthesis:

 **Synthesis**
  Synthesis is the process of building a netlist from a circuit design model.

  Synthesis represents the hardware definition language as register transfer level that is automatically transfered into gates. 

 **Waveform**
  A mathematical (logical) description of a signal.

  Waveforms have three main characteristics: period, the length of time the waveform takes to repeat; frequency, the number of times the waveform repeats within a one second time period; and amplitude, the magnitude or intensity of the signal waveform measured in volts or amps.

  The waveform of an electrical signal can be visualised using an oscilloscope. The square waveform is commonly used to represent digital information. A waveform dump, one of the outputs of simulation, can be used to measure the performance of devices a CPU.
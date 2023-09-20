.. glossary::

Glossary 
========

.. _Amaranth:

 **Amaranth**
  An open-source toolchain that uses the Python programming language to create.

  Amaranth makes developing hardware definitions based on synchronous digital logic more intuitive by using the Python programming language. The toolchain consists of the Amaranth language, the standard library, the simulator, and the build system, covering all steps of a typical :abbr:`FPGA(Field Programmable Gate Array)` development workflow.

.. _ASIC:

 **ASIC (Application-Specific Integrated Circuit)**
  A non-standard application-specific integrated circuit chip made for a specific task or product.

  The term *application* refers to the function the circuit will perform, not to a software application.

  ASICs can be configured to be more power efficient and have better performance than an off-the-shelf general purpose integrated circuit. However, unlike FPGAs, ASICs cannot be reprogrammed and are expensive to produce. Design and testing are critical to the success of ASIC development.

  Rather than designing and building them from the ground up, ASICs can be created by interconnecting functional components from :ref:`cell libraries<Standard cell library>`. The resulting system can then be verified via :ref:`simulation<Simulation>`.

.. _Bitstream generation:  

 **Bitstream generation**
  The final step in translating requirements into circuits on a chip, the generated bitstream defines the logic blocks and interconnects on an FPGA chip as well as configuring the flash memory or external storage device to boot the FPGA at power on.

.. _BRAM:

 **BRAM (Block RAM)**
  On-chip random access memory, distributed evenly across a chip, to store large amounts of data.
   
  BRAM, sometimes called embedded RAM, doesn't need refreshing (as :ref:`DRAM<DRAM>` does) and, like :ref:`SRAM<SRAM>`, doesn't need a memory controller. Single-port BRAM can either read or write on the single port;  dual-port BRAM supports read and write for any two addresses and both ports can read *and* write.

  BRAM :ref:`FIFO<FIFO>` is used to cross clock domains or to buffer data between two interfaces. 

.. _CLB:

 **CLB Configurable Logic Block**
  The basic repeating logic block on an FPGA, the purpose of CLBs is to implement combinational and sequential logic on an FPGA.

  Be aware that different FPGA manufacturers use different names for this component. 

  Each FPGA contains many logic blocks that are surrounded by a system of programmable interconnects (I/O blocks), called a fabric, that routes signals between the CLBs. The three essential components of a logic block are :ref:`flip-flops<Flip-flop>`, :ref:`LUTs<LUT>`, and :ref:`multiplexers<Multiplexer>`.

.. _Clock signal:

 **Clock signal**
  An electronic logic signal that oscillates between a high and a low state at a constant frequency.

  Used to synchronise the actions of digital circuits, clock signals can be one of two types: primary or derived. Primary clocks are generated using a frequency standard: a stable oscillator that creates a signal with a high degree of accuracy and precision. Derived clocks can be made by dividing another clock signal or using a :ref:`PLL<PLL>`. 

.. _Clock tree:

 **Clock tree**
  A clock distribution network — clocking circuitry and devices — within a hardware design.

  The simplicity or complexity of the clock tree depends on the hardware design. In more complex systems, the clock tree is represented as a hierarchy where a single reference clock is cascaded and synthesized into a number of different output clocks.
  
.. _Clock tree synthesis:

 **Clock tree synthesis**
  A technique for distributing the clock signal equally among all sequential parts of a design. 

  Clock tree synthesis occurs directly after :ref:`routing and before placement<Place and route>` in the :ref:`synthesis<Synthesis>` process. It inserts buffers and/or inverters along the clock path to balance the clock delay to all inputs. The aim being to reduce latency and skew to ensure all inputs are synchronized. 

.. _Combinational logic:

 **Combinational logic**
  A digital logic function, composed of :ref:`logic gates<Logic gate>`, whose outputs are directly related to the current combination of values on its input — combinational logic has no memory or history. 

  Combinational logic is also known as combinatorial logic.

.. _DRAM:

 **DRAM (Dynamic Random Access Memmory)**
  Memory that is stored in capacitors and is constantly refreshed.
  
  Rather than store data in :ref:`flip-flop`s, as :ref:`SRAM<SRAM>` does, DRAM constantly reads data into capacitors, row-by-row, in sequence, even when no processing is taking place. Racing the decay of the refresh has a negative impact on speed and performance; and the write process produces extra heat because it uses a strong charge. 
  
  DRAM has a higher storage capacity than other kinds of memory; is cheaper and smaller than SRAM; and memory can be deleted and refreshed while running a program.
  
  DRAM is incompatible with SRAM. To create a :ref:`SoC<SoC>` with DRAM requires the design of capacitors; creating a SoC with SRAM requires the design of flip-flops.

.. _DUT:

 **DUT (Device Under Test)**
  A physical chip or logic circuit being tested at :ref:`simulation<Simulation>`.

  Testing can result in a chip being given a grade to represent the extent to which it met tolerance values. 

.. _Elaboration:

 **Elaboration**
  The first step in the toolchain process, elaboration begins the translation of requirements into circuits on a chip. 
  
  In elaboration, the behaviour described in the :ref:`HDL<HDL>` code is analyzed to produce a technology independent :ref:`netlist<Netlist>` that itemizes the required logic elements and interconnects. 

  In the toolchain, elaboration is followed by :ref:`synthesis<Synthesis>`, :ref:`place and route<Place and route>`, and :ref:`bitstream generation<Bitstream generation>`.

.. _FIFO:

 **FIFO (First In First Out)**
  A method for organizing the processing of data, especially in a buffer, where the oldest entry is processed first.  

  An elementary building block of integrated circuits, FIFOs are used when crossing clock domains, buffering data, or storing data for use at a later time.  

.. _Finite state machine:

 **Finite state machine**
  A mathematical model describing a system with a limited number of conditional states of being.
  
  A finite state machine reads a series of inputs. For each input, it will transition to a different state. Each state specifies which state to transition to next, for the given input. When the processing is complete, a ‘then’ action is taken. The abstract machine can process only one state at a time. This approach enables engineers to study and test each input and output scenario.

.. _Flip-flop:

 **Flip-flop**
  An elementary building block of integrated circuits, flip-flops are the basic memory element for storing a single bit of binary data.

  An edge-triggered device, flip-flops react to the edge of a pulse and have two stable states that they ‘flip’ and ‘flop’ between. 

  Modern digital design centres around the D flip-flop (DFF) with Set, Reset, and Enable inputs. The D stands for data or delay, the signals to be stored. 

.. _FPGA:

 **FPGA (Field Programmable Gate Array)**
  A reconfigurable integrated circuit containing internal hardware blocks with user-programmable interconnects to create a customised application.

  The device’s physical attributes are programmed using a :ref:`hardware definition language<HDL>`. User-programmable I/O blocks interface between the FPGA and external devices.

  FPGAs combine speed, programmability, and flexibility. In addition, they can process very large volumes of data by duplicating circuits and running them in parallel.

.. _GDSII:

 **GDSII**
  A binary file format consisting of geometric shapes, labels, and additional data that a foundry can use to manufacture a silicon chip.

  GDSII (or GDS2) is a standard for database interchange of ASIC artwork: all shapes in the design are assigned to a layer (or, sometimes, layers). Layers are combined to form a mask. Each mask is used in the photolithography process that produces the GDSII file the foundry will use when manufacturing the chip.
  
.. _Hardware register:

 **Hardware register**
  Circuits, typically composed of D :ref:`flip-flops<Flip-flop>` (DFF), that hold configuration and status information.

  Written in low-level :ref:`HDL<HDL>` code, a hardware register is a set of DFFs with a shared function. At a higher level, a hardware register can be a specific context for making an SoC a function of a peripheral that is controlled by read and write signals to a memory location. 

.. _HDL:

 **HDL (Hardware Definition Language)**
  An HDL, such as :ref:`Amaranth<Amaranth>`, describes the structure and timing of electronic circuits and digital logic circuits.

  Modern HDLs include synthesizable code that characterises the synchronous logic (:ref:`registers<Register>`), combinational logic (:ref:`logic gates<Logic gate>`), and behavioural code (used in testing) that describe a circuit.    

.. _IC:

 **IC (Integrated Circuit)**
  Sometimes called a microchip or chip, an IC is a semiconductor-based electronic device consisting of transistors, resistors, capacitors, diodes, and inductors that perform the same functions as a larger circuit comprised of discrete components.

  The circuit is a small wafer that can hold anywhere from hundreds to millions of transistors and resistors (with possibly a few capacitors). These components can perform calculations and store data using either digital or analog technology. Digital ICs use :ref:`logic gates<Logic gate>` that work only with values of 1s and 0s. 

.. _JTAG:

 **JTAG**
  An industry standard for verifying designs and testing devices — micro controllers, FPGAs, etc. — after manufacture. 
  
  JTAG is a hardware interface that provides a way to communicate directly with the microchips on a board. It enables the testing, via software, of all the different interconnects on a chip without having to physically probe the connections. 

.. _Logic gate:

 **Logic gate**
  An elementary building block of integrated circuits, logic gates are electronic devices that perform Boolean functions on one or more binary inputs to produce a single binary output.

  The relationship between the input and output is based on the logic gates in the circuit — AND, OR, NOT, XOR, etc. Logic gates can be combined to perform complex processes based on Boolean logic.

.. _Logic synthesis:

 **Logic synthesis**
  The process of translating a high-level logic definition to lower-level :ref:`flip-flops<Flip-flop>` and :ref:`logic gates<Logic gate>`.
  
  To achieve this, high-level code, written in a program like Python, is translated to register transfer level (:ref:`RTL<RTL>`) to simulate the behaviour of the circuit for testing.

.. _LUT:

 **LUT (Look Up Table)**
  An elementary building block of integrated circuits, LUTs define how combinational logic behaves: the output for every combination of inputs.

  A single input LUT is made up of two :ref:`flip-flops<Flip-flop>` and a :ref:`multiplexer<Multiplexer>`. This structure can be expanded into a tree to provide the required capacity. The larger the number of multiplexers, the longer the associated propagation delay.

  LUTs can be used to implement an arbitrary logic gate with the same or fewer inputs: a 4-LUT can implement 1, 2, 3, or 4 inputs. If five inputs are required, two 4-LUTS can be combined but at the expense of propogation delay.

.. _MCU:

 **MCU (Microcontroller Unit)**
  An integrated circuit designed to govern a specific operation in an embedded system.

  An MCU integrates a CPU, onboard memory (may be volatile, may be non-volatile), peripherals for communication, and, usually, clock functions. A complex MCU can be described as a system on chip :ref:`(SoC)<SoC>`.

.. _Memory-mapped peripheral:

 **Memory-mapped peripheral**
   A hardware device that is treated as a memory location in a microcontroller or microprocessor.

   A memory-mapped peripheral is identified by a unique 16-bit address and has a specific address in memory that it reads to and writes data from. 

.. _Microprocessor:

 **Microprocessor**
  A miniature, programmable digital device — a tiny computer on a chip — that retrieves instructions from memory, decodes and executes them, and returns the output. 

  Accepting binary data as input, microprocessors have memory, are clock-driven, and register-based. They contain the arithmetic, logic, and control circuitry necessary to perform the functions of a computer’s central processing unit.

.. _Multiplexer:

 **Multiplexer**
  A combinational logic circuit designed to switch one of several control signals, often from different sources, to a single common output by the application of a control signal.

  Also known as a data selector or input selector, a multiplexer makes it possible for several input signals to share one device rather than having one device per input signal. 

.. _Netlist:

 **Netlist**
  A description of the components and connectivity of an electronic circuit.

  Netlists can be generated at different points in the toolchain process: after synthesis, where the placement information will not be available; and after place and route, when the placement information will be included. 

.. _PLL:

 **PLL (Phase-Locked Loop)**
  A feedback circuit designed to allow one circuit board to synchronize the phase of its on-board clock with an external timing signal. 
  
  PLL circuits compare the phase of an external signal to the phase of a clock signal produced by a voltage controlled crystal oscillator. The circuit then adjusts the phase of the oscillator’s clock signal to match the phase of the external signal to ensure the signals are precisely synchronised with each other. 

  The derived clock signal can be the result of dividing an input frequency. PLLs can increase frequency by a non-integer factor. Where multiple clock domains are interacting synchronously, PLLs use a fixed phase relationship.

.. _Place and route:

 **Place and route**
  A stage in the IC design process, place and route decides the placement of components on a chip and the wiring between those components. 
  
  Placement defines the location of the electronic components, circuitry, and logic elements within the defined space. Routing defines the wiring required to connect the components. These routines are usually performed by the toolchain and produce the layout schema for a chip. 

.. _Propogation delay:

 **Propagation delay**
  The time required to change the output from one logic state to another logic state after input is changed.

  In simplified terms, the time it takes for a signal to move from source to destination. Propogation delay impacts :ref:`sequential logic<Sequential logic>` — logic driven by a clock. The further apart components in a circuit are, the longer the propogation delay will be. This will cause the clock to run more slowly and create timing errors. 

  The maximum speed at which a synchronous logic circuit works can be determined by combining the longest path of propagation delay from input to output with the maximum combined propagation delay. Bear in mind that not only do logic gates have propogation delay, wires do too.  

.. _Register:

 **Register**
  A memory device, located at a known address, that can store a specific number of data bits.

  Made up of a series of :ref:`flip-flops<Flip-flop>`, a register can temporarily store data or a set of instructions for a processor. A register can enable both serial and parallel data transfers, allowing logic operations to be performed on the data stored in it.

  A number of flip-flops can be combined to store binary words. The length of the stored binary word depends on the number of flip-flops that make up the register. 

.. _RTL:

 **RTL (Register Transfer Level)**
   The lowest abstraction level for developing :ref:`FPGAs<FPGA>`, RTL creates a representation of synchronous digital circuits between :ref:`hardware registers<Hardware register>`.

   Hardware definition language is tranformed to RTL which then defines the circuit at gate level. The representation can be verified via :ref:`simulation<Simulation>`. 

.. _Sequential logic:

 **Sequential logic**
  A digital logic function whose outputs depend on both current and past inputs.
  
  Sequential logic has a memory function (unlike :ref:`combinational logic<Combinational logic>` which has none) and is used to construct :ref:`Finite state machines<Finite state machine>`.

  Sequential logic circuits can be either synchronous, the state of the device changes in response to a clock signal or asynchronous, the state of the device changes in response to changing inputs.

.. _Simulation:

 **Simulation**
  A process in which a model of an electronic circuit is analysed by a computer program to validate its functionality.
  
  Simulation models the behaviour of a circuit; it does not model the hardware components described by the :ref:`HDL<HDL>`. Despite being written in HDL, the simulator treats the code as event-driven parallel programming language to run programs on a particular operating system or to port a system that doesn't have an :ref:`FPGA<FPGA>`.  The output of the simulation is a value change dump (VCD).  

.. _SoC:

 **SoC (System on Chip)**
  An integrated circuit, containing almost all the circuitry and components an electronic system (smartphone, small embedded devices) requires.

  In contrast to a computer system that is made up of many distinct components, a SoC integrates the required resources — CPU, memory interfaces, I/O devices, I/O interfaces — into a single chip. SoCs are more complex than a microcontroller with a higher degree of integration and a greater variety of perhipherals. 

  SoCs are typically built around a :ref:`microprocessor<Microprocessor>`, :ref:`microcontroller<MCU>`, or specialised :ref:`integrated circuit<IC>`. This increases performance, reduces power consumption, and requires a smaller footprint on a printed circuit board.

.. _SRAM:

 **SRAM (Static Random Access Memory)**
  Volatile memory that stores data whilst power is supplied (if the power is turned off, data is lost).
  
  SRAM uses flip-flops to store bits and holds that value until the opposite value replaces it. SRAM is faster in operation than :ref:`DRAM<DRAM>` as it doesn't require a refresh process. 

  In comparison with DRAM, SRAM has a lower power consumption, is more expensive to purchase, has lower storaage capacity, and is more complex in design. 
  
  SRAM is incompatible with DRAM.

.. _Standard cell library:

 **Standard cell library**
  A collection of low-level logic functions, with fixed height and variable width cells that can be placed in rows, used to simplify automated digital circuit layout. 

  The library will usually contain well-defined, pre-characterized logic functions — flip-flops, buffers, etc. — optimised for performance and physical size. Cell library characterization is a process of analyzing a circuit using both static and dynamic methods to generate models suitable for chip implementation flows.
  
  These functions enable a more modular approach to circuit design by abstracting some of the complexity of component layout and connectivity. Being well-defined, it's easier to estimate factors such as performance and timing and increase the likelihood of a successful design. 

.. _Synthesis:

 **Synthesis**
  The process of coverting a high-level behavioural design to a lower-level physical implementation.

  The synthesis process represents the behaviour outlined in a :ref:`hardware definition language<HDL>` as :ref:`register transfer level<RTL>` that is then translated into logic gates: :ref:`LUTs<LUT>` and :ref:`flip-flops<Flip-flop>`. A bitstream can then be generated to program an FPGA.

.. _Tapeout:

 **Tapeout**
  The final stage of the IC design process where photolithography is used to produce a graphic representation of the photomask of a circuit, in :ref:`GDSII<GDSII>` format, to be sent to the semiconductor foundry for manufacture.

.. _Waveform:

 **Waveform**
  A visual representation of changes in voltage or current in an electrical circuit over time.

  Waveforms have different shapes and three main characteristics: period, the length of time the waveform takes to repeat; frequency, the number of times the waveform repeats within a time period; and amplitude, the magnitude or intensity of the signal waveform measured in volts or amps.

  The waveform of an electrical signal can be visualised using an oscilloscope. The square waveform is commonly used to represent digital information. A waveform dump, one of the outputs of simulation, can be used to measure the performance of devices.
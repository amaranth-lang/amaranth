Glossary
========

**Amaranth**

 An open-source toolchain that uses the Python programming language.
 Amaranth makes developing hardware definitions, based on synchronous digital logic, more intuitive by using the popular Python programming language. The toolchain consists of the Amaranth language, the standard library, the simulator, and the build system, covering all steps of a typical FPGA development workflow.

**ASIC (Application-specific integrated circuit)**

 A non-standard integrated circuit chip made for a specific task or product.
 The term *application* refers to the function the circuit will perform, not to a software application.
 ASICs can be configured to be more power efficient and have better performance than an off-the-shelf general purpose integrated circuit. However, unlike FPGAs, ASICs cannot be reprogrammed and are expensive to produce so design and testing are critical to the success of ASIC development.
 Rather than designing and building them from the ground up, ASICs can be created by interconnecting functional components from cell libraries. The resulting system can then be verified via simulation.

**CLB (Configurable logic block)**

 The basic repeating logic block on an FPGA, the purpose of CLBs is to implement combinational and sequential logic on an FPGA.
 Be aware that different FPGA manufacturers use different names for this component. 
 Each FPGA contains many logic blocks that are surrounded by a system of programmable interconnects (I/O blocks), called a fabric, that routes signals between the CLBs.
 The three essential components of a logic block are flip-flops, LUTs, and multiplexers.

**Clock signal**

 An electronic logic signal that oscillates between a high and a low state at a constant frequency.
 Used to synchronise the actions of digital circuits, clock signals can be one of two types: primary or derived. Primary clocks are generated using a frequency standard, a stable oscillator that creates a signal with a high degree of accuracy and precision. Derived clocks use a ring oscillator to monitor an input signal strength and try to balance any fluctuations in the voltage by making its signal faster or slower. 

**DUT (Device under test)**

 A module that is being tested for performance and proficiency.
 The module fails testing as soon the first out-of-tolerance value is identified. The aim is to ensure damaged devices don’t enter the market.

**Finite state machine**

 A mathematical model describing a system with a limited number of conditional states of being.
 A finite state machine reads a series of inputs. For each input, it will transition to a different state. Each state specifies which state to transition to next, for the given input. When the processing is complete, a ‘then’ action is taken. The abstract machine can process only one state at a time.
 This approach enables engineers to study and test each input and output scenario.

**Flip-flop**

 An elementary building block of integrated circuits, flip-flops are the basic memory element for storing a single bit of binary data.
 An edge-triggered device, flip-flops react to the edge of a pulse and have two stable states that they ‘flip’ and ‘flop’ between. 
 There are different kinds of flip-flops: SR (set or reset), D (data or delay), JK (a modified SR flip-flop that acts as a toggle), and T(a single input JK flip-flop).

**FPGA (Field Programmable Gate Array)**

 A reconfigurable integrated circuit containing internal hardware blocks with user-programmable interconnects to create a customised application.
 The device’s physical attributes are programmed using a hardware definition language. I/O blocks interface between the FPGA and external devices.
 FPGAs combine speed, programmability, and flexibility. In addition, they can process very large volumes of data by duplicating circuits and running them in parallel.

**Hardware register**

 Circuits, typically composed of flip flops, that hold configuration and status information.
 Hardware registers are used in the interface between software and peripherals: data passed between peripherals and the FPGA is stored temporarily in the hardware register. 
**HDL (Hardware definition language)**

 A hardware definition language, such as Amaranth, describes the structure and timing of electronic circuits and digital logic circuits.
 HDLs describe register transfer, gate, and switch-level logic. Register transfer logic enables the transfer of data between registers. These actions are driven by an explicit clock and gate level logic that defines the individual gate level logic. 

**IC (Integrated circuit)**

 An integrated circuit is a computer chip that has an electronic circuit embedded in it.
 The circuit is a small wafer, usually made of silicon, that can hold anywhere from hundreds to millions of transistors, resistors, and capacitors. These components can perform calculations and store data using either digital or analog technology.
 Digital ICs use logic gates that work only with values of 1s and 0s. 

**Logic gate**

 An elementary building block of integrated circuits, logic gates perform logical operations on binary inputs and outputs.
 Based on a Boolean function that computes TRUE or FALSE, each output is based on the input or combination of inputs supplied to it.
**LUT (Look up table)**

 An elementary building block of integrated circuits, a LUT defines how combinatorial logic behaves: the output for every combination of inputs.
 A single input LUT is made up of two flip-flops and a multiplexer. This structure can be expanded into a tree to provide the required capacity. The larger the number of multiplexers, the longer the associated propagation delay.

**MCU (Microcontroller unit)**

 A compact integrated circuit designed to govern a specific operation in an embedded system.
 An MCU may be comprised of a processor unit, communication interfaces, and peripherals. Memory and clock functions are usually external to an MCU.

**Multiplexer**

 A combinational logic circuit designed to switch one of several inputs through to a single common output by the application of a control signal.
 A multiplexer selects between several input signals and forwards the selected input to a single output. 
 This makes it possible for several input signals to access one device or resource instead of having one device per input signal. They use high speed logic gates to switch digital or binary data through to a single output.

**PLL (Phase-locked loop)**
 A phase-locked loop is an electronic circuit with a voltage-driven oscillator that constantly adjusts in response to an input signal.
 Its purpose is to increase or decrease its output to stabilise a signal on a noisy channel or where data transfer has been interrupted. 

**Propagation delay**

 The time required to change the output from one logic state to another logic state after input is applied.
 In simplified terms, the time it takes for a signal to move from source to destination. The timing begins when the input to a logic gate becomes stable and valid to change and ends when the output of that logic gate is stable and valid to change.
 The propagation delay of a complete circuit is calculated by identifying the longest path of propagation delay from input to output and adding each propagation delay along the path.

**Register**
 A memory device that can store a specific number of data bits.
 Made up of a series of flip-flops, a register can temporarily store data or a set of instructions for a processor. A register can enable both serial and parallel data transfers, allowing logic operations to be performed on the data stored in it.
 A number of flip-flops can be combined to store binary words. The length of the stored binary word depends on the number of flip-flops that make up the register. 

**RTL (Register transfer level)**

 RTL is used to create high-level representations of a circuit, from which lower-level representations and wiring can be derived.
 It models a synchronous digital circuit in terms of the flow of digital signals between hardware registers, and the logical operations performed on those signals.

**Simulation**

 A process in which a model of an electronic circuit is replicated and analysed to verify its functionality.
 Simulation is an invaluable tool for ensuring a circuit works the way it was intended to by checking accuracy, capacity, and performance. It also enables designers to rapidly iterate designs and test them to find the optimal configuration.

**SoC (System on Chip)**

 An integrated circuit, containing almost all the circuitry and components an electronic system requires.
 In contrast to a computer system that is made up of many distinct components, an SoC integrates the required resources — CPU, memory interfaces, I/O devices, I/O interfaces, secondary storage interfaces — into a single chip. SoCs are typically built around a microprocessor, microcontroller, or specialised integrated circuit. This increases performance, reduces power consumption, and requires a smaller semiconductor die area.

**Waveform**

 A mathematical (logical) description of a signal.
 Periodic waveforms provide a clock signal for FPGAs.
 Waveforms have three main characteristics: period, the length of time the waveform takes to repeat; frequency, the number of times the waveform repeats within a one second time period; and amplitude, the magnitude or intensity of the signal waveform measured in volts or amps.
 The waveform of an electrical signal can be visualised in an oscilloscope or instrument that can capture and plot the variations in the signal. The square waveform is commonly used to represent digital information.
 A waveform dump, one of the outputs of simulation, is used in problem resolution.
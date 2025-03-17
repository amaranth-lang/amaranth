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
    
    Parameters
    ----------
    divisor : int
        Clock divisor for baud rate (system_clock / baud_rate)
        Example: 100MHz system clock, 9600 baud → divisor = 10,417
    
    Attributes
    ----------
    i : Signal, in
        Serial input line
    ack : Signal, in
        Acknowledgment (read the received byte)
    data : Signal, out
        8-bit received data
    rdy : Signal, out
        Data ready flag (high when byte received)
    err : Signal, out
        Error flag (high on framing error)
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
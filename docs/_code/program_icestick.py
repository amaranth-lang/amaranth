from amaranth import *
# This import assumes you have amaranth-boards package installed
# If using a different board, import the appropriate platform
try:
    from amaranth_boards.icestick import ICEStickPlatform
    
    # Import our blinker
    from controlled_blinker import ControlledBlinker
    
    # Create a platform for the iCEStick board
    platform = ICEStickPlatform()
    
    # Create a 1Hz blinker (adjust frequency as needed)
    blinker = ControlledBlinker(freq_hz=1)
    
    # Build and program
    platform.build(blinker, do_program=True)
except ImportError:
    print("This example requires amaranth-boards package")
    print("Install it with: pdm add amaranth-boards")
    
# How to run: pdm run python program_icestick.py
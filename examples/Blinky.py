#!/usr/bin/env python3

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog

import argparse
import subprocess
import importlib
import os
import shutil

top_name = "Blinky"

class Blinky(Elaboratable):

    def __init__(self, num_leds=1, clock_divider=21):
        self.num_leds = num_leds
        self.clock_divider = clock_divider
        self.leds = Signal(num_leds)

    def elaborate(self, platform):
        # Create a new Amaranth module
        m = Module()

        # This is a local signal, which will not be accessible from outside.
        count = Signal(self.clock_divider)

        # If the platform is not defined then it is simulation
        if platform is not None:

            # ULX3S
            #leds = [platform.request("led", i) for i in range(self.num_leds)]
            #m.d.comb += [led.o.eq(self.leds[i]) for i, led in enumerate(leds)]

            # Olimex GateMate
            led = platform.request("led", 0)
            m.d.comb += led.o.eq(self.leds)

        # In the sync domain all logic is clocked at the positive edge of
        # the implicit clk signal.
        m.d.sync += count.eq(count + 1)
        with m.If(count == (2**self.clock_divider - 1)):
            m.d.sync += [
                self.leds.eq(~self.leds),
                count.eq(0)
            ]

        return m


def clean():
    files_to_remove = [f"{top_name}.vcd", f"{top_name}.gtkw", f"{top_name}.v"]
    build_dir = "build"

    for file in files_to_remove:
        try:
            os.remove(file)
            print(f"Removed {file}")
        except FileNotFoundError:
            print(f"{file} not found, skipping")

    if os.path.isdir(build_dir):
        try:
            shutil.rmtree(build_dir)
            print(f"Removed {build_dir} directory")
        except OSError as e:
            print(f"Error removing {build_dir}: {e}")

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--simulate", action="store_true", help="Simulate Blinky Example")
    parser.add_argument("-b", "--build", action="store_true", help="Build The Blinky Example")
    parser.add_argument("-v", "--verilog", action="store_true", help="Generate Verilog for Blinky Example")
    parser.add_argument("-p", "--platform", type=str, required=False, help="Platform module (e.g., amaranth_boards.ulx3s.ULX3S_85F_Platform)")
    parser.add_argument("-n", "--num-leds", type=int, default=1, help="Number of LEDs")
    parser.add_argument("-cd", "--clock-divider", type=int, default=21, help="Clock divider (bit width of the counter)")
    parser.add_argument("-cf", "--clock-frequency", type=float, default=1.0, help="Clock frequency in MHz")
    parser.add_argument("-rt", "--runtime", type=int, default=30000, help="Testbench runtime in clock cycles")
    parser.add_argument("-c", "--clean", action="store_true", help="Clean generated files and build directory")
    parser.add_argument("-dp", "--do-program", action="store_true", help="Program the device after building")
    parser.add_argument("-gw", "--gtkwave", action="store_true", help="Open GTKWave after simulation")

    args = parser.parse_args()

    if args.clean:
        clean()

    else:
        num_leds = args.num_leds if args.num_leds is not None else 1
        clock_divider = args.clock_divider if args.clock_divider is not None else 21
        clock_frequency = args.clock_frequency if args.clock_frequency is not None else 1.0
        runtime = args.runtime if args.runtime is not None else 30000
        do_program = args.do_program

        if args.simulate:

            def testbench():
                for _ in range(runtime):
                    yield Tick()

            # Instantiate the Blinky module
            dut = Blinky(num_leds, clock_divider)

            # Create a simulator
            sim = Simulator(dut)
            sim.add_clock(1e-6 / clock_frequency)
            sim.add_process(testbench)
            with sim.write_vcd(f"{top_name}.vcd", f"{top_name}.gtkw", traces=[dut.leds]):
                sim.run()
            
            # Open GTKWave with the generated VCD file if --gtkwave is set
            if args.gtkwave:
                subprocess.run(["gtkwave", f"{top_name}.vcd"])

        elif args.build:
            if args.platform is None:
                raise ValueError("Platform must be specified for building")
            platform_module_name, platform_class_name = args.platform.rsplit(".", 1)
            platform_module = importlib.import_module(platform_module_name)
            platform_class = getattr(platform_module, platform_class_name)

            plat = platform_class()
            plat.build(Blinky(num_leds, clock_divider), do_program=do_program)

        elif args.verilog:
            dut = Blinky(num_leds, clock_divider)
            with open(f"{top_name}.v", "w") as f:
                f.write(verilog.convert(dut, ports=[dut.leds]))

# TODO: Maybe write an additional file where all of the amaranth_boards with their vendors are specified so that you can type ulx3s -85F instead of amaranth_boards.ulx3s.ULX3S_85F_Platform

from .. import *
from ..build import Platform

__all__ = ["ECP5PLL"]


class ECP5PLL(Elaboratable):
    """ECP5 PLL

    Instantiates the EHXPLLL primitive, and provides up to three clock outputs. The EHXPLLL primitive itself
    provides up to four clock outputs, but the last output (CLKOS3) is fed back into the feedback input.

    The frequency ranges are based on: https://github.com/YosysHQ/prjtrellis/blob/master/libtrellis/tools/ecppll.cpp
    """
    num_clkouts_max = 3

    clki_div_range = (1, 128+1)
    clkfb_div_range = (1, 128+1)
    clko_div_range = (1, 128+1)
    clki_freq_range = (8e6, 400e6)
    clko_freq_range = (3.125e6, 400e6)
    vco_freq_range = (400e6, 800e6)

    def __init__(self):
        self.reset = Signal()
        self.locked = Signal()
        self.clkin_freq = None
        self.vcxo_freq = None
        self.num_clkouts = 0
        self.clkin = None
        self.clkouts = {}
        self.config = {}
        self.params = {}
        #self.m = Module()

    def register_clkin(self, clkin, freq):
        # if not isinstance(clkin, (Signal, ClockSignal)):
        #    raise TypeError("clkin must be of type Signal or ClockSignal, not {!r}"
        #                    .format(clkin))
        # else:
        (clki_freq_min, clki_freq_max) = self.clki_freq_range
        if(freq < clki_freq_min):
            raise ValueError("Input clock frequency ({!r}) is lower than the minimum allowed input clock frequency ({!r})"
                             .format(freq, clki_freq_min))
        if(freq > clki_freq_max):
            raise ValueError("Input clock frequency ({!r}) is higher than the maximum allowed input clock frequency ({!r})"
                             .format(freq, clki_freq_max))

        self.clkin_freq = freq
        # self.clkin = Signal()
        # self.m.d.comb += self.clkin.eq(clkin)
        self.clkin = clkin

    def create_clkout(self, cd, freq, phase=0, margin=1e-2):
        (clko_freq_min, clko_freq_max) = self.clko_freq_range
        if freq < clko_freq_min:
            raise ValueError("Requested output clock frequency ({!r}) is lower than the minimum allowed output clock frequency ({!r})"
                             .format(freq, clko_freq_min))
        if freq > clko_freq_max:
            raise ValueError("Requested output clock frequency ({!r}) is higher than the maximum allowed output clock frequency ({!r})"
                             .format(freq, clko_freq_max))
        if self.num_clkouts >= self.num_clkouts_max:
            raise ValueError("Requested number of PLL clock outputs ({!r}) is higher than the number of PLL outputs ({!r})"
                             .format(self.num_clkouts, self.num_clkouts_max))

        self.clkouts[self.num_clkouts] = (cd, freq, phase, margin)
        self.num_clkouts += 1

    def compute_config(self):
        config = {}
        for clki_div in range(*self.clkfb_div_range):
            config["clki_div"] = clki_div
            for clkfb_div in range(*self.clkfb_div_range):
                all_valid = True
                vco_freq = self.clkin_freq/clki_div*clkfb_div*1  # CLKOS3_DIV = 1
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                if vco_freq >= vco_freq_min and vco_freq <= vco_freq_max:
                    for n, (clock_domain, frequency, phase, margin) in sorted(self.clkouts.items()):
                        valid = False
                        for div in range(*self.clko_div_range):
                            clk_freq = vco_freq / div
                            if abs(clk_freq - frequency) <= frequency * margin:
                                config["clko{}_freq".format(n)] = clk_freq
                                config["clko{}_div".format(n)] = div
                                config["clko{}_phase".format(n)] = phase
                                valid = True
                        if not valid:
                            all_valid = False
                else:
                    all_valid = False
                if all_valid:
                    config["vco"] = vco_freq
                    config["clkfb_div"] = clkfb_div
                    return config
        raise ValueError("No PLL config found")

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        config = self.compute_config()

        self.params.update(
            a_FREQUENCY_PIN_CLKI=str(self.clkin_freq / 1e6),
            a_ICP_CURRENT="6",
            a_LPF_RESISTOR="16",
            a_MFG_ENABLE_FILTEROPAMP="1",
            a_MFG_GMCREF_SEL="2",
            i_RST=self.reset,
            i_CLKI=self.clkin,
            o_LOCK=self.locked,
            # CLKOS3 reserved for feedback with div=1.
            p_FEEDBK_PATH="INT_OS3",
            p_CLKOS3_ENABLE="ENABLED",
            p_CLKOS3_DIV=1,
            p_CLKFB_DIV=config["clkfb_div"],
            p_CLKI_DIV=config["clki_div"],
        )

        for n, (clock_domain, frequency, phase, margin) in sorted(self.clkouts.items()):
            n_to_l = {0: "P", 1: "S", 2: "S2"}
            div = config["clko{}_div".format(n)]
            cphase = int(phase * (div + 1) / 360 + div)
            self.params["p_CLKO{}_ENABLE".format(n_to_l[n])] = "ENABLED"
            self.params["p_CLKO{}_DIV".format(n_to_l[n])] = div
            self.params["p_CLKO{}_FPHASE".format(n_to_l[n])] = 0
            self.params["p_CLKO{}_CPHASE".format(n_to_l[n])] = cphase
            self.params["o_CLKO{}".format(n_to_l[n])] = ClockSignal(
                clock_domain.name)

        pll = Instance("EHXPLLL", **self.params)
        m.submodules += pll

        return m

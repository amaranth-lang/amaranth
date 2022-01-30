# amaranth: UnusedElaboratable=no

import unittest

from amaranth.sim import *
from amaranth.lib.crc import Algorithm, Processor, catalog


# Subset of catalogue CRCs used to test the hardware CRC implementation,
# as testing all algorithms takes a long time for little benefit.
# Selected to ensure coverage of CRC width, initial value, reflection, and
# XOR output.
CRCS = [
    "CRC3_GSM", "CRC4_INTERLAKEN", "CRC5_USB", "CRC8_AUTOSAR", "CRC8_BLUETOOTH",
    "CRC8_I_432_1", "CRC12_UMTS", "CRC15_CAN", "CRC16_ARC", "CRC16_IBM_3740",
    "CRC17_CAN_FD", "CRC21_CAN_FD", "CRC24_FLEXRAY_A", "CRC32_AUTOSAR",
    "CRC32_BZIP2", "CRC32_ISO_HDLC", "CRC40_GSM"
]

# All catalogue CRCs with their associated check values and residues from
# the reveng catalogue. Used to verify our computation of the check and
# residue values.
CRC_CHECKS = {
    "CRC3_GSM": (0x4, 0x2),
    "CRC3_ROHC": (0x6, 0x0),
    "CRC4_G_704": (0x7, 0x0),
    "CRC4_ITU": (0x7, 0x0),
    "CRC4_INTERLAKEN": (0xb, 0x2),
    "CRC5_EPC_C1G2": (0x00, 0x00),
    "CRC5_EPC": (0x00, 0x00),
    "CRC5_G_704": (0x07, 0x00),
    "CRC5_ITU": (0x07, 0x00),
    "CRC5_USB": (0x19, 0x06),
    "CRC6_CDMA2000_A": (0x0d, 0x00),
    "CRC6_CDMA2000_B": (0x3b, 0x00),
    "CRC6_DARC": (0x26, 0x00),
    "CRC6_G_704": (0x06, 0x00),
    "CRC6_ITU": (0x06, 0x00),
    "CRC6_GSM": (0x13, 0x3a),
    "CRC7_MMC": (0x75, 0x00),
    "CRC7_ROHC": (0x53, 0x00),
    "CRC7_UMTS": (0x61, 0x00),
    "CRC8_AUTOSAR": (0xdf, 0x42),
    "CRC8_BLUETOOTH": (0x26, 0x00),
    "CRC8_CDMA2000": (0xda, 0x00),
    "CRC8_DARC": (0x15, 0x00),
    "CRC8_DVB_S2": (0xbc, 0x00),
    "CRC8_GSM_A": (0x37, 0x00),
    "CRC8_GSM_B": (0x94, 0x53),
    "CRC8_HITAG": (0xb4, 0x00),
    "CRC8_I_432_1": (0xa1, 0xac),
    "CRC8_ITU": (0xa1, 0xac),
    "CRC8_I_CODE": (0x7e, 0x00),
    "CRC8_LTE": (0xea, 0x00),
    "CRC8_MAXIM_DOW": (0xa1, 0x00),
    "CRC8_MAXIM": (0xa1, 0x00),
    "CRC8_MIFARE_MAD": (0x99, 0x00),
    "CRC8_NRSC_5": (0xf7, 0x00),
    "CRC8_OPENSAFETY": (0x3e, 0x00),
    "CRC8_ROHC": (0xd0, 0x00),
    "CRC8_SAE_J1850": (0x4b, 0xc4),
    "CRC8_SMBUS": (0xf4, 0x00),
    "CRC8_TECH_3250": (0x97, 0x00),
    "CRC8_AES": (0x97, 0x00),
    "CRC8_ETU": (0x97, 0x00),
    "CRC8_WCDMA": (0x25, 0x00),
    "CRC10_ATM": (0x199, 0x000),
    "CRC10_I_610": (0x199, 0x000),
    "CRC10_CDMA2000": (0x233, 0x000),
    "CRC10_GSM": (0x12a, 0x0c6),
    "CRC11_FLEXRAY": (0x5a3, 0x000),
    "CRC11_UMTS": (0x061, 0x000),
    "CRC12_CDMA2000": (0xd4d, 0x000),
    "CRC12_DECT": (0xf5b, 0x000),
    "CRC12_GSM": (0xb34, 0x178),
    "CRC12_UMTS": (0xdaf, 0x000),
    "CRC12_3GPP": (0xdaf, 0x000),
    "CRC13_BBC": (0x04fa, 0x0000),
    "CRC14_DARC": (0x082d, 0x0000),
    "CRC14_GSM": (0x30ae, 0x031e),
    "CRC15_CAN": (0x059e, 0x0000),
    "CRC15_MPT1327": (0x2566, 0x6815),
    "CRC16_ARC": (0xbb3d, 0x0000),
    "CRC16_IBM": (0xbb3d, 0x0000),
    "CRC16_CDMA2000": (0x4c06, 0x0000),
    "CRC16_CMS": (0xaee7, 0x0000),
    "CRC16_DDS_110": (0x9ecf, 0x0000),
    "CRC16_DECT_R": (0x007e, 0x0589),
    "CRC16_DECT_X": (0x007f, 0x0000),
    "CRC16_DNP": (0xea82, 0x66c5),
    "CRC16_EN_13757": (0xc2b7, 0xa366),
    "CRC16_GENIBUS": (0xd64e, 0x1d0f),
    "CRC16_DARC": (0xd64e, 0x1d0f),
    "CRC16_EPC": (0xd64e, 0x1d0f),
    "CRC16_EPC_C1G2": (0xd64e, 0x1d0f),
    "CRC16_I_CODE": (0xd64e, 0x1d0f),
    "CRC16_GSM": (0xce3c, 0x1d0f),
    "CRC16_IBM_3740": (0x29b1, 0x0000),
    "CRC16_AUTOSAR": (0x29b1, 0x0000),
    "CRC16_CCITT_FALSE": (0x29b1, 0x0000),
    "CRC16_IBM_SDLC": (0x906e, 0xf0b8),
    "CRC16_ISO_HDLC": (0x906e, 0xf0b8),
    "CRC16_ISO_IEC_14443_3_B": (0x906e, 0xf0b8),
    "CRC16_X25": (0x906e, 0xf0b8),
    "CRC16_ISO_IEC_14443_3_A": (0xbf05, 0x0000),
    "CRC16_KERMIT": (0x2189, 0x0000),
    "CRC16_BLUETOOTH": (0x2189, 0x0000),
    "CRC16_CCITT": (0x2189, 0x0000),
    "CRC16_CCITT_TRUE": (0x2189, 0x0000),
    "CRC16_V_41_LSB": (0x2189, 0x0000),
    "CRC16_LJ1200": (0xbdf4, 0x0000),
    "CRC16_M17": (0x772b, 0x0000),
    "CRC16_MAXIM_DOW": (0x44c2, 0xb001),
    "CRC16_MAXIM": (0x44c2, 0xb001),
    "CRC16_MCRF4XX": (0x6f91, 0x0000),
    "CRC16_MODBUS": (0x4b37, 0x0000),
    "CRC16_NRSC_5": (0xa066, 0x0000),
    "CRC16_OPENSAFETY_A": (0x5d38, 0x0000),
    "CRC16_OPENSAFETY_B": (0x20fe, 0x0000),
    "CRC16_PROFIBUS": (0xa819, 0xe394),
    "CRC16_IEC_61158_2": (0xa819, 0xe394),
    "CRC16_RIELLO": (0x63d0, 0x0000),
    "CRC16_SPI_FUJITSU": (0xe5cc, 0x0000),
    "CRC16_AUG_CCITT": (0xe5cc, 0x0000),
    "CRC16_T10_DIF": (0xd0db, 0x0000),
    "CRC16_TELEDISK": (0x0fb3, 0x0000),
    "CRC16_TMS37157": (0x26b1, 0x0000),
    "CRC16_UMTS": (0xfee8, 0x0000),
    "CRC16_BUYPASS": (0xfee8, 0x0000),
    "CRC16_VERIFONE": (0xfee8, 0x0000),
    "CRC16_USB": (0xb4c8, 0xb001),
    "CRC16_XMODEM": (0x31c3, 0x0000),
    "CRC16_ACORN": (0x31c3, 0x0000),
    "CRC16_LTE": (0x31c3, 0x0000),
    "CRC16_V_41_MSB": (0x31c3, 0x0000),
    "CRC16_ZMODEM": (0x31c3, 0x0000),
    "CRC17_CAN_FD": (0x04f03, 0x00000),
    "CRC21_CAN_FD": (0x0ed841, 0x000000),
    "CRC24_BLE": (0xc25a56, 0x000000),
    "CRC24_FLEXRAY_A": (0x7979bd, 0x000000),
    "CRC24_FLEXRAY_B": (0x1f23b8, 0x000000),
    "CRC24_INTERLAKEN": (0xb4f3e6, 0x144e63),
    "CRC24_LTE_A": (0xcde703, 0x000000),
    "CRC24_LTE_B": (0x23ef52, 0x000000),
    "CRC24_OPENPGP": (0x21cf02, 0x000000),
    "CRC24_OS_9": (0x200fa5, 0x800fe3),
    "CRC30_CDMA": (0x04c34abf, 0x34efa55a),
    "CRC31_PHILIPS": (0x0ce9e46c, 0x4eaf26f1),
    "CRC32_AIXM": (0x3010bf7f, 0x00000000),
    "CRC32_AUTOSAR": (0x1697d06a, 0x904cddbf),
    "CRC32_BASE91_D": (0x87315576, 0x45270551),
    "CRC32_BZIP2": (0xfc891918, 0xc704dd7b),
    "CRC32_AAL5": (0xfc891918, 0xc704dd7b),
    "CRC32_DECT_B": (0xfc891918, 0xc704dd7b),
    "CRC32_CD_ROM_EDC": (0x6ec2edc4, 0x00000000),
    "CRC32_CKSUM": (0x765e7680, 0xc704dd7b),
    "CRC32_POSIX": (0x765e7680, 0xc704dd7b),
    "CRC32_ISCSI": (0xe3069283, 0xb798b438),
    "CRC32_BASE91_C": (0xe3069283, 0xb798b438),
    "CRC32_CASTAGNOLI": (0xe3069283, 0xb798b438),
    "CRC32_INTERLAKEN": (0xe3069283, 0xb798b438),
    "CRC32_ISO_HDLC": (0xcbf43926, 0xdebb20e3),
    "CRC32_ADCCP": (0xcbf43926, 0xdebb20e3),
    "CRC32_V_42": (0xcbf43926, 0xdebb20e3),
    "CRC32_XZ": (0xcbf43926, 0xdebb20e3),
    "CRC32_PKZIP": (0xcbf43926, 0xdebb20e3),
    "CRC32_ETHERNET": (0xcbf43926, 0xdebb20e3),
    "CRC32_JAMCRC": (0x340bc6d9, 0x00000000),
    "CRC32_MEF": (0xd2c22f51, 0x00000000),
    "CRC32_MPEG_2": (0x0376e6e7, 0x00000000),
    "CRC32_XFER": (0xbd0be338, 0x00000000),
    "CRC40_GSM": (0xd4164fc646, 0xc4ff8071ff),
    "CRC64_ECMA_182": (0x6c40df5f0b497347, 0x0000000000000000),
    "CRC64_GO_ISO": (0xb90956c775a41001, 0x5300000000000000),
    "CRC64_MS": (0x75d4b74f024eceea, 0x0000000000000000),
    "CRC64_REDIS": (0xe9c6d914c4b8d9ca, 0x0000000000000000),
    "CRC64_WE": (0x62ec59e3f1a4f00a, 0xfcacbebd5931a992),
    "CRC64_XZ": (0x995dc9bbdf1939fa, 0x49958c9abd7d353f),
    "CRC64_ECMA": (0x995dc9bbdf1939fa, 0x49958c9abd7d353f),
    "CRC82_DARC": (0x09ea83f625023801fd612, 0x000000000000000000000),
}


class CRCTestCase(unittest.TestCase):
    def test_checks(self):
        """
        Verify computed check values and residues match catalogue entries.
        """
        for name in dir(catalog):
            if name.startswith("CRC"):
                crc = getattr(catalog, name)(data_width=8)
                check, residue = CRC_CHECKS[name]
                assert crc.compute(b"123456789") == check
                assert crc.residue() == residue

    def test_repr(self):
        algorithm = catalog.CRC8_AUTOSAR
        assert repr(algorithm) == "Algorithm(crc_width=8, polynomial=0x2f," \
            " initial_crc=0xff, reflect_input=False, reflect_output=False," \
            " xor_output=0xff)"

        params = algorithm(data_width=8)
        assert repr(params) == "Parameters(Algorithm(crc_width=8," \
            " polynomial=0x2f, initial_crc=0xff, reflect_input=False," \
            " reflect_output=False, xor_output=0xff), data_width=8)"

    def test_processor_typecheck(self):
        with self.assertRaises(TypeError):
            proc = Processor(12)

    def test_algorithm_range_checks(self):
        with self.assertRaises(ValueError):
            Algorithm(crc_width=0, polynomial=0x3, initial_crc=0x0,
                      reflect_input=False, reflect_output=False, xor_output=0x7)
        with self.assertRaises(ValueError):
            Algorithm(crc_width=3, polynomial=0x8, initial_crc=0x0,
                      reflect_input=False, reflect_output=False, xor_output=0x7)
        with self.assertRaises(ValueError):
            Algorithm(crc_width=3, polynomial=0x3, initial_crc=0x8,
                      reflect_input=False, reflect_output=False, xor_output=0x7)
        with self.assertRaises(ValueError):
            Algorithm(crc_width=3, polynomial=0x3, initial_crc=0x0,
                      reflect_input=False, reflect_output=False, xor_output=0x8)

    def test_parameter_range_checks(self):
        with self.assertRaises(ValueError):
            catalog.CRC8_AUTOSAR(data_width=0)
        with self.assertRaises(ValueError):
            crc = catalog.CRC8_AUTOSAR()
            crc.compute([3, 4, 256])

    def test_crc_bytes(self):
        """
        Verify CRC generation by computing the check value for each CRC
        in the catalogue with byte-sized inputs.
        """
        for name in CRCS:
            crc = getattr(catalog, name)(data_width=8).create()
            check = CRC_CHECKS[name][0]

            def process():
                for word in b"123456789":
                    yield crc.start.eq(word == b"1")
                    yield crc.data.eq(word)
                    yield crc.valid.eq(1)
                    yield
                yield crc.valid.eq(0)
                yield
                self.assertEqual((yield crc.crc), check)

            sim = Simulator(crc)
            sim.add_sync_process(process)
            sim.add_clock(1e-6)
            sim.run()

    def test_crc_words(self):
        """
        Verify CRC generation for non-byte-sized data by computing a check
        value for 1, 2, 4, 16, 32, and 64-bit inputs.
        """
        # We can't use the catalogue check value since it requires 8-bit
        # inputs, so we'll instead use an input of b"12345678".
        data = b"12345678"
        # Split data into individual bits. When input is reflected, we have
        # to reflect each byte first, then form the input words, then let
        # the CRC module reflect those words, to get the same effective input.
        bits = "".join(f"{x:08b}" for x in data)
        bits_r = "".join(f"{x:08b}"[::-1] for x in data)

        for name in CRCS:
            for m in (1, 2, 4, 16, 32, 64):
                algo = getattr(catalog, name)
                crc = algo(data_width=m).create()
                # Use a SoftwareCRC with byte inputs to compute new checks.
                swcrc = algo(data_width=8)
                check = swcrc.compute(data)
                # Chunk input bits into m-bit words, reflecting if needed.
                if algo.reflect_input:
                    d = [bits_r[i : i+m][::-1] for i in range(0, len(bits), m)]
                else:
                    d = [bits[i : i+m] for i in range(0, len(bits), m)]
                words = [int(x, 2) for x in d]

                def process():
                    yield crc.start.eq(1)
                    yield
                    yield crc.start.eq(0)
                    for word in words:
                        yield crc.data.eq(word)
                        yield crc.valid.eq(1)
                        yield
                    yield crc.valid.eq(0)
                    yield
                    self.assertEqual((yield crc.crc), check)

                sim = Simulator(crc)
                sim.add_sync_process(process)
                sim.add_clock(1e-6)
                sim.run()

    def test_crc_match(self):
        """Verify match_detected output detects valid codewords."""
        for name in CRCS:
            algo = getattr(catalog, name)
            n = algo.crc_width
            m = 8 if n % 8 == 0 else 1
            crc = algo(data_width=m).create()
            check = CRC_CHECKS[name][0]

            if m == 8:
                # For CRCs which are multiples of one byte wide, we can easily
                # append the correct checksum in bytes.
                check_b = check.to_bytes(n // 8, "little" if algo.reflect_output else "big")
                words = b"123456789" + check_b
            else:
                # For other CRC sizes, use single-bit input data.
                if algo.reflect_output:
                    check_b = check.to_bytes((n + 7)//8, "little")
                    if not algo.reflect_input:
                        # For cross-endian CRCs, flip the CRC bits separately.
                        check_b = bytearray(int(f"{x:08b}"[::-1], 2) for x in check_b)
                else:
                    shift = 8 - (n % 8)
                    check_b = (check << shift).to_bytes((n + 7)//8, "big")
                    # No catalogue CRCs have ref_in but not ref_out.
                codeword = b"123456789" + check_b
                words = []
                for byte in codeword:
                    if algo.reflect_input:
                        words += [int(x) for x in f"{byte:08b}"[::-1]]
                    else:
                        words += [int(x) for x in f"{byte:08b}"]
                words = words[:72 + n]

            def process():
                yield crc.start.eq(1)
                yield
                yield crc.start.eq(0)
                for word in words:
                    yield crc.data.eq(word)
                    yield crc.valid.eq(1)
                    yield
                yield crc.valid.eq(0)
                yield
                self.assertTrue((yield crc.match_detected))

            sim = Simulator(crc)
            sim.add_sync_process(process)
            sim.add_clock(1e-6)
            sim.run()

"""
This module contains a catalog of predefined CRC algorithms, retrieved from the `reveng catalogue`_
on 2023-05-25.

.. _reveng catalogue: https://reveng.sourceforge.io/crc-catalogue/all.htm

See the documentation for the :mod:`~amaranth.lib.crc` module for examples.
"""

from . import Algorithm

# Note: The trailing `#:` gives Sphinx an empty documentation string for each
# constant, allowing it to be documented with `automodule` (which otherwise
# ignores undocumented module constants) and also preventing it from using
# the Algorithm docstring if otherwise forced to document the constants.

CRC3_GSM = Algorithm(
    crc_width=3,
    polynomial=0x3,
    initial_crc=0x0,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x7)  #:

CRC3_ROHC = Algorithm(
    crc_width=3,
    polynomial=0x3,
    initial_crc=0x7,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0)  #:

CRC4_G_704 = CRC4_ITU = Algorithm(
    crc_width=4,
    polynomial=0x3,
    initial_crc=0x0,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0)  #:

CRC4_INTERLAKEN = Algorithm(
    crc_width=4,
    polynomial=0x3,
    initial_crc=0xf,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xf)  #:

CRC5_EPC_C1G2 = CRC5_EPC = Algorithm(
    crc_width=5,
    polynomial=0x09,
    initial_crc=0x09,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC5_G_704 = CRC5_ITU = Algorithm(
    crc_width=5,
    polynomial=0x15,
    initial_crc=0x00,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00)  #:

CRC5_USB = Algorithm(
    crc_width=5,
    polynomial=0x05,
    initial_crc=0x1f,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x1f)  #:

CRC6_CDMA2000_A = Algorithm(
    crc_width=6,
    polynomial=0x27,
    initial_crc=0x3f,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC6_CDMA2000_B = Algorithm(
    crc_width=6,
    polynomial=0x07,
    initial_crc=0x3f,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC6_DARC = Algorithm(
    crc_width=6,
    polynomial=0x19,
    initial_crc=0x00,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00)  #:

CRC6_G_704 = CRC6_ITU = Algorithm(
    crc_width=6,
    polynomial=0x03,
    initial_crc=0x00,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00)  #:

CRC6_GSM = Algorithm(
    crc_width=6,
    polynomial=0x2f,
    initial_crc=0x00,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x3f)  #:

CRC7_MMC = Algorithm(
    crc_width=7,
    polynomial=0x09,
    initial_crc=0x00,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC7_ROHC = Algorithm(
    crc_width=7,
    polynomial=0x4f,
    initial_crc=0x7f,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00)  #:

CRC7_UMTS = Algorithm(
    crc_width=7,
    polynomial=0x45,
    initial_crc=0x00,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC8_AUTOSAR = Algorithm(
    crc_width=8,
    polynomial=0x2f,
    initial_crc=0xff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xff)  #:

CRC8_BLUETOOTH = Algorithm(
    crc_width=8,
    polynomial=0xa7,
    initial_crc=0x00,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00)  #:

CRC8_CDMA2000 = Algorithm(
    crc_width=8,
    polynomial=0x9b,
    initial_crc=0xff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC8_DARC = Algorithm(
    crc_width=8,
    polynomial=0x39,
    initial_crc=0x00,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00)  #:

CRC8_DVB_S2 = Algorithm(
    crc_width=8,
    polynomial=0xd5,
    initial_crc=0x00,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC8_GSM_A = Algorithm(
    crc_width=8,
    polynomial=0x1d,
    initial_crc=0x00,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC8_GSM_B = Algorithm(
    crc_width=8,
    polynomial=0x49,
    initial_crc=0x00,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xff)  #:

CRC8_HITAG = Algorithm(
    crc_width=8,
    polynomial=0x1d,
    initial_crc=0xff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC8_I_432_1 = CRC8_ITU = Algorithm(
    crc_width=8,
    polynomial=0x07,
    initial_crc=0x00,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x55)  #:

CRC8_I_CODE = Algorithm(
    crc_width=8,
    polynomial=0x1d,
    initial_crc=0xfd,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC8_LTE = Algorithm(
    crc_width=8,
    polynomial=0x9b,
    initial_crc=0x00,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC8_MAXIM_DOW = CRC8_MAXIM = Algorithm(
    crc_width=8,
    polynomial=0x31,
    initial_crc=0x00,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00)  #:

CRC8_MIFARE_MAD = Algorithm(
    crc_width=8,
    polynomial=0x1d,
    initial_crc=0xc7,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC8_NRSC_5 = Algorithm(
    crc_width=8,
    polynomial=0x31,
    initial_crc=0xff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC8_OPENSAFETY = Algorithm(
    crc_width=8,
    polynomial=0x2f,
    initial_crc=0x00,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC8_ROHC = Algorithm(
    crc_width=8,
    polynomial=0x07,
    initial_crc=0xff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00)  #:

CRC8_SAE_J1850 = Algorithm(
    crc_width=8,
    polynomial=0x1d,
    initial_crc=0xff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xff)  #:

CRC8_SMBUS = Algorithm(
    crc_width=8,
    polynomial=0x07,
    initial_crc=0x00,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00)  #:

CRC8_TECH_3250 = CRC8_AES = CRC8_ETU = Algorithm(
    crc_width=8,
    polynomial=0x1d,
    initial_crc=0xff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00)  #:

CRC8_WCDMA = Algorithm(
    crc_width=8,
    polynomial=0x9b,
    initial_crc=0x00,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00)  #:

CRC10_ATM = CRC10_I_610 = Algorithm(
    crc_width=10,
    polynomial=0x233,
    initial_crc=0x000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x000)  #:

CRC10_CDMA2000 = Algorithm(
    crc_width=10,
    polynomial=0x3d9,
    initial_crc=0x3ff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x000)  #:

CRC10_GSM = Algorithm(
    crc_width=10,
    polynomial=0x175,
    initial_crc=0x000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x3ff)  #:

CRC11_FLEXRAY = Algorithm(
    crc_width=11,
    polynomial=0x385,
    initial_crc=0x01a,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x000)  #:

CRC11_UMTS = Algorithm(
    crc_width=11,
    polynomial=0x307,
    initial_crc=0x000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x000)  #:

CRC12_CDMA2000 = Algorithm(
    crc_width=12,
    polynomial=0xf13,
    initial_crc=0xfff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x000)  #:

CRC12_DECT = Algorithm(
    crc_width=12,
    polynomial=0x80f,
    initial_crc=0x000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x000)  #:

CRC12_GSM = Algorithm(
    crc_width=12,
    polynomial=0xd31,
    initial_crc=0x000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xfff)  #:

CRC12_UMTS = CRC12_3GPP = Algorithm(
    crc_width=12,
    polynomial=0x80f,
    initial_crc=0x000,
    reflect_input=False,
    reflect_output=True,
    xor_output=0x000)  #:

CRC13_BBC = Algorithm(
    crc_width=13,
    polynomial=0x1cf5,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC14_DARC = Algorithm(
    crc_width=14,
    polynomial=0x0805,
    initial_crc=0x0000,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0000)  #:

CRC14_GSM = Algorithm(
    crc_width=14,
    polynomial=0x202d,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x3fff)  #:

CRC15_CAN = Algorithm(
    crc_width=15,
    polynomial=0x4599,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC15_MPT1327 = Algorithm(
    crc_width=15,
    polynomial=0x6815,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0001)  #:

CRC16_ARC = CRC16_IBM = Algorithm(
    crc_width=16,
    polynomial=0x8005,
    initial_crc=0x0000,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0000)  #:

CRC16_CDMA2000 = Algorithm(
    crc_width=16,
    polynomial=0xc867,
    initial_crc=0xffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_CMS = Algorithm(
    crc_width=16,
    polynomial=0x8005,
    initial_crc=0xffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_DDS_110 = Algorithm(
    crc_width=16,
    polynomial=0x8005,
    initial_crc=0x800d,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_DECT_R = Algorithm(
    crc_width=16,
    polynomial=0x0589,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0001)  #:

CRC16_DECT_X = Algorithm(
    crc_width=16,
    polynomial=0x0589,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_DNP = Algorithm(
    crc_width=16,
    polynomial=0x3d65,
    initial_crc=0x0000,
    reflect_input=True,
    reflect_output=True,
    xor_output=0xffff)  #:

CRC16_EN_13757 = Algorithm(
    crc_width=16,
    polynomial=0x3d65,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xffff)  #:

CRC16_GENIBUS = CRC16_DARC = CRC16_EPC = CRC16_EPC_C1G2 = CRC16_I_CODE = Algorithm(
    crc_width=16,
    polynomial=0x1021,
    initial_crc=0xffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xffff)  #:

CRC16_GSM = Algorithm(
    crc_width=16,
    polynomial=0x1021,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xffff)  #:

CRC16_IBM_3740 = CRC16_AUTOSAR = CRC16_CCITT_FALSE = Algorithm(
    crc_width=16,
    polynomial=0x1021,
    initial_crc=0xffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_IBM_SDLC = CRC16_ISO_HDLC = CRC16_ISO_IEC_14443_3_B = CRC16_X25 = Algorithm(
    crc_width=16,
    polynomial=0x1021,
    initial_crc=0xffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0xffff)  #:

CRC16_ISO_IEC_14443_3_A = Algorithm(
    crc_width=16,
    polynomial=0x1021,
    initial_crc=0xc6c6,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0000)  #:

CRC16_KERMIT = CRC16_BLUETOOTH = CRC16_CCITT = CRC16_CCITT_TRUE = CRC16_V_41_LSB = Algorithm(
    crc_width=16,
    polynomial=0x1021,
    initial_crc=0x0000,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0000)  #:

CRC16_LJ1200 = Algorithm(
    crc_width=16,
    polynomial=0x6f63,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_M17 = Algorithm(
    crc_width=16,
    polynomial=0x5935,
    initial_crc=0xffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_MAXIM_DOW = CRC16_MAXIM = Algorithm(
    crc_width=16,
    polynomial=0x8005,
    initial_crc=0x0000,
    reflect_input=True,
    reflect_output=True,
    xor_output=0xffff)  #:

CRC16_MCRF4XX = Algorithm(
    crc_width=16,
    polynomial=0x1021,
    initial_crc=0xffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0000)  #:

CRC16_MODBUS = Algorithm(
    crc_width=16,
    polynomial=0x8005,
    initial_crc=0xffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0000)  #:

CRC16_NRSC_5 = Algorithm(
    crc_width=16,
    polynomial=0x080b,
    initial_crc=0xffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0000)  #:

CRC16_OPENSAFETY_A = Algorithm(
    crc_width=16,
    polynomial=0x5935,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_OPENSAFETY_B = Algorithm(
    crc_width=16,
    polynomial=0x755b,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_PROFIBUS = CRC16_IEC_61158_2 = Algorithm(
    crc_width=16,
    polynomial=0x1dcf,
    initial_crc=0xffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xffff)  #:

CRC16_RIELLO = Algorithm(
    crc_width=16,
    polynomial=0x1021,
    initial_crc=0xb2aa,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0000)  #:

CRC16_SPI_FUJITSU = CRC16_AUG_CCITT = Algorithm(
    crc_width=16,
    polynomial=0x1021,
    initial_crc=0x1d0f,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_T10_DIF = Algorithm(
    crc_width=16,
    polynomial=0x8bb7,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_TELEDISK = Algorithm(
    crc_width=16,
    polynomial=0xa097,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_TMS37157 = Algorithm(
    crc_width=16,
    polynomial=0x1021,
    initial_crc=0x89ec,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0000)  #:

CRC16_UMTS = CRC16_BUYPASS = CRC16_VERIFONE = Algorithm(
    crc_width=16,
    polynomial=0x8005,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC16_USB = Algorithm(
    crc_width=16,
    polynomial=0x8005,
    initial_crc=0xffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0xffff)  #:

CRC16_XMODEM = CRC16_ACORN = CRC16_LTE = CRC16_V_41_MSB = CRC16_ZMODEM = Algorithm(
    crc_width=16,
    polynomial=0x1021,
    initial_crc=0x0000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000)  #:

CRC17_CAN_FD = Algorithm(
    crc_width=17,
    polynomial=0x1685b,
    initial_crc=0x00000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00000)  #:

CRC21_CAN_FD = Algorithm(
    crc_width=21,
    polynomial=0x102899,
    initial_crc=0x000000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x000000)  #:

CRC24_BLE = Algorithm(
    crc_width=24,
    polynomial=0x00065b,
    initial_crc=0x555555,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x000000)  #:

CRC24_FLEXRAY_A = Algorithm(
    crc_width=24,
    polynomial=0x5d6dcb,
    initial_crc=0xfedcba,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x000000)  #:

CRC24_FLEXRAY_B = Algorithm(
    crc_width=24,
    polynomial=0x5d6dcb,
    initial_crc=0xabcdef,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x000000)  #:

CRC24_INTERLAKEN = Algorithm(
    crc_width=24,
    polynomial=0x328b63,
    initial_crc=0xffffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xffffff)  #:

CRC24_LTE_A = Algorithm(
    crc_width=24,
    polynomial=0x864cfb,
    initial_crc=0x000000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x000000)  #:

CRC24_LTE_B = Algorithm(
    crc_width=24,
    polynomial=0x800063,
    initial_crc=0x000000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x000000)  #:

CRC24_OPENPGP = Algorithm(
    crc_width=24,
    polynomial=0x864cfb,
    initial_crc=0xb704ce,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x000000)  #:

CRC24_OS_9 = Algorithm(
    crc_width=24,
    polynomial=0x800063,
    initial_crc=0xffffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xffffff)  #:

CRC30_CDMA = Algorithm(
    crc_width=30,
    polynomial=0x2030b9c7,
    initial_crc=0x3fffffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x3fffffff)  #:

CRC31_PHILIPS = Algorithm(
    crc_width=31,
    polynomial=0x04c11db7,
    initial_crc=0x7fffffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x7fffffff)  #:

CRC32_AIXM = Algorithm(
    crc_width=32,
    polynomial=0x814141ab,
    initial_crc=0x00000000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00000000)  #:

CRC32_AUTOSAR = Algorithm(
    crc_width=32,
    polynomial=0xf4acfb13,
    initial_crc=0xffffffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0xffffffff)  #:

CRC32_BASE91_D = Algorithm(
    crc_width=32,
    polynomial=0xa833982b,
    initial_crc=0xffffffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0xffffffff)  #:

CRC32_BZIP2 = CRC32_AAL5 = CRC32_DECT_B = Algorithm(
    crc_width=32,
    polynomial=0x04c11db7,
    initial_crc=0xffffffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xffffffff)  #:

CRC32_CD_ROM_EDC = Algorithm(
    crc_width=32,
    polynomial=0x8001801b,
    initial_crc=0x00000000,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00000000)  #:

CRC32_CKSUM = CRC32_POSIX = Algorithm(
    crc_width=32,
    polynomial=0x04c11db7,
    initial_crc=0x00000000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xffffffff)  #:

CRC32_ISCSI = CRC32_BASE91_C = CRC32_CASTAGNOLI = CRC32_INTERLAKEN = Algorithm(
    crc_width=32,
    polynomial=0x1edc6f41,
    initial_crc=0xffffffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0xffffffff)  #:

CRC32_ISO_HDLC = CRC32_ADCCP = CRC32_V_42 = CRC32_XZ = CRC32_PKZIP = CRC32_ETHERNET = Algorithm(
    crc_width=32,
    polynomial=0x04c11db7,
    initial_crc=0xffffffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0xffffffff)  #:

CRC32_JAMCRC = Algorithm(
    crc_width=32,
    polynomial=0x04c11db7,
    initial_crc=0xffffffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00000000)  #:

CRC32_MEF = Algorithm(
    crc_width=32,
    polynomial=0x741b8cd7,
    initial_crc=0xffffffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x00000000)  #:

CRC32_MPEG_2 = Algorithm(
    crc_width=32,
    polynomial=0x04c11db7,
    initial_crc=0xffffffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00000000)  #:

CRC32_XFER = Algorithm(
    crc_width=32,
    polynomial=0x000000af,
    initial_crc=0x00000000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x00000000)  #:

CRC40_GSM = Algorithm(
    crc_width=40,
    polynomial=0x0004820009,
    initial_crc=0x0000000000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xffffffffff)  #:

CRC64_ECMA_182 = Algorithm(
    crc_width=64,
    polynomial=0x42f0e1eba9ea3693,
    initial_crc=0x0000000000000000,
    reflect_input=False,
    reflect_output=False,
    xor_output=0x0000000000000000)  #:

CRC64_GO_ISO = Algorithm(
    crc_width=64,
    polynomial=0x000000000000001b,
    initial_crc=0xffffffffffffffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0xffffffffffffffff)  #:

CRC64_MS = Algorithm(
    crc_width=64,
    polynomial=0x259c84cba6426349,
    initial_crc=0xffffffffffffffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0000000000000000)  #:

CRC64_REDIS = Algorithm(
    crc_width=64,
    polynomial=0xad93d23594c935a9,
    initial_crc=0x0000000000000000,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x0000000000000000)  #:

CRC64_WE = Algorithm(
    crc_width=64,
    polynomial=0x42f0e1eba9ea3693,
    initial_crc=0xffffffffffffffff,
    reflect_input=False,
    reflect_output=False,
    xor_output=0xffffffffffffffff)  #:

CRC64_XZ = CRC64_ECMA = Algorithm(
    crc_width=64,
    polynomial=0x42f0e1eba9ea3693,
    initial_crc=0xffffffffffffffff,
    reflect_input=True,
    reflect_output=True,
    xor_output=0xffffffffffffffff)  #:

CRC82_DARC = Algorithm(
    crc_width=82,
    polynomial=0x0308c0111011401440411,
    initial_crc=0x000000000000000000000,
    reflect_input=True,
    reflect_output=True,
    xor_output=0x000000000000000000000)  #:

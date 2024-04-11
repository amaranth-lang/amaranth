Cyclic redundancy checks
########################

.. py:module:: amaranth.lib.crc

The :mod:`amaranth.lib.crc` module provides facilities for computing cyclic redundancy checks (CRCs)
in software and in hardware.


Introduction
============

The essentials of a CRC computation are specified with an :class:`Algorithm` object, which defines
CRC width, polynomial, initial value, input/output reflection, and output XOR. Many commonly used
CRC algorithms are available in the :py:mod:`~amaranth.lib.crc.catalog` module, while most other
CRC designs can be accommodated by manually constructing an :class:`Algorithm`.

An :class:`Algorithm` is specialized for a particular data width to obtain :class:`Parameters`,
which fully define a CRC computation. :meth:`Parameters.compute` computes a CRC in software, while
:meth:`Parameters.create` creates a :class:`Processor` that computes a CRC in hardware.


Examples
========

.. testsetup::

    from amaranth import *

    m = Module()

.. testcode::

    from amaranth.lib.crc import Algorithm
    from amaranth.lib.crc.catalog import CRC16_CCITT, CRC16_USB


    # Compute a CRC in hardware using the predefined CRC16-CCITT algorithm and a data word
    # width of 8 bits (in other words, computing it over bytes).
    m.submodules.crc16_ccitt = crc16_ccitt = CRC16_CCITT().create()

    # Compute a CRC in hardware using the predefined CRC16-USB algorithm and a data word
    # width of 32 bits.
    m.submodules.crc16_usb = crc16_usb = CRC16_USB(32).create()

    # Compute a CRC in software using a custom CRC algorithm and explicitly specified data word
    # width.
    algo = Algorithm(crc_width=16, polynomial=0x1021, initial_crc=0xffff,
        reflect_input=False, reflect_output=False, xor_output=0x0000)
    assert algo(data_width=8).compute(b"123456789") == 0x29b1


Algorithms and parameters
=========================

.. autoclass:: Algorithm
   :special-members: __call__

.. autoclass:: Parameters


CRC computation
===============

.. autoclass:: Processor()


Predefined algorithms
=====================

The following predefined CRC algorithms are available:

.. toctree::

   crc/catalog

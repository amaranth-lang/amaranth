Resource mapping and definitions
################################

.. py:module:: amaranth.build.dsl

The :mod:`amaranth.build.dsl` module provides a fluent DSL for defining I/O resources that may be
requested from a platform and their pinouts.


Resource definitions
====================

.. autoclass:: Resource
.. autoclass:: Subsignal


Pin definitions
===============
.. autoclass:: Pins
.. autoclass:: PinsN
.. autoclass:: DiffPairs
.. autoclass:: DiffPairsN


Resource helpers
================
.. autoclass:: Connector
.. autoclass:: Attrs
.. autoclass:: Clock
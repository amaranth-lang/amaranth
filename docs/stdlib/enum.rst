Enumerations
############

.. py:module:: amaranth.lib.enum

The :mod:`amaranth.lib.enum` module is a drop-in replacement for the standard :mod:`enum` module that provides extended :class:`Enum`, :class:`IntEnum`, :class:`Flag`, and :class:`IntFlag` classes with the ability to specify a shape explicitly.

A shape can be specified for an enumeration with the ``shape=`` keyword argument:

.. testsetup::

   from amaranth import *

.. testcode::

   from amaranth.lib import enum

   class Funct4(enum.Enum, shape=4):
       ADD = 0
       SUB = 1
       MUL = 2

.. doctest::

   >>> Shape.cast(Funct4)
   unsigned(4)

This module is a drop-in replacement for the standard :mod:`enum` module, and re-exports all of its members (not just the ones described below). In an Amaranth project, all ``import enum`` statements may be replaced with ``from amaranth.lib import enum``.


Metaclass
=========

.. autoclass:: EnumMeta()


Base classes
============

.. autoclass:: Enum()
.. autoclass:: IntEnum()
.. autoclass:: Flag()
.. autoclass:: IntFlag()

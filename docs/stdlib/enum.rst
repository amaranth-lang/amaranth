Enumerations
############

.. py:module:: amaranth.lib.enum

The :mod:`amaranth.lib.enum` module is a drop-in replacement for the standard :mod:`enum` module that provides extended :class:`Enum`, :class:`IntEnum`, :class:`Flag`, and :class:`IntFlag` classes with the ability to specify a shape explicitly.

A shape can be specified for an enumeration with the ``shape=`` keyword argument:

.. testsetup::

   from amaranth import *

.. testcode::

   from amaranth.lib import enum

   class Funct(enum.Enum, shape=4):
       ADD = 0
       SUB = 1
       MUL = 2

.. doctest::

   >>> Shape.cast(Funct)
   unsigned(4)

Any :ref:`constant-castable <lang-constcasting>` expression can be used as the value of a member:

.. testcode::

   class Op(enum.Enum, shape=1):
       REG = 0
       IMM = 1

   class Instr(enum.Enum, shape=5):
       ADD  = Cat(Funct.ADD, Op.REG)
       ADDI = Cat(Funct.ADD, Op.IMM)
       SUB  = Cat(Funct.SUB, Op.REG)
       SUBI = Cat(Funct.SUB, Op.IMM)
       ...

.. doctest::

   >>> Instr.SUBI
   <Instr.SUBI: 17>

The ``shape=`` argument is optional. If not specified, classes from this module behave exactly the same as classes from the standard :mod:`enum` module, and likewise, this module re-exports everything exported by the standard :mod:`enum` module.

.. testcode::

   import amaranth.lib.enum

   class NormalEnum(amaranth.lib.enum.Enum):
       SPAM = 0
       HAM  = 1

In this way, this module is a drop-in replacement for the standard :mod:`enum` module, and in an Amaranth project, all ``import enum`` statements may be replaced with ``from amaranth.lib import enum``.


Metaclass
=========

.. autoclass:: EnumMeta()


Base classes
============

.. autoclass:: Enum()
.. autoclass:: IntEnum()
.. autoclass:: Flag()
.. autoclass:: IntFlag()

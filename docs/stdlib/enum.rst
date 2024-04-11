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
   >>> Value.cast(Funct.ADD)
   (const 4'd0)

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

Signals with :class:`Enum` or :class:`Flag` based shape are automatically wrapped in the :class:`EnumView` or :class:`FlagView` value-like wrappers, which ensure type safety. Any :ref:`value-like <lang-valuelike>` can also be explicitly wrapped in a view class by casting it to the enum type:

.. doctest::

   >>> a = Signal(Funct)
   >>> b = Signal(Op)
   >>> type(a)
   <class 'amaranth.lib.enum.EnumView'>
   >>> a == b
   Traceback (most recent call last):
     File "<stdin>", line 1, in <module>
   TypeError: an EnumView can only be compared to value or other EnumView of the same enum type
   >>> c = Signal(4)
   >>> type(Funct(c))
   <class 'amaranth.lib.enum.EnumView'>

Like the standard Python :class:`enum.IntEnum` and :class:`enum.IntFlag` classes, the Amaranth :class:`IntEnum` and :class:`IntFlag` classes are loosely typed and will not be subject to wrapping in view classes:

.. testcode::

   class TransparentEnum(enum.IntEnum, shape=unsigned(4)):
       FOO = 0
       BAR = 1

.. doctest::

   >>> a = Signal(TransparentEnum)
   >>> type(a) is Signal
   True

It is also possible to define a custom view class for a given enum:

.. testcode::

   class InstrView(enum.EnumView):
       def has_immediate(self):
           return (self == Instr.ADDI) | (self == Instr.SUBI)

   class Instr(enum.Enum, shape=5, view_class=InstrView):
       ADD  = Cat(Funct.ADD, Op.REG)
       ADDI = Cat(Funct.ADD, Op.IMM)
       SUB  = Cat(Funct.SUB, Op.REG)
       SUBI = Cat(Funct.SUB, Op.IMM)

.. doctest::

   >>> a = Signal(Instr)
   >>> type(a)
   <class 'InstrView'>
   >>> a.has_immediate()
   (| (== (sig a) (const 5'd16)) (== (sig a) (const 5'd17)))

Metaclass
=========

.. autoclass:: EnumType()


Base classes
============

.. autoclass:: Enum()
.. autoclass:: IntEnum()
.. autoclass:: Flag()
.. autoclass:: IntFlag()

View classes
============

.. autoclass:: EnumView()
.. autoclass:: FlagView()
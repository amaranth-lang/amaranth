First-in first-out queues
#########################

.. py:module:: amaranth.lib.fifo

The ``amaranth.lib.fifo`` module provides building blocks for first-in, first-out queues.


.. autoclass:: FIFOInterface

   .. note::

      The :class:`FIFOInterface` class can be used directly to substitute a FIFO in tests, or inherited from in a custom FIFO implementation.

.. autoclass:: SyncFIFO(*, width, depth, fwft=True)
.. autoclass:: SyncFIFOBuffered(*, width, depth)
.. autoclass:: AsyncFIFO(*, width, depth, r_domain="read", w_domain="write", exact_depth=False)
.. autoclass:: AsyncFIFOBuffered(*, width, depth, r_domain="read", w_domain="write", exact_depth=False)

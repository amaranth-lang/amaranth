Migen and nMigen compatibility summary
======================================

nMigen intends to provide as close to 100% compatibility to Migen as possible without compromising its other goals. However, Migen widely uses `*` imports, tends to expose implementation details, and in general does not have a well-defined interface. This document attempts to elucidate a well-defined Migen API surface (including, when necessary, private items that have been used downstream), and describes the intended nMigen replacements and their implementation status.

API change legend:
  - *id*: identical
  - *obs*: removed or incompatibly changed with compatibility stub provided
  - *obs →n*: removed or incompatibly changed with compatibility stub provided, use *n* instead
  - *brk*: removed or incompatibly changed with no replacement provided
  - *brk →n*: removed or incompatibly changed with no replacement provided, use *n* instead
  - *→n*: renamed to *n*
  - *⇒m*: merged into *m*
  - *a=→b=*: parameter *a* renamed to *b*
  - *a=∼*: parameter *a* removed
  - *.a=→.b*: attribute *a* renamed to *b*
  - *.a=∼*: attribute *a* removed
  - *?*: no decision made yet

When describing renames or replacements, `mod` refers to a 3rd-party package `mod` (no nMigen implementation provided), `.mod.item` refers to `nmigen.mod.item`, and "(import `.item`)" means that, while `item` is provided under `nmigen.mod.item`, it is aliased to, and should be imported from a shorter path for readability.

Status legend:
  - (−) No decision yet, or no replacement implemented
  - (+) Implemented replacement (the API and/or compatibility shim are provided)
  - (⊕) Verified replacement and/or compatibility shim (the compatibility shim is manually reviewed and/or has 100% test coverage)
  - (⊙) No direct replacement or compatibility shim is provided

Compatibility summary
---------------------

  - (−) `fhdl` → `.hdl`
    - (⊕) `bitcontainer` ⇒ `.tools`
      - (⊕) `log2_int` id
      - (⊕) `bits_for` id
      - (⊕) `value_bits_sign` → `Value.shape`
    - (⊕) `conv_output` **obs**
    - (⊕) `decorators` ⇒ `.hdl.xfrm`
      <br>Note: `transform_*` methods not considered part of public API.
      - (⊙) `ModuleTransformer` **brk**
      - (⊙) `ControlInserter` **brk**
      - (⊕) `CEInserter` → `EnableInserter`
      - (⊕) `ResetInserter` id
      - (⊕) `ClockDomainsRenamer` → `DomainRenamer`, `cd_remapping=`→`domain_map=`
    - (⊙) `edif` **brk**
    - (⊕) `module` **obs** → `.hdl.dsl`
      <br>Note: any class inheriting from `Module` in oMigen should inherit from `Elaboratable` in nMigen and use an nMigen `Module` in its `.elaborate()` method.
      - (⊕) `FinalizeError` **obs**
      - (⊕) `Module` **obs** → `.hdl.dsl.Module`
    - (⊙) `namer` **brk**
    - (⊙) `simplify` **brk**
    - (⊕) `specials` **obs**
      - (⊙) `Special` **brk**
      - (⊕) `Tristate` **obs**
      - (⊕) `TSTriple` **obs** → `.lib.io.Pin`
      - (⊕) `Instance` → `.hdl.ir.Instance`
      - (⊕) `Memory` id
        <br>Note: nMigen memories should not be added as submodules.
        - (⊕) `.get_port` **obs** → `.read_port()` + `.write_port()`
      - (⊕) `_MemoryPort` **obs** → `.hdl.mem.ReadPort` + `.hdl.mem.WritePort`
      - (⊕) `READ_FIRST`/`WRITE_FIRST` **obs**
        <br>Note: `READ_FIRST` corresponds to `mem.read_port(transparent=False)`, and `WRITE_FIRST` to `mem.read_port(transparent=True)`.
      - (⊙) `NO_CHANGE` **brk**
        <br>Note: in designs using `NO_CHANGE`, replace it with logic implementing required semantics explicitly, or with a different mode.
    - (⊕) `structure` → `.hdl.ast`
      - (⊕) `DUID` id
      - (⊕) `_Value` → `Value`
        <br>Note: values no longer valid as keys in `dict` and `set`; use `ValueDict` and `ValueSet` instead.
      - (⊕) `wrap` → `Value.cast`
      - (⊕) `_Operator` → `Operator`, `op=`→`operator=`, `.op`→`.operator`
      - (⊕) `Mux` id
      - (⊕) `_Slice` → `Slice` id
      - (⊕) `_Part` → `Part` id
      - (⊕) `Cat` id, `.l`→`.parts`
      - (⊕) `Replicate` → `Repl`, `v=`→`value=`, `n=`→`count=`, `.v`→`.value`, `.n`→`.count`
      - (⊕) `Constant` → `Const`, `bits_sign=`→`shape=`, `.nbits`→`.width`
      - (⊕) `Signal` id, `bits_sign=`→`shape=`, `attr=`→`attrs=`, `name_override=`∼, `related=`, `variable=`∼, `.nbits`→`.width`
      - (⊕) `ClockSignal` id, `cd=`→`domain=`, `.cd`→`.domain`
      - (⊕) `ResetSignal` id, `cd=`→`domain=`, `.cd`→`.domain`
      - (⊕) `_Statement` → `Statement`
      - (⊕) `_Assign` → `Assign`, `l=`→`lhs=`, `r=`→`rhs=`
      - (⊕) `_check_statement` **obs** → `Statement.cast`
      - (⊕) `If` **obs** → `.hdl.dsl.Module.If`
      - (⊕) `Case` **obs** → `.hdl.dsl.Module.Switch`
      - (⊕) `_ArrayProxy` → `.hdl.ast.ArrayProxy`, `choices=`→`elems=`, `key=`→`index=`
      - (⊕) `Array` id
      - (⊕) `ClockDomain` → `.hdl.cd.ClockDomain`
      - (⊙) `_ClockDomainList` **brk**
      - (⊙) `SPECIAL_INPUT`/`SPECIAL_OUTPUT`/`SPECIAL_INOUT` **brk**
      - (⊙) `_Fragment` **brk** → `.hdl.ir.Fragment`
    - (⊙) `tools` **brk**
      - (⊙) `insert_resets` **brk** → `.hdl.xfrm.ResetInserter`
      - (⊙) `rename_clock_domain` **brk** → `.hdl.xfrm.DomainRenamer`
    - (⊙) `tracer` **brk**
      - (⊕) `get_var_name` → `.tracer.get_var_name`
      - (⊙) `remove_underscore` **brk**
      - (⊙) `get_obj_var_name` **brk**
      - (⊙) `index_id` **brk**
      - (⊙) `trace_back` **brk**
    - (⊙) `verilog`
      - (⊙) `DummyAttrTranslate` ?
      - (⊕) `convert` **obs** → `.back.verilog.convert`
    - (⊙) `visit` **brk** → `.hdl.xfrm`
      - (⊙) `NodeVisitor` **brk**
      - (⊙) `NodeTransformer` **brk** → `.hdl.xfrm.ValueTransformer`/`.hdl.xfrm.StatementTransformer`
  - (−) `genlib` → `.lib`
    - (−) `cdc` ?
      - (⊙) `MultiRegImpl` **brk**
      - (⊕) `MultiReg` → `.lib.cdc.FFSynchronizer`
      - (−) `PulseSynchronizer` ?
      - (−) `BusSynchronizer` ?
      - (⊕) `GrayCounter` **obs** → `.lib.coding.GrayEncoder`
      - (⊕) `GrayDecoder` **obs** → `.lib.coding.GrayDecoder`
        <br>Note: `.lib.coding.GrayEncoder` and `.lib.coding.GrayDecoder` are purely combinatorial.
      - (−) `ElasticBuffer` ?
      - (−) `lcm` ?
      - (−) `Gearbox` ?
    - (⊕) `coding` id
      - (⊕) `Encoder` id
      - (⊕) `PriorityEncoder` id
      - (⊕) `Decoder` id
      - (⊕) `PriorityDecoder` id
    - (−) `divider` ?
      - (−) `Divider` ?
    - (⊕) `fifo` → `.lib.fifo`
      - (⊕) `_FIFOInterface` → `FIFOInterface`
      - (⊕) `SyncFIFO` id, `.replace=`∼
      - (⊕) `SyncFIFOBuffered` id, `.fifo=`∼
      - (⊕) `AsyncFIFO` ?
      - (⊕) `AsyncFIFOBuffered`, `.fifo=`∼
    - (⊕) `fsm` **obs**
      <br>Note: FSMs are a part of core nMigen DSL; however, not all functionality is provided. The compatibility shim is a complete port of Migen FSM module.
    - (⊙) `io` **brk**
      <br>Note: all functionality in this module is a part of nMigen platform system.
    - (−) `misc` ?
      - (−) `split` ?
      - (−) `displacer` ?
      - (−) `chooser` ?
      - (−) `timeline` ?
      - (−) `WaitTimer` ?
      - (−) `BitSlip` ?
    - (⊕) `record` **obs** → `.hdl.rec.Record`
      <br>Note: nMigen uses a `Layout` object to represent record layouts.
      - (⊕) `DIR_NONE` id
      - (⊕) `DIR_M_TO_S` → `DIR_FANOUT`
      - (⊕) `DIR_S_TO_M` → `DIR_FANIN`
      - (⊕) `Record` id
      - (⊙) `set_layout_parameters` **brk**
      - (⊙) `layout_len` **brk**
      - (⊙) `layout_get` **brk**
      - (⊙) `layout_partial` **brk**
    - (⊕) `resetsync` **obs**
      - (⊕) `AsyncResetSynchronizer` **obs** → `.lib.cdc.ResetSynchronizer`
    - (−) `roundrobin` ?
      - (−) `SP_WITHDRAW`/`SP_CE` ?
      - (−) `RoundRobin` ?
    - (−) `sort` ?
      - (−) `BitonicSort` ?
  - (⊕) `sim` **obs** → `.back.pysim`
    <br>Note: only items directly under `nmigen.compat.sim`, not submodules, are provided.
    - (⊙) `core` **brk**
    - (⊙) `vcd` **brk** → `vcd`
    - (⊙) `Simulator` **brk**
    - (⊕) `run_simulation` **obs** → `.back.pysim.Simulator`
    - (⊕) `passive` **obs** → `.hdl.ast.Passive`
  - (⊙) `build` **brk**
    <br>Note: the build system has been completely redesigned in nMigen.
  - (⊙) `util` **brk**

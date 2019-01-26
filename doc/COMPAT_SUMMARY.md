Migen and nMigen compatibility summary
======================================

nMigen intends to provide as close to 100% compatibility to Migen as possible without compromising its other goals. However, Migen widely uses `*` imports, tends to expose implementation details, and in general does not have a well-defined interface. This document attempts to elucidate a well-defined Migen API surface (including, when necessary, private items that have been used downstream), and describes the intended nMigen replacements and their implementation status.

API change legend:
  - *id*: identical
  - *obs*: removed or irreversibly changed with compatibility stub provided
  - *obs →n*: removed or irreversibly changed with compatibility stub provided, use *n* instead
  - *brk*: removed or irreversibly changed with no replacement provided
  - *brk →n*: removed or irreversibly changed with no replacement provided, use *n* instead
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
    - (+) `bitcontainer` ⇒ `.tools`
      - (+) `log2_int` id
      - (+) `bits_for` id
      - (+) `value_bits_sign` → `Value.shape`
    - (−) `conv_output` ?
    - (+) `decorators` ⇒ `.hdl.xfrm`
      <br>Note: `transform_*` methods not considered part of public API.
      - (⊙) `ModuleTransformer` **brk**
      - (⊙) `ControlInserter` **brk**
      - (-) `CEInserter` **obs**
      - (-) `ResetInserter` **obs**
      - (+) `ClockDomainsRenamer` → `DomainRenamer`, `cd_remapping=`→`domain_map=`
    - (⊙) `edif` **brk**
    - (+) `module` **obs** → `.hdl.dsl`
      - (+) `FinalizeError` **obs**
      - (+) `Module` **obs** → `.hdl.dsl.Module`
    - (⊙) `namer` **brk**
    - (−) `simplify` ?
      - (−) `FullMemoryWE` ?
      - (−) `MemoryToArray` ?
      - (−) `SplitMemory` ?
    - (⊕) `specials` **obs**
      - (⊙) `Special` **brk**
      - (⊕) `Tristate` → `.lib.io.Tristate`, `target=`→`io=`
      - (⊕) `TSTriple` → `.lib.io.TSTriple`, `bits_sign=`→`shape=`
      - (⊕) `Instance` → `.hdl.ir.Instance`
      - (⊕) `Memory` id
        - (⊕) `.get_port` **obs** → `.read_port()` + `.write_port()`
      - (⊕) `_MemoryPort` **obs**
        <br>Note: nMigen separates read and write ports.
      - (⊕) `READ_FIRST`/`WRITE_FIRST` **obs**
        <br>Note: `READ_FIRST` corresponds to `mem.read_port(transparent=False)`, and `WRITE_FIRST` to `mem.read_port(transparent=True)`.
      - (⊙) `NO_CHANGE` **brk**
        <br>Note: in designs using `NO_CHANGE`, repalce it with an asynchronous read port and logic implementing required semantics explicitly.
    - (−) `structure` → `.hdl.ast`
      - (+) `DUID` id
      - (+) `_Value` → `Value`
        <br>Note: values no longer valid as keys in `dict` and `set`; use `ValueDict` and `ValueSet` instead.
      - (+) `wrap` → `Value.wrap`
      - (+) `_Operator` → `Operator`
      - (+) `Mux` id
      - (+) `_Slice` → `Slice`, `stop=`→`end=`, `.stop`→`.end`
      - (+) `_Part` → `Part`
      - (+) `Cat` id, `.l`→`.parts`
      - (+) `Replicate` → `Repl`, `v=`→`value=`, `n=`→`count=`, `.v`→`.value`, `.n`→`.count`
      - (+) `Constant` → `Const`, `bits_sign=`→`shape=`
      - (+) `Signal` id, `bits_sign=`→`shape=`, `attr=`→`attrs=`, `name_override=`∼, `related=`, `variable=`∼
      - (+) `ClockSignal` id, `cd=`→`domain=`
      - (+) `ResetSignal` id, `cd=`→`domain=`
      - (+) `_Statement` → `Statement`
      - (+) `_Assign` → `Assign`, `l=`→`lhs=`, `r=`→`rhs=`
      - (+) `_check_statement` **obs** → `Statement.wrap`
      - (+) `If` **obs** → `.hdl.dsl.Module.If`
      - (+) `Case` **obs** → `.hdl.dsl.Module.Switch`
      - (+) `_ArrayProxy` → `.hdl.ast.ArrayProxy`, `choices=`→`elems=`, `key=`→`index=`
      - (+) `Array` id
      - (+) `ClockDomain` → `.hdl.cd.ClockDomain`
      - (−) `_ClockDomainList` ?
      - (−) `SPECIAL_INPUT`/`SPECIAL_OUTPUT`/`SPECIAL_INOUT` ?
      - (⊙) `_Fragment` **brk** → `.hdl.ir.Fragment`
    - (−) `tools` **brk**
      - (−) `list_signals` ?
      - (−) `list_targets` ?
      - (−) `list_inputs` ?
      - (−) `group_by_targets` ?
      - (⊙) `list_special_ios` **brk**
      - (⊙) `list_clock_domains_expr` **brk**
      - (−) `list_clock_domains` ?
      - (−) `is_variable` ?
      - (⊙) `generate_reset` **brk**
      - (⊙) `insert_reset` **brk**
      - (⊙) `insert_resets` **brk** → `.hdl.xfrm.ResetInserter`
      - (⊙) `lower_basics` **brk**
      - (⊙) `lower_complex_slices` **brk**
      - (⊙) `lower_complex_parts` **brk**
      - (⊙) `rename_clock_domain_expr` **brk**
      - (⊙) `rename_clock_domain` **brk** → `.hdl.xfrm.DomainRenamer`
      - (⊙) `call_special_classmethod` **brk**
      - (⊙) `lower_specials` **brk**
    - (−) `tracer` **brk**
      - (−) `get_var_name` ?
      - (−) `remove_underscore` ?
      - (−) `get_obj_var_name` ?
      - (−) `index_id` ?
      - (−) `trace_back` ?
    - (−) `verilog`
      - (−) `DummyAttrTranslate` ?
      - (−) `convert` **obs** → `.back.verilog.convert`
    - (⊙) `visit` **brk** → `.hdl.xfrm`
      - (⊙) `NodeVisitor` **brk**
      - (⊙) `NodeTransformer` **brk** → `.hdl.xfrm.ValueTransformer`/`.hdl.xfrm.StatementTransformer`
  - (−) `genlib` → `.lib`
    - (−) `cdc` ?
      - (−) `MultiRegImpl` ?
      - (⊕) `MultiReg` id
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
    - (−) `fifo` ?
      - (⊕) `_FIFOInterface` → `FIFOInterface`
      - (⊕) `SyncFIFO` id, `.fifo=`∼
      - (⊕) `SyncFIFOBuffered` id, `.fifo=`∼
      - (−) `AsyncFIFO` ?
      - (−) `AsyncFIFOBuffered` ?
    - (+) `fsm` **obs**
      - (+) `AnonymousState` **obs**
      - (+) `NextState` **obs**
      - (+) `NextValue` **obs**
      - (+) `_LowerNext` **obs**
      - (+) `FSM` **obs**
    - (−) `io` ?
      - (−) `DifferentialInput` ?
      - (−) `DifferentialOutput` ?
      - (−) `CRG` ?
      - (−) `DDRInput` ?
      - (−) `DDROutput` ?
    - (−) `misc` ?
      - (−) `split` ?
      - (−) `displacer` ?
      - (−) `chooser` ?
      - (−) `timeline` ?
      - (−) `WaitTimer` ?
      - (−) `BitSlip` ?
    - (−) `record` **obs** → `.hdl.rec.Record`
      - (−) `DIR_NONE` id
      - (−) `DIR_M_TO_S` → `DIR_FANOUT`
      - (−) `DIR_S_TO_M` → `DIR_FANIN`
      - (−) `set_layout_parameters` **brk**
      - (−) `layout_len` **brk**
      - (−) `layout_get` **brk**
      - (−) `layout_partial` **brk**
      - (−) `Record` id
    - (+) `resetsync` ?
      - (+) `AsyncResetSynchronizer` **obs** → `.lib.cdc.ResetSynchronizer`
    - (−) `roundrobin` ?
      - (−) `SP_WITHDRAW`/`SP_CE` ?
      - (−) `RoundRobin` ?
    - (−) `sort` ?
      - (−) `BitonicSort` ?
  - (-) `sim` **obs** → `.back.pysim`
    <br>Note: only items directly under `nmigen.compat.sim`, not submodules, are provided.
    - (⊙) `core` **brk**
    - (⊙) `vcd` **brk** → `vcd`
    - (⊙) `Simulator` **brk**
    - (⊕) `run_simulation` **obs** → `.back.pysim.Simulator`
    - (⊕) `passive` **obs** → `.hdl.ast.Passive`
  - (−) `build` ?
  - (+) `util` **obs**
    - (+) `misc` ⇒ `.tools`
      - (+) `flat_iteration` → `.flatten`
      - (⊙) `xdir` **brk**
      - (⊙) `gcd_multiple` **brk**
    - (⊙) `treeviz` **brk**

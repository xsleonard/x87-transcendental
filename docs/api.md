# C API and supported scope

Include `x87trans/x87trans.h` and link `x87trans::x87trans`. The library currently
identifies itself as `skylake-numerical-preview`, version 0.1.0. Its eight named
functions use one raw80 representation, one control structure and one result
structure. The ABI is a preview and is not yet frozen for a 1.0 release.

`x87t_create` initializes immutable GMP constants. Share the context across
threads after creation; each call owns its evaluation temporaries. Destroy it
only after all callers finish. A NULL allocation result is possible; GMP's own
allocator failure policy still applies. No guest controls, flags, counters or
scratch values are stored in process-global or thread-local variables.

Raw80 is the original sign/exponent word plus its explicit 64-bit significand.
Do not normalize inputs before calling. The struct may contain padding: use
`x87t_load_le` and `x87t_store_le` with valid ten-byte buffers for memory access.
Those helpers preserve unsupported encodings and NaN payloads exactly.

All evaluation calls require non-NULL context, control and output pointers.
Binary order is `y = ST(1)`, `x = ST(0)`. RC is RN/RD/RU/RZ; accepted precision
controls are 24, 53 and 64 significand bits. Internal precision cuts remain fixed
by each numerical program, independently of guest PC. Only the all-masked value
`exception_masks = 0x3f` is supported. Other masks are rejected explicitly.

| Return | Meaning |
| --- | --- |
| `X87T_OK` | Modeled numerical evaluation, including range return or masked arithmetic exceptions |
| `X87T_BAD_ARGUMENT` | Invalid pointer or rounding enum |
| `X87T_UNSUPPORTED_CONTROL` | Unsupported precision or exception masks |
| `X87T_OUTSIDE_SCOPE` | Operand behavior not supplied by this preview |

Errors leave the output structure unchanged. Arithmetic IE/DE/ZE/OE/UE/PE are
reported inside a successful result when that instruction implements them.

The result fields have the following interpretation:

- `values` marks which of `primary` and `pushed` may be used. FSINCOS returns
  sine as primary and cosine as pushed. FPTAN returns tangent and its actual
  modeled pushed value, including copied NaN/indefinite results.
- `exceptions` contains newly raised arithmetic flags in x87 bit positions 0..5.
  `exceptions_known` identifies the implemented bits. **An unknown bit is not a
  predicted zero.** The caller must supply missing semantics before committing
  guest state or use a supported implementation for that case.
- `cc` contains applicable condition bits. `cc_known` marks implemented metadata,
  not the architecture's defined-bit mask. In particular, paired C1 is the
  final external cosine lane's magnitude increment, not the OR of both lanes.
- `completion` is ordinary completion or a C2 range return. The latter has no
  valid new numerical fields and `destination = X87T_NO_WRITE`; preserve the
  original operand and stack.
- `destination` describes the normal caller-side operation: replace ST(0),
  replace old ST(0) and push, or replace ST(1) and pop. It does not perform it.

| Instruction | Available metadata | Current operand limits |
| --- | --- | --- |
| FSIN, FCOS | Numerical value, C1 and C2; arithmetic flags unknown | Current raw80 special-value and finite programs; C2 range return retained |
| FSINCOS | Both values, C2; C1 on finite numerical paths, special C1 unknown; arithmetic flags unknown | Independent paired program, with original special and range handling |
| FPTAN | Both values and C2; C1 and arithmetic flags unknown | Unsupported raw encodings return OUTSIDE_SCOPE; normal/special numerical program retained |
| F2XM1 | Value; C1 for finite results; arithmetic flags unknown | Unsupported raw encodings return OUTSIDE_SCOPE; original outside-[-1,1] identity behavior retained as profile behavior, not an architectural guarantee |
| FPATAN | Value, C1, all six masked arithmetic flags | Existing raw80 class handling and masked numerical contract |
| FYL2X | Value, C1, all six masked arithmetic flags | Existing zero/negative/infinite/NaN rules and finite program |
| FYL2XP1 | Value, C1, all six masked arithmetic flags | Existing finite domain: absolute x at most `1-sqrt(1/2)`; endpoint raw80 `3ffd:95f619980c4336f7`; other finite x/infinite x return OUTSIDE_SCOPE after special-operand priority |

The original binary-family status contract assumes valid stack operands and
clear initial exception latches. Existing sticky status and pending exceptions
are caller responsibilities. This release does not add mask-dependent endpoints,
unmasked fault delivery, stack fault priority, physical pointers or save/restore
state behavior. See the preserved [semantics implementation plan](../research/fsincos-re/docs/EMULATION-LIBRARY-PLAN.md)
for those separate tasks.

No function calls a host transcendental instruction or host libm to compute an
answer. The normal runtime uses integer arithmetic and GMP, with no files,
network access, environment-variable algorithm choices or diagnostic output.
Internal assertions and GMP invariant checks remain; the extraction does not
promise recoverable resource exhaustion or claim exhaustive input validation.

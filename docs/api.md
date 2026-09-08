# C API and supported scope

Include `x87trans/x87trans.h` and link `x87trans::x87trans`. Version 0.2.0
identifies the profile as `skylake-emulation-preview`. The eight functions use
one raw80 representation, control structure and result structure. The ABI is
provisional; recompile consumers when updating from 0.1.

`x87t_create` initializes immutable GMP constants. A context can be shared across
threads; each call owns its temporaries. Destroy it after all calls finish.
Creation can return NULL; GMP's allocator failure policy also applies. There is
no mutable process-global or thread-local evaluation state.

Raw80 contains the original sign/exponent word and explicit 64-bit significand.
Preserve the original encoding: normalizing before evaluation loses distinctions
between denormals, pseudo-denormals and unsupported operands. Struct padding is
not serialized. Use `x87t_load_le` and `x87t_store_le` with valid ten-byte buffers.

Every evaluation requires context, control and output pointers. Binary order is
`y = ST(1), x = ST(0)`. RC accepts RN/RD/RU/RZ, PC accepts 24/53/64, and all 64
combinations of exception masks are supported. A set mask bit suppresses that
exception's trap. Fixed internal precision cuts remain independent of guest PC.

| Return | Meaning |
| --- | --- |
| `X87T_OK` | An arithmetic outcome, including exceptions and range returns |
| `X87T_BAD_ARGUMENT` | Invalid pointer or rounding enum |
| `X87T_UNSUPPORTED_CONTROL` | Invalid precision or mask bits outside 0..5 |
| `X87T_OUTSIDE_SCOPE` | Numerical domain excluded from this profile |

Errors leave the output unchanged. Arithmetic exceptions are successful API
results, never host signals, C exceptions or error returns.

## Results and architectural effects

`exceptions` contains newly raised IE/DE/ZE/OE/UE/PE in x87 bit positions 0..5;
`exceptions_known` is `0x3f` on every successful call. Flags describe the selected
masked or unmasked execution, including suppression of later exceptions after
an early fault. `first_unmasked` identifies the selected newly unmasked exception,
or zero. Existing sticky flags and pending exceptions are not inputs to this API.

`cc` and `cc_known` describe condition updates. All instructions provide C1;
FSIN/FCOS/FSINCOS/FPTAN also provide C2. A range return provides only C2, leaving
undefined C1 to the caller's policy. Other condition bits are outside this
contract. C1 comes from the final modeled rounding step, including paired
FSINCOS's external cosine lane; it is not inferred from the sign of the error
or by comparing multiple rounded evaluations.

| `completion` | Register/stack action |
| --- | --- |
| `X87T_COMPLETE` | Apply `destination`; any reported exceptions are masked |
| `X87T_RANGE_RETURN` | Preserve all registers and stack, set C2 |
| `X87T_UNMASKED_NO_WRITE` | Merge flags/condition updates and suppress every result write, push and pop |
| `X87T_UNMASKED_WRITE` | Merge flags/condition updates and apply `destination`, with an exception pending |

Unmasked IE/DE/ZE stop before result writeback. Register overflow, underflow and
precision can commit before pending exception delivery. Unmasked overflow and
underflow use exponent-adjusted register results: the retained result is scaled
by `2^-24576` or `2^24576` before final rounding. Scaling a masked infinity or zero
would lose the required result and is not equivalent.

`values` marks valid `primary`/`pushed` fields. `destination` requests replacement
of ST(0), replacement of old ST(0) followed by a push, or replacement of ST(1)
followed by a pop. FSINCOS primary is sine and pushed is cosine. FPTAN returns
its actual pushed value, including copied NaNs/indefinites in special cases.
Suppressed writes and range returns have `values = 0` and `X87T_NO_WRITE`.

## Special operands and numerical limits

Quiet NaNs propagate without IE; signaling NaNs request IE and produce a
quieted result only if invalid is masked. Unsupported raw80 encodings request
IE and produce the negative indefinite when masked. Binary selection preserves
the modeled quiet/signaling precedence, payload and sign rules. These are x87
profile rules; replacing every NaN with a canonical host NaN is insufficient.

| Instructions | Accepted scope |
| --- | --- |
| FSIN, FCOS, FSINCOS, FPTAN | Raw80 finite and special operands; finite magnitudes at least `2^63` return C2 without writing |
| F2XM1 | Raw80 finite and NaN/unsupported operands; finite inputs outside `[-1,1]` retain the observed identity/PE profile behavior; infinities return OUTSIDE_SCOPE |
| FPATAN, FYL2X | Existing finite and raw80 special-value programs |
| FYL2XP1 | Finite `abs(x) <= 1-sqrt(1/2)`, endpoint `3ffd:95f619980c4336f7`; other finite/infinite x return OUTSIDE_SCOPE after NaN/unsupported priority |

F2XM1 outside `[-1,1]` and FYL2XP1 outside its defined domain have no architectural
numerical guarantee. The caller chooses its fallback policy on OUTSIDE_SCOPE.
See [validation](validation.md) for evidence and remaining confidence limits.

## Emulator responsibilities

Check existing pending exceptions and instruction-specific stack priority before
calling. The emulator owns physical registers, TOP, tags, sticky status, ES/B,
instruction/data pointers, CR0 behavior and deferred #MF/legacy IRQ delivery.
Merge flags and only the condition bits supplied by the result. Apply writes
according to completion, even when a late unmasked exception is pending. The
[Bochs integration](bochs.md) exercises this division through actual guest
instructions, FXSAVE and guest exception handlers.

The runtime uses integer arithmetic and GMP, without host transcendental
instructions, libm, files, network access or diagnostic output. Internal
assertions and GMP invariant checks remain. Recoverable allocation exhaustion
and exhaustive correctness over every raw80 encoding are not promised.

# H1644–H1647: encoding-class status and the underflow domain

2026-09-04. Analysis-only. No new hardware observation, private-ledger access,
manifest freeze, production/default change or paper/PDF edit. The goal is
still active/unachieved. This is progress toward full state semantics, not a
redefinition of success as masked numerical outputs alone.

## New result

The original 80-bit encoding class must survive numerical normalization.
It supplies a compact candidate for the six new exception flags. An exact
interval certificate also proves that, in the specified fixed numerical
program, only original true-denormal FSIN inputs can produce subnormal outputs.
This proof covers whole domains, not a selection of previously failing inputs.
The exception rule is checked retrospectively against retained observations;
it has not received a fresh prospective state campaign in this turn.

## H1644: the load is not the source of these exceptions

Intel SDM revision 089, Vol.1 §8.5.2 and the FLD entry, explicitly exempt
80-bit loads from denormal and signaling-NaN load exceptions. Vol.2A marks
C0/C3 undefined for FSIN/FCOS; FCOS also marks C1 undefined on C2. The FSIN
exception list on printed page 3-374 does not list underflow, despite the
retained observed UE flags. That omission cannot erase silicon evidence.
General underflow/precision handling appears in Vol.1 §§8.5.5–8.5.6.
Source: [Intel combined SDM](https://cdrdv2-public.intel.com/868137/325462-089-sdm-vol-1-2abcd-3abcd-4.pdf).
Local PDF: `tmp/pdfs/h1644-intel-sdm-089.pdf`, SHA256
`1eb81360c636a723fb34610a1deef276e98e1fc331ac08b380114079664add20`.
Relevant PDF pages are 236–238, 1019–1020, 1041–1042, 1069–1070; the FLD,
denormal and both instruction exception pages were visually inspected.

H1644 reauthenticates all 124 immutable H1401 raw state rows and their frozen
identities. Every pre-instruction raw operand equals the original encoding,
including unsupported formats, SNaNs and pseudo-denormals. Before arithmetic,
122 rows have exception mask 00; two intentionally seeded rows have 01.
The three known PE seed failures, A002/A005/A024, remain failures. They are
not recaptured or credited with sticky-PE coverage. The 24 previously declared
architecture relations reproduce, with the old overflow row's deliberately
unpredicted response still not converted into a prediction.

The six special paired rows A008–A013 have zero flags after FLDT, before
FSINCOS. After the instruction they show QNaN=00, SNaN/infinity/unsupported=01,
true denormal=32, pseudo-denormal=22. This localizes those observed flags to
arithmetic rather than loading. It does not prove paired/standalone numerical
equivalence or recover a physical flag-generation micro-operation. H1641
separately supplies actual standalone special-value records.

A read-only check finds no `/root/h491/specials` archive on the Xeon. The
correct i7 142.132.217.24 still times out on port 22. These are limited archive
availability results, not a global blocker; local evidence work completed.
No old capture script was run, and no unrelated service was touched.

## H1645: class-based masked exception algebra

The analysis module `experiments/h1645_masked_status_model.py` classifies raw
sign/exponent/significand before normalization. Let E be the exponent field,
J the explicit integer bit, and S select standalone FSIN. For valid nonzero
finite in-range input, the candidate new exception mask is:

```text
0x20 | (0x02 if E == 0 else 0)
     | (0x10 if S and E == 0 and J == 0 else 0)
```

Thus a pseudo-denormal and its normal numerical counterpart cannot be merged
before flag generation. This is an encoding distinction, not an input-error
boundary fit. The exact-equal-value normal/pseudo-normal pair remains a useful
fresh prospective discriminator; it is not asserted captured here by analogy.

Unsupported encodings and infinity return indefinite with IE. SNaNs retain
sign/payload while setting the quiet bit and IE; QNaNs preserve their payload
without a new exception. Zero has its ordinary signed FSIN/+1 FCOS result;
out-of-range normal inputs retain their operand and set C2 without a new
exception. Prior exception flags and SF are sticky. The normal arithmetic/C1
comes from the unchanged H1638 program. Empty-stack masked response is an
architecture-constrained implementation with no new hardware credit here.

The module explicitly returns `status_bits` AND `status_known_mask`. It does
not fabricate physical C0/C3, C1 on range rejection, or C2 on exceptional/empty
inputs with an arbitrary initial C2. Unmasked exceptions, pending/error-summary
or busy state, and reserved PC reject the call instead of falling back to a
masked approximation. This interface is therefore NOT a complete physical-state
emulator. Unknown physical condition bits are still part of the actual goal.

An algebraic partition accounts for all 2^80 raw encodings in nine disjoint
classes. The counts sum exactly to 1208925819614629174706176. Separate Boolean
predicates agree on all exponent/sign combinations and all class-predicate
boundaries: 655,360 software checks. Another 1,536 software checks exercise
sticky/SF/TOP and empty/nonempty transitions. These prove properties of the
software classification/transition algebra, not silicon behavior on 2^80 inputs.

Retrospective results, with no changes to frozen H1641 predictions:

| Evidence | Checks | Result and scope |
| --- | ---: | --- |
| H1641 output/C2 + modeled status | 6,432 | All pass; only known status bits compared |
| H1641 exception masks | 6,432 | Includes 2,688 formerly unpredicted fields |
| H1641 modeled C1 | 6,048 | Includes 1,536 formerly unpredicted bits; range C1 unknown |
| H1637 mixed banks | 451,422 | Exception masks only; no new output/C1 credit |
| H1401 standalone raw states | 59 | Outputs, modeled SW, TOP/tags/deeper registers pass |

The newly checked fields are post-hoc checks, NOT prospective successes.
The broader mixed bank includes 18 actual signed smallest-normal observations:
FSIN returns the unchanged minimum normal; FCOS returns +1; flags are 20,
not underflow. This is retained evidence from both instructions' RN/RD/RU
and available FSIN RZ/PC24/53 settings, not FCOS RZ/PC at that exact operand.
The scalar C2 streams cannot establish retained ST0 bits absent from their
format; H1645 does not count such bits as observed.

## H1647: a whole-domain numerical enclosure, not fitting

All native polynomial coefficients, including the existing S4 correction,
have magnitude below 1. Every native table sine/cosine value lies between
1/4 and 1. The certificate verifies these conditions against the pinned ROM.
Chopped multiplies cannot increase magnitude. For RN64 additions/products,
use the deliberately loose bound rho=65/64; final 64-bit rounding preserves
at least eta=63/64 of a positive prevalue. Both enclose the actual quantizer
relative errors by wide margins, without using any observed labels.

For polynomial r<=1/4, square<=1/16 and fourth<=1/256. Exact rational interval
propagation bounds both Horner arms below 9/8 and both terminal correction
magnitudes below 1/8 (relative to r for sine). Cosine stays above 1/2 after
rounding. Polynomial sine, whose dispatcher has r>=2^-32, stays above 2^-33.

For table |a|<=1/16, square<=1/256. Both four-term Horner expressions remain
below 9/8. The total terminal correction stays below 1/8 against a ROM leading
value above 1/4. The final table magnitude therefore exceeds 1/16. The direct
RN64 table product is bounded separately, not replaced by a double-round.

Direct non-bypass tiny r is at least 2^-68. Reduced nonzero tiny r is at least
2^-65 because it is an integer multiple of 2^-65. A 64-bit predecessor is
at least half its leading value, so those outputs are at least 2^-69 and
2^-66 respectively. Exact reduced zero is excluded by the odd 66-bit M66
versus the external 64-bit significand. Every bound is far above 2^-16382.

Only the direct extreme-tiny bypass can return a subnormal: it returns x for
FSIN or 1 for FCOS. An original true denormal stays subnormal under FSIN;
normal and pseudo-denormal inputs remain normal. Hence the entire specified
numerical program has this subnormal-output criterion:

```text
FSIN and original exponent == 0 and original integer bit == 0
     and original significand != 0
```

This is an all-input numerical theorem conditional on the fixed graph and
its dispatcher/grid semantics. It is not proof that hardware generates UE by
examining the stored result, that the graph equals silicon on every input,
or that unmasked underflow shares the same output. It supports the structural
class rule while keeping the remaining physical claims separate.

## H1646: prepared next observable, not executed

`capture-kit/x87_masked_transition_capture.c` reuses the audited packing,
snapshot and single-instruction primitives, restores explicitly specified
condition/sticky bits using FXRSTOR, and verifies the full requested prestate
before executing exactly one FSIN or FCOS. It can mark ST0 empty while keeping
the raw register bytes and deeper stack controlled. No numerical PE seed is
needed. Restored x87/SSE registers are declared clobbered for compiler safety.

The x86-64 object cross-compiles locally with O2/Wall/Wextra/Werror and its
FXRSTOR/FXSAVE/call path was inspected. This is not a tested Linux capture
binary. No input bank or manifest exists, no private freshness audit was made,
and no hardware was executed. Before use: fresh architectural inputs, frozen
value/flag predictions and discriminator alternatives, target build/disassembly
checks, then the normal once-only guard. Never reuse H1641 tuples just to get
more status detail. Explicitly resolve any changed tuple-identity convention;
do not silently weaken the conservative freshness discipline.

The immediate useful challenges are normal/pseudo-denormal equal-value pairs,
initial C0/C1/C2/C3 patterns, and empty-stack priority. These address missing
state observables; they are not another search for a fitted arithmetic selector.
Unmasked exceptions and remaining exact-center/zero/infinity provenance remain
obligations, not dropped requirements.

## Verification anchors

| Artifact (relative to fsincos-re) | SHA256 |
| --- | --- |
| `tmp/ledger33/current/h1644_load_status_causal_audit/report.json` | `9b182fb2082fbfffc4554a551f056db8819fda9852fa134568eb9b3147ad7ded` |
| `experiments/h1645_masked_status_model.py` | `d00bbf0adf069be0e2553712c45df96eb1e457dfe74b8403e27b61f69eda0fc5` |
| `tmp/ledger33/current/h1645_masked_status_audit/report.json` | `29e14b55569b301ed161a2fbc378f7aa6b1deb9622c39e17f019b00cd52e6053` |
| `capture-kit/x87_masked_transition_capture.c` | `c718ded47f49a8a4d84532eb2d7eab9ec811bd52940806b97b56659ed961fddd` |
| `tmp/ledger33/current/h1647_underflow_domain_certificate/report.json` | `e559fcd4c56430f9297b64eb2a39c4d30d55dfee094f0ae7b89ec7181e8ae684` |

H1644/H1645/H1647 directories reproduce byte-for-byte under
`/private/tmp/h1644-h1647-root-replay.lOQfTN`. Python syntax, canonical build,
both emulator selftests, tracked diff and new-file whitespace checks pass.
Canonical source remains
`0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`.
No candidate arithmetic adjustment, production/default or paper/PDF edit.
The Intel PDF and renders are retained as source evidence, not paper revisions.
No new incumbent frontier census: documented direct50/48, external81/79 remains.
R96 remains empirical/incomplete in the incumbent; full goal is not closed.

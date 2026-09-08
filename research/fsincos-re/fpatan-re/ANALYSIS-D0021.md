# D0021: source-guided split-polynomial candidate V6

**Superseded by [D0022](ANALYSIS-D0022.md): complete V6 is falsified and not
promoted.** Its new failure localizes to table-midpoint selection at 19/64.
The discovery results below remain valid historical evidence.

**Discovery-exact, not yet a validated solution or promoted default.** V6
matches all **1,649,232 saved observations** across D0001–D0009 and D0013,
with zero output, C1, exception or pre-load-flag differences. Main C/library
remain V4. No paper or trig-source changes are made.

## Independent source evidence

The existing public Goldmont 506C9 dump contains all ten P5 atan coefficient
payloads, projected to 64 bits, consecutively at FP-ROM rows `0x12..0x1b`.
All 32 atan(n/32) payload projections also match at `0xf6..0x115`.
This is **42 exact payload projections**, not evidence of their low bits,
exponents or sign metadata.

The addressed long-polynomial block `U70ca..U70e4` reads rows
`1b,1a,19,18,17,16`. It uses two interleaved coefficient chains, with distinct
`0x649` and `0x6c9` sum opcodes, a distinct `0x661` square and `0x6e1`
products. The short block `U6d1e..U6d32` reads `14,15,12,13` and shares the
two-chain structure. The following table read uses index `0xf5 + tmp6`.
The long block transfers to `U6d39`, joining the common terminal path.

Primary sources, pinned and hash-verified:

- [Goldmont operation listing](https://github.com/chip-red-pill/uCodeDisasm/blob/ffc9070233a6e7a26dbabe723289259f087ee20b/ucode/ucode_glm.txt),
  SHA256 `46fb61bfaf174765c117de65b036b73ae4433b9c2b9871d5289fd02d4867067e`.
- [FP-ROM projection](https://github.com/pietroborrello/CustomProcessingUnit/blob/4237524fe7545c66e42dd986113f220662c06f6a/bios/dumps/rom.txt),
  SHA256 `87b9ee93e0c7a1f988906d8fd79d886590aa41a7368d06ef1954be8d5aca14db`.

This is a high-confidence arctangent-shaped routine, not a dynamically
confirmed architectural dispatch. Goldmont is not Skylake; its arithmetic
semantics and ROM low bits are not recovered by this static audit. The
Skylake numerical interpretation below remains a transfer hypothesis.

Two other primary-source leads were checked and not treated as target
microcode: [EP0738959A1](https://patents.google.com/patent/EP0738959A1/en)
is Motorola's arctangent method; [US6055553A](https://patents.google.com/patent/US6055553A/en)
is an individually assigned digit-recurrence design. Neither supplies an
Intel FPATAN operation schedule.

## Candidate numerical graph

Let `M(a,b)=CHOP67(a*b)`, `A(a,b)=RN64(a+b)`, `W(a,b)=CHOP67(a+b)`.
The existing quotient/reduction/quadrant hypotheses are retained. For reduced
z, form `u=RN64(z*CHOP64(z))` and `v=M(u,u)`.

Long direct polynomial:

```text
odd  = W(C119, M(v, A(C121, M(v, C123))))
even = W(C118, M(v, A(C120, M(v, C122))))
h    = A(M(u, odd), even)
tail = M(M(z, u), h)
kernel = z + tail
```

Short table polynomial:

```text
even = W(C114, M(v, C116))
odd  = A(C115, M(v, C117))
h    = A(M(u, odd), even)
tail = M(M(z, u), h)
kernel = z + tail
```

There is no operand ledger, fitted selector or per-input precision choice.
The operation-class difference is present in an independent public listing.
Earlier tree audits used uniform RN64 sums; the fixed interleaving plus
different sum classes was not covered by their negative conclusions.

`d0021_goldmont_fpatan_audit.py` parses raw register fields and executes these
source slices under the stated interpretation. Exact-mode polynomial
identities pass; slice/Python arithmetic agrees for all 285 frontier groups,
and all their output/C1 intervals match. Table sign/metadata operations are
not decoded: the slice check starts with already signed reduced z.

## Implementation and verification

- `graph_v6.py`: analysis-only Python graph.
- `fpatan_candidate_v6.c`: self-contained GMP C source, no algorithm flags.
  Main `fpatan_candidate.c` and its library are unchanged.
- `d0021-v6-full-corpus-replay.json`: authenticated C replay of all ten jobs,
  zero differences in every recorded output/status field.
- `d0021-v6-sanitizer-parity.json`: 9,844 C/Python comparisons, covering all
  frontier rows, samples from every job and synthetic sign/scale/RC/PC cases.
  All fields agree under address/undefined-behavior sanitizers.
- `d0021-goldmont-fpatan-audit.json`: source pins, all 42 projections,
  addressed operation slices and all 285 frontier comparisons.

All generated evidence lives in `../tmp/fpatan-re/`. These are discovery and
implementation checks, not prospective hardware proof. D0022 is the fresh
frozen challenge; inspect its actual receipts for state. Its inputs include
old-frontier neighborhoods, every table center/midpoint, independent direct,
table and cancellation ratios, tiny/bypass cases, signs/octants and wide
common exponent scales. No prior hardware tuple may be repeated.

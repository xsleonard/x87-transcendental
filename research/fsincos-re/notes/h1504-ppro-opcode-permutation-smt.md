# H1504: Pentium Pro cross-dword opcode-permutation wall

> **H1555 correction (2026-09-04):** this audit consumes H1467's now-falsified
> 19-eight-dword body partition. Its bounded result applies only to that
> mispartitioned dataset and does not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-03

Status: **exact non-inverting transfer rejection under a bounded opcode
condition; fixed-inversion query UNKNOWN; no logical decoder or selector.**

## Question

H1493 exhausts mappings obtained from the public later-P6 wiring by a global
eight-dword permutation, four conventional within-dword transforms, and the
two core orientations.  It does not cover a genuinely different cross-dword
bit permutation.  H1504 tests that remaining family at the opcode field
without assuming any dword boundary.

The audit keeps all nineteen recovered MSRAM lines for each patch.  It uses
the 248 physical channels `(dword 0..7, bit 0..30)` and excludes dword bit 31,
which the public later-P6 descrambler does not consume.  Each of the twelve
logical opcode positions must select one physical channel, and all selected
channels must be distinct.  The primary query allows no inversion and
requires every resulting twelve-bit value to belong to the 459-value public
P6 recognized-opcode set used by H1490.

This is an arbitrary cross-dword opcode-bit permutation, not a continuation of
H1493's serialization family.  Conversely, it is only an opcode-field audit;
it does not recover the other sixty logical bits or prove that the public
opcode catalogue is complete for old patch programs.

## Exact physical split

The bit-31 surface independently reproduces H1492 and is sharper when the
nineteenth line is kept separate:

| Signature | Set bit-31 positions, groups 0..17 | Set dwords, group 18 |
|---:|---:|---:|
| `0x611` | 0 / 144 | 2 / 8 |
| `0x612` | 0 / 144 | 1 / 8 |
| `0x617` | 73 / 144 | 2 / 8 |
| `0x619` | 64 / 144 | 6 / 8 |

This confirms two physical-format populations but does not identify the
meaning of bit 31 in the old steppings.

## Single-body fits are controls, not decoders

When each early body is solved independently, Z3 can assign three disjoint
twelve-channel mappings that make all 57 candidate micro-operations
recognized.  Those models collapse on sibling bodies:

| Training body | Train | `0x611` | `0x612` | `0x617` | `0x619` |
|---:|---:|---:|---:|---:|---:|
| `0x611` | 57 / 57 | 57 | 10 | 6 | 6 |
| `0x612` | 57 / 57 | 4 | 57 | 4 | 5 |

Four deterministic random controls preserve the same nineteen-line,
eight-dword, low-31-bit shape and fix every dword bit 31 to zero.  All four
also admit 57/57 three-lane recognized-opcode mappings.  Therefore isolated
SAT is a high-dimensional multiple-choice fit and supplies no decoder
evidence.

## Joint exact result

H1504 transposes the candidate opcode bits across the 38 address-aligned
`0x611`/`0x612` rows.  For each logical opcode bit, the resulting 38-bit
column must equal one actual physical-channel column.  This is exactly
equivalent to selecting an injective physical-bit mapping, but it avoids an
expensive row-by-row array encoding.

Bitwuzla 0.9.1 proves the non-inverting, one-lane query **UNSAT**.  A
three-lane mapping satisfying the same every-opcode-recognized condition would
contain a satisfying single lane, so that stronger query is impossible as an
immediate logical consequence.

Allowing an independent fixed inversion on each of the twelve selected
channels returns **UNKNOWN** after 60,000 ms.  UNKNOWN is not UNSAT and no
fixed-inversion impossibility is inferred.

An extended solver audit subsequently ran the same byte-exact
fixed-inversion SMT2 through Bitwuzla 0.9.1's `bitblast`, `prop`, and
`preprop` bit-vector engines, independently bounded at 300,000 ms.  All three
returned **UNKNOWN**.  This is a stronger documented computational wall, not
a logical result: it supplies neither a model nor an impossibility proof.

## Interpretation

The new exact boundary is:

- arbitrary per-body opcode mappings are as easy to obtain on random controls
  as on the recovered patches and do not transfer;
- the two early bodies cannot share a non-inverting injective opcode-bit
  mapping if every decoded patch operation must be in the current public P6
  recognized set; and
- the fixed-inversion extension remains unresolved.

The three independent 300-second engine bounds do not change that last
classification.

This does **not** prove that Pentium Pro patch bodies are undecodable.  A real
patch can contain opcodes absent from the public catalogue, the old format can
use channel polarity, and other logical fields may be stepping-specific.
H1504 recovers neither an absolute base-ROM state nor an R59 selector.  It
closes another feature-fitting route rather than advancing emulator behavior.

## Artifacts

- `experiments/h1504_ppro_opcode_permutation_smt.py`, SHA-256
  `169a24b9d514df3de81e7aae5ee35464528b7dd2095b1822de94e1e1ddb2e323`;
- `tmp/ledger33/current/h1504_ppro_opcode_permutation_smt.json`, SHA-256
  `a0fea5f962284950fb0c87647e25814ff443c9e876bf88369e366fa84fa3bde9`;
- non-inverting SMT2, SHA-256
  `c9110f73eed3f36087d1e1bced8a40a7314f6fbdf35968227f87c872a3c132af`;
- non-inverting solver output, SHA-256
  `5c17dfcc2a8f1f30d9e96df6a9825a5030ade046d560332c19de74d93d591a18`;
- fixed-inversion SMT2, SHA-256
  `356e915cadf88332a763f72efdad95694208b1e586e80f297f63b20db6141970`;
  and
- fixed-inversion solver output, SHA-256
  `7f51b4fb44dbc72708fac0a474600c2e9d8af4ce3a8b8f1680330454f6a8d68f`.

An independent run reproduced the report, both SMT2 inputs, and both solver
outputs byte-for-byte.  No update was loaded, no x87 instruction or hardware
capture ran, no hardware label or private ledger was opened, and H1488 remains
`FROZEN_UNOPENED`.  The emulator and academic paper/PDF were not changed.  R96
remains empirical/incomplete; the authoritative frontier remains eleven mode
rows over ten operands.

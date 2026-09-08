# FPTAN corpus v1

The first pack has **495,432 unique input/control tuples**, representing
122,900 signed, normal finite raw80 operands. Both recorded CPU contexts
have observed every tuple exactly once:

- Skylake Xeon: CPUID `00050654`, microcode `0x1`, job T0002;
- i7: CPUID `000506e3`, microcode `0xf0`, job T0003.

Both match the unchanged numerical implementation in tangent, pushed
value, C1 and C2. Their complete captured output/status streams are
byte-identical. See [the analysis](../ANALYSIS-T0001-T0003.md).

## Public files

- `inputs.txt.gz`: the portable input stream, approximately 14 MiB;
- `categories.tsv.gz`: input identity and independent selection family;
- `MANIFEST.json`: hashes, exact counts and observed CPU contexts.

There are no predictions, hardware labels, private supplemental data or
model sources in this pack. Its protocol differs from the two-input
FPATAN corpus and the three-instruction FSIN/FCOS/FSINCOS corpus.

Each input line is:

```text
identity rounding_mode precision_control sign_exponent significand
```

The raw80 fields have 4 and 16 hexadecimal digits. `rounding_mode` is
`rn`, `rd`, `ru` or `rz`; `precision_control` is 24, 53 or 64.
The identity is the first 40 SHA256 hex digits of the canonical key made
by `../protocol.py`. Every operand appears under all four modes at PC64.
There are 491,600 PC64 rows and 1,916 rows each at PC24 and PC53.

## Running on another CPU context

Use `../capture.c` and the protocol/guard/support modules as the capture
implementation. Adapt a **new** job manifest to the actual CPUID and
microcode, audit its capture history, and reserve the tuples before calling
FPTAN. `capture --identity` reads CPUID only and is safe before reservation.
Never invoke the input stream directly without the durable guard, and
never retry an uncertain/failed/reserved capture.

The existing `campaign.py` IDs are frozen completed jobs, not reusable
example IDs. Do not dispatch T0002/T0003 again. On the recorded contexts,
reuse `../../tmp/fptan-re/t000{2,3}/hardware.txt.gz`. Future additions should
be new immutable packs with distinct job IDs; retain the original hashes.

The capture resets the x87 state, masks exceptions, loads one operand,
and records both outputs and pre/post/store status. Successful calls push
a second stack value; C2 returns must not push and must preserve input.
Only the public stream and generic capture code need to reach a new host.

## Coverage limits

Inputs were selected by mathematical boundaries, exact residue/SMT
witnesses, full-significand strata and adjacent windows, independently of
candidate arithmetic. History clearance removed 938 generated operands;
only nine of 32 original windows remain complete. No held input is counted
as captured. Full exception words are retained and compared between CPUs,
but this numerical adapter does not predict exception-latch behavior.

This pack excludes zeros, subnormals, infinities, NaNs, unsupported
encodings and arbitrary incoming/unmasked state. A finite passing corpus
is evidence of agreement, not an all-input or all-generation proof.

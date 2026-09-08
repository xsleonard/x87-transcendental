# Promoted general standalone numerical program

This normal build target packages the unchanged H1630/H1633/H1638 arithmetic
program, now also used by the main default standalone entries. It is not the
older R96 model and cannot enable its fitted
experimental switches. R84 is off. The selected hardware reference is the
Skylake Xeon at 45.32.204.118; cross-generation equality is not required.

```sh
make -C fsincos-re/src general-candidate
fsincos-re/src/general/fsin_fcos_candidate --help
fsincos-re/src/general/fsin_fcos_candidate --batch --fsin-standalone --rc=rn < inputs.txt
fsincos-re/src/general/fsin_fcos_candidate --batch --fcos-standalone --rc=rz < inputs.txt
```

Each input line contains a hexadecimal sign/exponent word and 64-bit
significand, such as `3ffe 8000000000000000`. Output retains the existing
`OK`/`C2` numerical protocol; arithmetic/C1 metadata is on stderr. RC choices
are rn/rd/ru/rz. The wrapper rejects conflicting instruction selectors,
experimental switches and unsupported modes. This is a value-level CLI;
control-word/state APIs are not silently implemented by accepting arbitrary
arguments.

The fixed polynomial operators, table program, tiny predecessor rule and
exact reducer are unchanged. Existing domain reasoning and fresh adversarial
evidence remain applicable to that graph; packaging is not new hardware evidence.
All 81 recorded incumbent-frontier outputs match. H1708's default-source
regression passes 3,379,017 retained output appearances and 3,378,987 C1 checks.
An additional opened-bank replay passes 7,056 outputs and 5,136 C1 checks.
No new hardware was run. See `../../notes/h1707-h1708-standalone-promotion.md`.

The build currently reuses the historical source translation unit. Its inactive
legacy bodies remain as source text, but the restricted numerical routes and
fixed numerical graph is the one checked in H1702 and revalidated after
promotion in H1708. Final source isolation and an
embedding API are still to be finished; this target is not a claim of final
minimal-source delivery. No private standalone generator/material is imported.

FSINCOS is **not available** here. It must be implemented and independently
validated after the standalone milestone; calling the two standalone functions
is not assumed to reproduce FSINCOS. Complete pointer-register behavior,
undefined condition bits, obscure restore histories and universal physical
implementation proofs are not numerical completion gates under the clarified
user objective. Standalone default and paper promotion were explicitly
authorized and completed in H1708; the full three-instruction goal is not done.

For the main executable, `make -C fsincos-re/src all` builds the same standalone
arithmetic in `fsincos_skylake`; its normal output is quiet. Add
`--general-trace` for numerical C1/route metadata. The restricted package above
always emits that metadata for regression. Neither CLI is a complete x87
control-word/exception-state API.

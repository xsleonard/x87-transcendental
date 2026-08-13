# Cross-generation borrow-gate probe

Tests whether another x86 chip reproduces Skylake's FCOS
terminal-borrow behavior bit-exactly (the Rounds 57/58
phenomenon; see notes/HANDOFF-collision-gate.md).

    ./check.sh

Contents: `inputs.txt` = 56k adversarial near-boundary FCOS
operands (se 3ffc); `skylake_{rn,rd,ru}.txt` = i7-6700
(Skylake) reference captures; `categories.tsv` = per-row class
under the Round-57 rule (rule / chop / other).

Interesting targets, in value order: any pre-Skylake Intel
(Haswell, Sandy Bridge, Core2, P4, P6, P5) — an IDENTICAL
verdict pushes the gate's heritage back toward an optically
extractable die; the first DIFFERS verdict brackets the
generation where the datapath changed.  Any AMD — a DIFFERS
verdict confirms the gate is Intel-physical (expected); an
IDENTICAL verdict would mean the exact-arithmetic reference
itself is wrong and would reframe the project.

Note: the runner is x86-64; pre-x86-64 machines need a -m32
build of ../x87_capture.c (untested).

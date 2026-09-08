# H1717 — all-product paired schedule promoted, 2026-09-05

User authorized promotion of H1710 policy 2 after the independent review
falsified H1713 policy 1. The current default `src/general/paired.h` truncates
every Horner product to 67 bits before its RN64 coefficient addition.
There is no runtime policy selector, operand lookup or fitted correction.
The main translation unit and three standalone arithmetic headers are unchanged.
Earlier claims that policy 1 closed the paired numerical frontier were too
strong: its concrete RN counterexample is retained permanently.

## Exact discriminator

FSINCOS RN input `3ffc:e79000000c3e46e7` produces hardware sine
`3ffc:e5980e1fae54d858`, cosine `3ffe:f97b7761040745d2`, C1=0.
Policy 1 returns sine `...d857`. Independent signed-dyadic arithmetic and
both C implementations reproduce the schedule difference. The first stored
sine difference is at the K2 addition, changing the factor's significand
from `885e01cd990b6e61` to `885e01cd990b6e62` at exponent -70.
The final prevalue relative to the RN midpoint is -5/1024 output ulp for
policy 1 and +5/512 ulp for policy 2. Directed outputs and the cosine lane
agree. This identifies an observable arithmetic cut, not a physical netlist.

The independent review reports observing this operand on both hosts. H1717
directly rechecks the retained i7 comb10 raw-label stream and records its
RN/RD/RU outputs in `tmp/ledger33/current/h1717_review_regression/separator.json`.
No hardware instructions were captured again. The separate review bank did
not include this operand; do not confuse its zero-miss score with this witness.

## Actual promoted executable: completed checks

| Check | Scope | Result |
| --- | --- | --- |
| Retained paired census | 11,919,273 instruction/RC appearances; 23,838,534 lanes; 11,919,267 C1 | zero misses |
| Retained standalone | 3,379,017 outputs; 3,378,987 C1; all 81 frontier rows | zero misses |
| Imported i7 comb7/9/10 paired census | 45,517,233 rows; 91,034,466 lanes; 45,517,233 C1 | zero misses |
| Opened H1712/H1714/H1715/review capture replay | 357,360 tuples; 482,304 lanes; 353,520 known C1 | zero misses |
| Independent O0/O2/O3/UBSan verification | 101,440 paired cases, 200,704 lanes; 202,880 standalone isolation cases | pass |
| Exact interval certificate | all 30 polynomial binades; 840 checks; <=139 accumulator bits, <=132 alignment shifts | pass |
| Quick permanent paired regression | six saved-hardware output/C1 cases | policy 2 passes; policy 1 fails the RN separator |

The review census overlaps the retained census: comb7 was already among the
15 retained paired banks. Comb9/comb10 were omitted. Do not sum these counts
as distinct inputs or fresh observations. The original review's blanket
"not among the 15" wording for all three banks is imprecise.

The original review's claim that H1715 never ran is also stale. Its sealed
OPENED record and both disjoint capture builds are present, authenticated and
replayed here. C1 comparisons use the actual promoted trace where available;
the older 15-bank scorer retains its explicitly documented directed-bound
C1 inference. Special/undefined flags are not silently credited as predictions.

Local `make all` and selftest pass. The 93 existing compiler warnings are
unchanged; four compiler variants introduce zero new warnings. No private
source or supplemental ledger was read, copied or published. A proposed
source upload to the i7 was rejected by platform review; it was not bypassed.
The safe alternative copied saved public labels locally and performed the
complete regression here. No remote numerical execution was needed.

## Reproduction and evidence

```sh
make -C fsincos-re/src all check-paired-regressions
fsincos-re/src/fsincos_skylake --selftest
```

The new `experiments/h1717_*` scripts reproduce the compiler, retained,
opened-capture, i7-label and interval checks. They write new result directories
and refuse to overwrite existing reports. Historical H1713 verifiers and
sealed artifacts remain unchanged, with their original hashes and policy-1
contracts. Despite its filename, `h1717_remote_regression.py` now runs the
copied i7 labels locally; its explicit `--inputs` and `--labels` paths are
required. No capture harness is called by these checks.

| Artifact | SHA256 |
| --- | --- |
| main source (unchanged) | `490039e787a89b4efa4df58f0804356cc47c9e882f0e6427b16923217e375e32` |
| promoted paired header | `4eeb671562969e39b334923cbf41a40cb86f2a5ecb3dbad23de320be315b9a5d` |
| actual main binary | `0fd0acc28dcf5ad6651a170dba20966a3af32fa2f82c6b2dada894e0710ea558` |
| retained paired report | `ba2f30f074c25ba08ae2c64146dc95ef4efae41f853fe6b72c30a7bdf84bc1f4` |
| retained standalone report | `4f5d4e1d22ec86f471902df54946fb72d69433a13f141943437fb8407fee47aa` |
| i7 three-bank report | `35345ecc8a8f27b0be05648efc9d012227c1a201245cc48405087862a93c05f0` |
| four-compiler report | `b77ab630ed819d53696beb361c66a434b740d2a08814a35b6720e0be04620d92` |
| opened replay report | `3d2391d5cdec9ac0f4d5b71948ce20b095c994fbb33d6e69e729f1bb00d7df75` |
| interval report | `a2aaabdc1f698b66467977ff88882bc0522a55b43c46757a3e88073876c7dac8` |

Reports live under `tmp/ledger33/current/h1717_*`. The prior paired header,
binary, manuscript, PDF and READMEs are preserved in `h1717_pre_promotion/`.
The paper specifies the confirmed all-product program, exact separator and
regression limits; it is not an ongoing experiment log. Its 15 pages compile
without TeX warnings and have been visually reviewed. See the H1718 delivery
audit for final PDF/distribution hashes. There is no known numerical miss in
these completed checks; this is not exhaustive raw80 or universal CPU proof.

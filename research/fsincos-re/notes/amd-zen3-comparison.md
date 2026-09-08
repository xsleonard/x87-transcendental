# AMD Zen 3 FSINCOS vs Intel Skylake — first cross-vendor capture

Capture: volunteer-run kit v2 on an **AMD Ryzen 5 5600H** (family 25 =
Zen 3, same core as the 5700X), 2026-07-15.  Data:
`../data/captures/capture-AuthenticAMD-AMDRyzen55600HwithRadeonGraphics-20260715.tar.gz`
(sha256-verified, all six output files complete).  Inputs byte-identical
to the Skylake baselines, so every comparison below is line-by-line.

## Headline results

1. **Same algorithm family.** Our Skylake behavioral model matches Zen 3
   bit-for-bit on **94.29%** of the 240k dense set and 96.17% of the 50k
   sweep; every single mismatch is exactly **1 ulp** on one output
   (zero gross, zero C2 disagreements). Zen 3 runs a Pentium-descendant
   FSINCOS: same reduction, same table geometry, same polynomial regions.

2. **Bit-identical 66-bit π reduction.** Sweep segment D (8000 inputs
   within a few ulps of k·π/2, where reduction error is maximally
   amplified — a single differing π bit would produce many-ulp
   divergence): **8000/8000 bit-identical** to Skylake. Segment F (large
   near-multiples): 99.65%, max 1 ulp. The "AMD trig is more accurate"
   folklore is **falsified for Zen 3** — its sin near multiples of π is
   exactly as wrong as Intel's, and identically so. (The folklore may
   still hold for the 1996 K5, which had full-range reduction; this data
   speaks only for Zen 3.)

3. **FSIN/FCOS ≡ FSINCOS on AMD: 0/240000 differ.** On Skylake,
   FSIN/FCOS take a microcode path that diverges from FSINCOS on
   987/240k (poly region only). Zen 3 has a single path. A clean
   microarchitectural fingerprint distinguishing the vendors.

4. **RC honored only at final rounding, like Intel.** Zero bracketing
   violations (RD ≤ RN ≤ RU) and RU−RD ∈ {0, 1} ulp on all 480k output
   pairs. One internal high-precision value per output; directed modes
   just re-round it.

5. **Intel-vs-AMD divergence (the CoD determinism number):**
   **5.71%** of dense-region FSINCOS outputs differ between Zen 3 and
   Skylake hardware, **all by exactly 1 ulp** (sweep: 3.83%, again all
   1 ulp). For the original mixed-playerbase question: cross-vendor x87
   trig divergence is real and pervasive at the last bit, but never
   larger than that — and identically zero in the near-multiple
   danger zones.

## Divergence structure (AMD hw vs Skylake hw, dense 240k RN)

| region       | inputs | sin flips (+1/−1)  | cos flips (+1/−1)  |
|--------------|--------|--------------------|--------------------|
| poly         | 80000  | 603 / 568          | 73 / 339           |
| tbl-narrow   | 80000  | 1532 / 1562        | 769 / 1283         |
| tbl-wide     | 45463  | 1457 / 1445        | 21 / 1447          |
| reduced      | 34537  | 558 / 545          | **0 / 1721**       |

- **sin**: balanced ± everywhere → unbiased rounding-position noise
  between two implementations of the same chains.
- **cos**: strongly one-sided, becoming *purely* one-sided in the
  reduced region (1721 −1, zero +1) and near-pure in wide cells
  (1447 vs 21). AMD's cos is systematically one lattice step below
  Skylake's. One-sidedness = a truncate-vs-nearest difference at a
  single site in the cos accumulation — the same "chop-of-S" shape as
  Skylake's own residual vs our model. The vendors' kernels are siblings
  differing at one or two rounding sites in the cos path plus balanced
  micro-noise elsewhere.

## Shared residual — second silicon witness for the Skylake wall

Comparing both chips against the model on the dense set:

- model≠AMD: 13714, model≠Skylake: 2593, overlap: **1337**
  (expected if independent: 148 → **9× enrichment**)
- on the overlap, AMD == Skylake on **1264/1337 (95%)**

So ~half of the Skylake residual is *shared ancestral algorithm detail*
that Zen 3 reproduces bit-for-bit — independent confirmation that those
flips are algorithmic, not per-die noise. As an oracle it is too weak to
break the wall (P(Skylake flips | AMD flips) ≈ 9.7%), but it upgrades
the wall statement: the unmodeled 2⁻⁷⁰..2⁻⁷² rounding detail is at least
partly a stable microcode property with cross-vendor heritage, not
implementation-local.

## Provenance / reproduction

- Kit: `../capture-kit/` v2 (commit 583777e27), outputs sha256-verified.
- Skylake baselines: dense captures from the Xeon VPS (GenuineIntel
  Skylake, SERVER_ACCESS.md); sweep baseline
  `../data/sweeps/skylake-xeon-20260715.out.gz`.
- Model runs: `fsincos_skylake --batch [--rc=rd|--rc=ru]` on
  `capture-kit/inputs/dense_qn.txt` (note: `--batch` must be argv[1]).
- All comparison scripts inline in the session; the per-path classifier
  is `src/compare_runs.py`.

## Open follow-ups

- A pre-Zen AMD (K8/K10/Bulldozer) or 1996 K5 capture would date the
  convergence to Intel's 66-bit reduction (K5 folklore says full-range).
- A second *Intel* generation (Haswell, Ice Lake…) remains the lead for
  the Skylake 0.5% wall; the AMD data shows the missing detail is
  stable microcode, so another Intel capture is likely to be similarly
  enriched or identical.
- A period Pentium capture would test the two ROM errata directly on
  1993 silicon (`rom-errata.md`).

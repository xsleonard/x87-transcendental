# Paper: Reconstructing x87 FPATAN on Intel Skylake

The manuscript is [skylake-fpatan.tex](skylake-fpatan.tex). The rendered PDF is
[skylake-fpatan.pdf](../../../output/pdf/skylake-fpatan.pdf). The code-first
reference is [PSEUDOCODE.md](../PSEUDOCODE.md); its exact code blocks also
form the paper's programmer's appendix.

## Confirmed result and scope

The paper describes the fixed, promoted V7 numerical graph, not an experimental
selector. It includes reduction, interleaved polynomial chains, internal and
architectural rounding, quadrant restoration, raw80 class handling, C1 and
masked arithmetic exceptions. A separate appendix reproduces all 44 literal
P5 ROM constants with their encoding conversion and provenance. The exact
D0025 certificate proves lower/odd index equivalence **within the graph**,
not the identity of a physical silicon selector.

The final model matches 2,783,208 retained observations from fourteen campaigns;
624,312 were prospective tests of unchanged V7. Every RC has 695,802 observations.
The paper distinguishes those observations from software replays and PC groups,
and records the reference environment's reported CPUID/microcode and hypervisor
qualification. It does not claim exhaustive raw80 coverage, cross-CPU transfer,
mathematically correct rounding, or arbitrary x87 state/trap emulation.

## Rebuild

From the repository root, regenerate the synchronized exhibits, compile and
render for visual review:

```sh
python3 fsincos-re/fpatan-re/paper/build_paper.py --render
```

The builder requires Python 3, Tectonic, Poppler, and the local verification
receipts. Standard TeX packages/fonts may be downloaded on the first build.
It refuses stale pseudocode-verification hashes, changed numerical source,
inconsistent evidence counts, or TeX box/reference warnings. It never runs a
hardware capture. Draft build files and content-addressed review images stay
under `tmp/pdfs/fpatan-paper/`; the final PDF is under `output/pdf/`.

For a typesetting-only rebuild, the generated exhibits allow ordinary LaTeX
without loading the capture corpus or running Python. From this directory:

```sh
tectonic --keep-logs --outdir ../../../output/pdf skylake-fpatan.tex
```

A conventional LaTeX distribution can build the same source. Do not hand-edit
the generated exhibits: edit `PSEUDOCODE.md` or the manuscript, reverify any
pseudocode change, then regenerate. `generated/SOURCE-MANIFEST.json` pins the
manuscript, pseudocode, C source, exhibits and supporting evidence reports.

## Verification

The standalone Markdown contains executable reference pseudocode using exact
`Fraction` arithmetic. `verify_pseudocode.py` executes those blocks directly,
binds the public ROM literals, and compares them with **every** retained native
observation without calling the production numerical functions. Full result,
C1, exception and pre-load fields, per-job hashes, and RC/PC counts are checked.

```sh
python3 fsincos-re/fpatan-re/paper/verify_pseudocode.py --out /new/pseudocode-replay.json
python3 fsincos-re/fpatan-re/d0025_midpoint_alias_certificate.py --verify
```

The output path must be new. The publication snapshot uses
`fsincos-re/tmp/fpatan-re/d0030-pseudocode-replay-v2.json` from the repository
root. The earlier pre-layout reference check is preserved separately; it is
not an additional hardware observation.

The publication PDF has 13 pages, no TeX warnings, and a completed visual
review of every page. The final audit is
`fsincos-re/tmp/fpatan-re/d0030-paper-verification.json` (status **PASS**),
which pins the PDF and its rendered pages, authenticates the source manifest,
checks all 44 literal entries in the PDF, and confirms that the C source and
historical release archive are unchanged.

Author attribution is intentionally withheld. Do not infer a name or contact
address from Git metadata, account details, or local paths. Add attribution
only after an explicit instruction from the user.

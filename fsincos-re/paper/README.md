# Paper: Thirty Years of the Pentium Kernel

`skylake-x87.tex` — the publication manuscript (standard LaTeX; builds
with any TeX distribution):

    pdflatex skylake-x87.tex && pdflatex skylake-x87.tex

or `tectonic skylake-x87.tex`.  A readable HTML preview can be
regenerated with:

    pandoc skylake-x87.tex -f latex -t html5 -s --mathjax -o skylake-x87-preview.html

Every number and hex constant in the manuscript is sourced from the
maintained campaign records: `../notes/algorithm-description.md`
(stage-by-stage algorithm + blind-spot register),
`../notes/algorithm-spec.md` (terminal-correction closed forms),
`../notes/rom-errata.md` (P5 ROM errata), `../notes/amd-zen3-comparison.md`
(cross-vendor capture), `../notes/HANDOFF-collision-gate.md` (round
records incl. Round 84 and the epoch discovery), and
`../experiments/r84_misses.tsv` (ledger row provenance).

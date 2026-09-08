# Source and attribution register

Bibliography used by the unified paper: [suite-references.bib](suite-references.bib).
This is a source map, not a completed novelty review.

| Key | Primary material | Cite for | Verification / editorial task |
| --- | --- | --- | --- |
| `shirriff2025rom` | [Pi in the Pentium](https://www.righto.com/2025/01/pentium-floating-point-ROM.html) | Pentium ROM decode and published algorithm explanation | Live article checked 2026-09-06; pin the saved source edition for each correction |
| `intelSdm` | [Intel SDM](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) | Instruction inventory, raw80, domains, stack effects and architectural flags | Landing page checked 2026-09-06, advertises revision 092; record exact downloaded revision/sections when writing claims |
| `harrison2000` | [Formal verification of floating point trigonometric functions](https://www.cl.cam.ac.uk/~jrh13/papers/fmcad00.html) | Itanium algorithm/verification lineage | Author's bibliographic page checked 2026-09-06; not a Skylake algorithm specification |
| `glibc238` | [glibc-2.38 IA-64 FPU sources](https://github.com/bminor/glibc/tree/glibc-2.38/sysdeps/ia64/fpu) | Preserved Intel implementation and notices | Existing [local provenance](../data/glibc-ia64-fpu/PROVENANCE.md) pins commit and files; recheck selected release files and preserve their notices |
| `ucodeDisasm` | [Pinned Goldmont operation listing](https://github.com/chip-red-pill/uCodeDisasm/blob/ffc9070233a6e7a26dbabe723289259f087ee20b/ucode/ucode_glm.txt) | Public operation structure, with uncertain opcode interpretation identified | Existing [D0021 audit](../fpatan-re/ANALYSIS-D0021.md) has artifact hash; live pinned URL fetch failed during this pass |
| `customProcessingUnit` | [Pinned FP-ROM dump](https://github.com/pietroborrello/CustomProcessingUnit/blob/4237524fe7545c66e42dd986113f220662c06f6a/bios/dumps/rom.txt) | Public projected payloads | Existing [lineage audit](../goldmont-lineage/README.md) pins source and hashes; live pinned URL fetch failed during this pass |

Failed live fetching is not a finding against the existing archived evidence.
For a release, supply the attributable public artifact or a verified stable
retrieval path, with the original source revision and notices.

## Placement and credit

Credit Ken's work in the introduction, where the ROM is first introduced,
beside each directly reconstructed instruction family, and in the
acknowledgments. Make the distinction readable: which constants and algorithm
ideas were available publicly, which interpretation/transcription was needed,
and which internal arithmetic rules were constrained by new observations.

Treat F2XM1 and FPTAN as full results even though the public material made
their reconstruction relatively direct. Do not inflate their novelty by
describing the public constants as newly discovered. Conversely, do not omit
their executable specification and validation merely because reconstruction
required fewer experiments.

Use the Goldmont material as a separate attributed source. It does not turn
the behavioral Skylake reconstruction into a direct Skylake microcode decode.
Refer to the Itanium program as the reconstructed public reference algorithm;
do not describe its source transcription as a new transcendental method.

## Footnotes, mathematics and figures

- Markdown explanations use named footnotes near the relevant claims.
- The article uses numbered bibliography citations; historical or tangential
  context can use prose footnotes rather than interrupting the algorithm.
- Equations describe a mathematical identity or an exact rounded operation;
  always distinguish the two. Pseudocode is the complete execution order.
- Create original operation/dispatch diagrams from the fixed programs.
  Any reused figure needs its own attribution and applicable permission/terms;
  linking a source does not make its image an original project figure.
- Corrected ROM words need original literal, replacement, source row/edition,
  mathematical check and hardware evidence. Avoid speculation about which
  stage of another researcher's workflow introduced an error.

## Related-work scope of this version

The article also uses Harrison, Kubaska, Story and Tang,
[The Computation of Transcendental Functions on the IA-64 Architecture](https://www.cl.cam.ac.uk/~jrh13/papers/itj.pdf)
(Intel Technology Journal, Q4 1999), for reduction, approximation and
reconstruction context, and Intel's
[explanation of x87 versus mathematical trigonometric functions](https://www.intel.com/content/www/us/en/developer/articles/technical/the-difference-between-x87-instructions-and-mathematical-functions.html).
These primary sources were checked for the current article. The final text
makes no priority claim over all earlier emulator or bit-exact models.
Such a claim would need a separate comprehensive prior-art comparison.

Do not imply that earlier implementations or studies did not exist, or
describe an implementation as a comparison baseline unless it was actually
used in that role. Describe the contribution through the specified numerical
programs and their recorded validation.

Keep project author and contact fields blank until the user explicitly
supplies and approves the attribution. Preserve third-party source credit. The
existing AI-assistance acknowledgment can be consolidated into one statement
with the author responsible for evidence and conclusions. A stable project
license and repository/report identifier remain release decisions. The author
has explicitly left original-work licensing undecided for this local version.

## Approximation mathematics

The mathematical discussion links each instruction to the analytic identity
that makes a small polynomial useful, then distinguishes that identity from
the reconstructed finite-precision operations.

| Source | Passage used | Connection in the manuscript |
| --- | --- | --- |
| [Harrison et al., 1999](https://www.cl.cam.ac.uk/~jrh13/papers/itj.pdf) | pp. 1-3: reduction, minimax approximation, tables and reconstruction | Common design framework; interval size versus polynomial degree; addition formulas |
| [Harrison, 2000](https://www.cl.cam.ac.uk/~jrh13/papers/fmcad00.pdf) | Sections 4-5: range reduction and core verification | Distinguishing reduction, approximation and evaluation error |
| [Shirriff, 2025](https://www.righto.com/2025/01/pentium-floating-point-ROM.html) | Polynomial approximation and the instruction-family discussions | ROM coefficients differing from Taylor coefficients, exponential scaling, tangent division and logarithm tables |
| [NIST DLMF 4.2](https://dlmf.nist.gov/4.2#E19) | Exponential power series | Direct computation of the small difference `exp(t)-1` |
| [NIST DLMF 4.19](https://dlmf.nist.gov/4.19) and [4.21](https://dlmf.nist.gov/4.21) | Sine/cosine series and addition identities | Parity, local correction polynomials and table reconstruction |
| [NIST DLMF 4.24](https://dlmf.nist.gov/4.24) | Arctangent series and addition/subtraction identities | Ratio reduction to a short odd polynomial |
| [NIST DLMF 4.6](https://dlmf.nist.gov/4.6#E4) | Transformed logarithm series | Atanh reduction, the two polynomial scalings and preservation of small increments |

These primary sources were checked on 2026-09-07. Residual interval bounds,
the two scaled logarithm expansions, the tangent error identity and the
finite-divisor phase-error formula are elementary derivations shown here to
connect the literature to this implementation. They do not attribute a
Skylake rounding schedule to an Itanium paper, or certify every quantized
ROM polynomial as an exact minimax solution. The illustrative Taylor
remainder bound applies to the displayed Taylor polynomial.

## Logarithm extension

The [logarithm source audit](evidence/logarithm-public-source-audit.json)
uses the same pinned public Goldmont listing and ROM projection cited above.
It checks all 77 logarithm-related projections and independently derives
four corrected split-table words (P5 rows 207, 245, 259 and 268) from
`RN40(log2(1+n/64))` and the signed RN67 residual. The original TSV remains
unchanged. Full formulas, source addresses and interpretation limits appear
in [the algorithm](../fyl2x-re/ALGORITHM.md).

For the underflow rule, Intel's [Volume 1 architecture manual](https://www.intel.com/content/dam/develop/external/us/en/documents-tps/253665-sdm-vol-11.pdf),
sections 4.9.1.5 and 8.5.5, specifies tininess using rounding with unbounded
exponent. The logarithm campaigns additionally establish the fixed 64-bit
precision and the kernel's forced-inexact behavior in the tested context.

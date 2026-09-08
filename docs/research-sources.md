# References

These sources support the library's constants, architectural behavior and
numerical explanations. [Provenance](provenance.md) describes their use in the
implementation; the [algorithm index](algorithms/README.md) connects the
reconstructed programs to their evidence.

## Constants, architecture and source lineage

| Source | Relevance |
| --- | --- |
| Ken Shirriff, [Pi in the Pentium](https://www.righto.com/2025/01/pentium-floating-point-ROM.html) (2025) | Published Pentium ROM transcription and algorithm explanations, including the F2XM1, FPTAN and logarithm constants. |
| Intel, [Software Developer's Manual](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) | x87 operands, domains, stack effects and architectural flags. Volume 1, sections 8.5.1–8.5.6 describe floating-point exceptions; sections 4.9.1.5 and 8.5.5 describe underflow and tininess with unbounded exponent. |
| Intel, [The Difference Between x87 Instructions and Mathematical Functions](https://www.intel.com/content/www/us/en/developer/articles/technical/the-difference-between-x87-instructions-and-mathematical-functions.html) | Limits of treating the hardware transcendental instructions as exact mathematical functions. |
| [glibc 2.38 IA-64 FPU sources](https://github.com/bminor/glibc/tree/glibc-2.38/sysdeps/ia64/fpu) | Preserved Intel Itanium implementation and third-party notices underlying the separate research reference. |
| [Goldmont operation listing](https://github.com/chip-red-pill/uCodeDisasm/blob/ffc9070233a6e7a26dbabe723289259f087ee20b/ucode/ucode_glm.txt), pinned revision `ffc9070` | Public operation structure used in the arctangent and logarithm source studies. Opcode interpretations have separate evidence limits. |
| [FP-ROM projection](https://github.com/pietroborrello/CustomProcessingUnit/blob/4237524fe7545c66e42dd986113f220662c06f6a/bios/dumps/rom.txt), pinned revision `4237524` | Public projected constant payloads used for comparison with reconstructed constants. |

Goldmont material supplies a separately attributed comparison; it is not a
direct decode of Skylake microcode. The logarithm source audit compares 77
related projections and derives four corrected split-table words (Pentium rows
207, 245, 259 and 268) from `RN40(log2(1+n/64))` and the signed RN67 residual.
The original [ROM TSV](../tests/data/pentium-rom/rom-constants.tsv) is preserved.
See [the logarithm program](algorithms/logarithms.md) for formulas and limits.

## Numerical methods and identities

| Source | Relevance |
| --- | --- |
| Harrison, Kubaska, Story and Tang, [The Computation of Transcendental Functions on the IA-64 Architecture](https://www.cl.cam.ac.uk/~jrh13/papers/itj.pdf), Intel Technology Journal, Q4 1999 | Reduction, approximation, tables and reconstruction; the tradeoff between reduced interval size and polynomial degree. |
| John Harrison, [Formal Verification of Floating Point Trigonometric Functions](https://www.cl.cam.ac.uk/~jrh13/papers/fmcad00.pdf), 2000 | Separation of range-reduction, approximation and evaluation error. Itanium verification is not a specification of Skylake rounding schedules. |
| NIST DLMF, [4.2: Exponential Function](https://dlmf.nist.gov/4.2#E19) | Power series underlying small `exp(t)-1` approximations. |
| NIST DLMF, [4.19: Maclaurin Series](https://dlmf.nist.gov/4.19) and [4.21: Identities](https://dlmf.nist.gov/4.21) | Sine/cosine parity, local polynomials and table reconstruction identities. |
| NIST DLMF, [4.24: Inverse Trigonometric Functions](https://dlmf.nist.gov/4.24) | Arctangent series and identities used for ratio reduction. |
| NIST DLMF, [4.6: Power Series](https://dlmf.nist.gov/4.6#E4) | Transformed logarithm series and preservation of small increments. |

The mathematical identities explain why these approximations are useful.
The library's particular constants, operation order and precision cuts require
the additional evidence described in [validation](validation.md).

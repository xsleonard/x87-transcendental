# Standalone FSIN/FCOS source hunt

## Conclusion

Standalone FSIN is now reconstructed as a separate C path.  It reuses the
solved M66 range reduction, P5 constants, table cells, special cases, and
architectural final rounding, but has distinct direct-entry, reduced-sine,
and odd-quadrant internal-cosine polynomial schedules.  The current full
sweep has 334 one-ulp mode misses out of 150,114 RN/RD/RU results; 78 are in
polynomial paths and 256 are inherited from the existing FSINCOS table wall.
Tiny input behavior is exact.

Standalone FCOS was captured and constrained because its direct cosine
producer is a useful ancestor of FSIN's odd-quadrant producer.  It transfers
profitably, but a fresh train/held-out sweep selects a different square
materialization for FSIN, so the two paths are not bit-identical.  Full
operation graphs and validation counts are in `fsin-reconstruction.md`.

## Direct algorithm lineage

Peter Tang's 1990 Argonne report gives implementable sine/cosine operation
graphs and coefficients:

- [Some Software Implementations of the Functions Sine and Cosine
  (ANL-90/3)](https://www.osti.gov/servlets/purl/7184536)
- Direct sine form: `Xsq=X*X`, evaluate a polynomial in `Xsq`, then
  `S=X+X*Q`.
- The report treats a machine-representable approximation to pi as defining a
  deliberately shifted trigonometric function, matching Intel x87 semantics.

Tang's 1991 ARITH paper is the strongest structural ancestor found:

- [Table-Lookup Algorithms for Elementary Functions and Their Error
  Analysis](https://www.acsel-lab.com/arithmetic/arith10/papers/ARITH10_Tang.pdf)
- For sine it chooses breakpoints
  `c_j=2^-f*(1+k/8)`, evaluates short residual polynomials, and reconstructs
  from stored `sin(c_j)` and `cos(c_j)`.
- The recovered P5 breakpoints are an exact subset of this family:
  `18,22,26,30 / 64` are `f=2`, odd `k`; `36,44,52,60 / 64` are `f=1`,
  odd `k`.  P5 uses the direct polynomial below `1/4`, so it does not need the
  paper's smaller breakpoint ranges.
- The paper explicitly motivates retaining internal guard/round information
  throughout reconstruction rather than rounding each intermediate to a
  software-visible floating-point format.

Tang's Intel Technology Journal biography says that he consulted on the
Pentium transcendental algorithms.  This makes the agreement specific design
lineage rather than a generic table-lookup resemblance:

- [Intel Technology Journal, Q4
  1999](https://www.intel.ru/content/dam/www/public/us/en/documents/research/1999-vol03-iss-4-intel-technology-journal.pdf)

The Pentium Developer's Manual independently describes table-driven
transcendentals using short polynomials, wide internal datapaths, and
microprogramming.  Its operand-dependent cycle ranges provide another
black-box observable:

- [Pentium Processor User's Manual, Volume
  3](https://datasheets.chipdb.org/Intel/x86/Pentium/24143004.PDF), Appendix G
- FSIN: 59--126 nonspecial cycles; FCOS: 59--126; FSINCOS: 83--138.

The Pentium architecture paper identifies 24/53/64-bit multiply rounding plus
separate wide add/shift hardware and transcendental micro-operations:

- [Architecture of the Pentium
  Microprocessor](https://pages.cs.wisc.edu/~markhill/restricted/MKreadings2000percaitlin/ieee_micro_1993_alpert.pdf)

Ken Shirriff's ROM work remains the physical-evidence route:

- [P5 constant ROM](https://www.righto.com/2025/01/pentium-floating-point-ROM.html)
- [P5 microcode ROM](https://www.righto.com/2025/03/pentium-microcde-rom-circuitry.html)

The P5 microcode ROM is physically recoverable, but its encoding is not
decoded.  Ken's March 2025 analysis establishes 4,608 90-bit
microinstructions and explicitly reports that neither the encoding nor the
entry-address generation is known.

Peter Bosch's Pentium II work is a stronger P6 lead.  He reports a perfect
software dump of one PII mask ROM and a substantially decoded micro-op format:

- [Pentium II microcode, part 1](https://pbx.sh/pentiumii-part1/)
- [Pentium II microcode, part 2](https://pbx.sh/pentiumii-part2/)
- [public p6tools repository](https://github.com/peterbjornx/p6tools)

As of 2026-09-02 the repository README is stale: the tree does contain
`simpleas.py`, `simpledis.py`, and `uc_isa.py` in addition to the
scrambler/descrambler.  The disassembler's opcode map is partial, and the
perfect mask-ROM image itself is not present.

We also decrypted and descrambled 12 public 2-KiB Pentium II update images
covering CPUID 650, 651, 652, and 653 platform variants with Bosch's
`patchtools` and the Python-3 `p6tools` fork.  Every decoded patch body is a
short MSRAM program at UROM 3FAC--3FFE that branches back to the base mask ROM.
None contains a micro-op named by the available map as floating point; the
only undecoded opcodes are 000, 0D8, 131, and 134 in ordinary control-flow,
load/store, and instruction-completion contexts.  Because the map remains
partial, this is a bounded negative result, not proof that no patch can affect
an FPU path.  More importantly, patch overlays do not reveal the bodies of the
base-ROM targets.  Microprogram recovery is therefore a concrete route, but
the public artifacts inspected here still do not expose the arithmetic
schedule or carry predicate for FSIN/FCOS.

## What the other sources do not solve

Intel's 2015 x87/libm comparison confirms the broad polynomial design, the
limited pi approximation, and shifted-function semantics, but does not expose
coefficients or evaluation precision:

- [The Difference Between x87 Instructions and Mathematical
  Functions](https://www.intel.com/content/www/us/en/developer/articles/technical/the-difference-between-x87-instructions-and-mathematical-functions.html)

No independent bit-exact Intel FSIN reconstruction was found.  Bochs uses one
shared software `fsincos()` implementation for all three instructions, a
128-bit pi constant, and binary128 Taylor arithmetic, so it cannot explain the
measured PII instruction differences:

- [Bochs FPU source](https://github.com/bochs-emu/Bochs/tree/master/bochs/cpu/fpu)

The AMD K5 and Cyrix papers are useful examples of precision-annotated
microcode algorithms but are not evidence for Intel P5/P6 sequencing.

## Evidence from the present captures

- Skylake and Pentium II standalone FSIN RN are identical on all 240,000
  dense operands.  Updated Skylake RN/RD/RU status captures add 478,278
  independently checkable C1 observations, all consistent.
- h110 reduces the 80,000-input direct FSIN region to 420/240,000 one-ulp
  mode misses and 303/80,000 inputs.  Constant-bias, coefficient-delta,
  factored-final, and local topology alternatives fail cross-validation.
- The structured full sweep exposes 26 RN differences between FSIN and the
  PII/Skylake FSINCOS sine output.  Every difference is in the polynomial
  kernel; 23 follow odd-quadrant reduction and therefore constrain the
  internal cosine producer.
- h119 constrains standalone FCOS with directed results and C1.  h121 then
  uses 12,249 FSIN odd-quadrant residuals to select its FSIN-specific variant
  on independent halves.  h122 similarly selects a separate reduced-entry
  sine schedule over 5,684 residuals.
- h117 identifies the small-input transition: exponents -68 through -33
  retain a nonzero correction visible only to directed rounding; exponent
  -69 and below returns the operand in every rounding mode.  The 360-input
  probe is exact in all 1,080 results.

The unusual odd/away/chop operations in the surviving graphs are explicit
equivalent representatives.  They are not claims that Intel microcode has
floating-point primitives with those literal modes; a fixed-point
alignment/carry/sticky datapath can produce the same retained bits.

## Remaining pass

1. The polynomial-producer literal-FADD part is complete in h200-h205.  A
   68-bit
   alignment/subtraction/normalization carrier tests four interpretations of
   the separate sticky wire, every Horner retain mask, direct/reduced gates,
   both FRND normalization states, and coherent physical FMUL/FADD routes.
   None passes componentwise old and focused-capture validation, so it does
   not explain the remaining 74 polynomial mode cases.
2. h206-h210 complete the missing table-reconstruction and carrier-transition
   coverage.  All seven Tang trees use literal FADD for all three additions;
   retained J/GRS carriers feed FMUL X67 directly; and 40 producer profiles
   are crossed with 20,160 coherent end-to-end schedules.  No profile passes
   the componentwise sample gate.  h210 verifies add, far-subtract, and near-
   subtract arithmetic against 50,000 exact reference cases.
3. A further raw-datapath pass now requires specific FIRC microcontrol or an
   FMUL behavior not equivalent to its documented exact product, sticky, and
   increment result.  Generic FADD topology, width, normalization, and
   carrier routing are exhausted on current evidence.
4. Resolve the 256 table cases through the existing shared FSINCOS
   `(S,t)` producer work; FSIN and FSINCOS have no observed table-kernel RN
   instruction differences in the full sweep.
5. Use timing only on bare metal.  Repeated KVM measurements did not preserve
   per-input fast/slow classifications and are rejected as algorithm
   evidence.
6. A future PII or P4 run of `run_standalone_prebuilt.sh` is useful as an
   independent generation witness, but is no longer required to execute this
   reconstruction pass.

## Conditional FIRC result

h211-h225 supply the specific microcontrol evidence requested by the earlier
source pass.  The literal patent datapath is arithmetically sufficient for
every measured table residual, but no unconditional program works.  Fresh
Skylake data validates one lane-local first-FADD carrier predicate, now
ported as Round 36.  Three additional discriminator rounds reject every
bounded second branch.  The selected FAMUBUS bit is not an alias for the
modeled carry, borrow, alignment, or sticky signals.  A future source lead is
therefore useful only if it exposes another microcontrol predicate or the
decoded FIRC sequencing; generic polynomial, topology, and width descriptions
will not advance the remaining cases.

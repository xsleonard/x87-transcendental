# D0040: exact correction-sum ties and neighboring inputs

This append-only corpus-v1 extension contains **956,608 unique observation
tuples** from one completed Skylake capture. The combined
[CATALOG-D0040.json](../../CATALOG-D0040.json) authenticates all seventeen
packs: **4,612,536 unique tuples**, approximately 140 MiB including the
retained construction pools. The original manifest, earlier packs and
CATALOG-D0036 remain unchanged.

`inputs.txt.gz` is the public FPATAN capture protocol: ordered raw80 operands,
RC, PC and case ID. The complete 28,799-pair D0039 inverse-halfway pool receives
all sign/octant and four-RC variants. The 32 endpoint-visible witnesses also
receive 5x5 both-operand neighborhoods and exact scales at the normal exponent
limits. Every RC has 239,152 rows. PC24 and PC53 each have 3,696 rows; PC64
has 949,216 rows. These are observation tuples, not distinct unconditioned
operand-pair counts.

`correction-halfway-input-pool.tsv.gz` preserves every D0039 external base
pair, with columns `search_id y_se y_sig x_se x_sig`. It is a construction
pool, not a capture-protocol pack. No model endpoints, internal state,
discriminator mask, hardware labels or private ledger are included.

All packed tuples were already observed once on the guest-reported Skylake
reference, CPUID `00050654`, microcode `0x1`. **Do not recapture them there.**
Reuse saved outputs. For another CPU, audit that host's prior history and
reserve each fresh tuple before execution. Preserve its actual identity and
full result/status separately. These inputs support cross-CPU comparisons;
their inclusion does not claim the V7 model transfers to other CPUs.

The complete theoretical adversarial space is not exhausted. See
[D0037–D0040](../../../ANALYSIS-D0037-D0040.md) for construction, validation
and remaining gaps. `MANIFEST.json` pins this extension; the combined catalog
and `extend_corpus_d0040.py` record provenance and duplicate checks.

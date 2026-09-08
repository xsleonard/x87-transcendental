# Source and constant provenance

The production numerical programs derive from the research implementations
under `research/fsincos-re/`. The
[reference list](research-sources.md) identifies public constants, architectural
specifications and supporting algorithm literature.

Original project material is licensed under the GNU Lesser General Public
License, version 3 only (`LGPL-3.0-only`); see [the license notice](../LICENSE.md),
[COPYING.LESSER](../COPYING.LESSER) and [COPYING](../COPYING). Third-party material
retains its existing terms, attributions and notices.

The Pentium constant transcription and corrections are retained in
`src/constants/`. Ken Shirriff's published Pentium ROM analysis supplies the
public constant transcription and algorithm explanations. Source comments
identify ROM rows, signs and significand bits. Logarithm table corrections
remain separate from the original transcription; the original
[ROM TSV](../tests/data/pentium-rom/rom-constants.tsv) accompanies the independent
test references. Public constants and related algorithms do not by themselves
establish the reconstructed Skylake precision cuts and operation order.

The fixed-width software-value helpers originate in the repository's Itanium
reference support. The library uses its integer representation, conversion and
comparison helpers. The separate Itanium implementation and reciprocal table
remain in research and are not runtime dependencies. FPATAN and the logarithms
use the local [bounded finite arithmetic](finite-arithmetic.md); no GMP source
or external arithmetic library is embedded in the runtime.

Special-value and completion semantics follow the retained
[hardware test fixtures](../tests/data/) and Intel SDM Volume 1,
sections 8.5.1 through 8.5.6. The [Bochs adapter](bochs.md) targets a pinned public
upstream checkout without copying that tree into the library release.

The source archive includes the library, these references and compact test
evidence. Private models, downloaded source trees, large capture archives,
generated papers and research working records remain outside the package.

# Validation and numerical limits

Run `make check` for the offline library suite. Tests and CLI clients link the
same compiled library used by consumers. No special numerical test build exists.

The retained hardware replay contains 1,800 rows: 724 original suite witnesses,
216 F2XM1 storage regressions, 854 logarithm witnesses and six paired polynomial
separators. The replay checks available output/status fields explicitly. Current
counts include 1,588 C1 checks, 506 C2 checks and 1,006 arithmetic-flag checks.
Independent exact-rational references cover the applicable FPATAN, FPTAN, F2XM1
and logarithm witnesses. The larger hardware archives remain in research; a
compact replay does not authenticate every archived byte or prove all inputs.

The initial extraction also matched the frozen source build on 151,680
comparisons: 25,536 for each unary instruction and 8,000 for each binary
instruction, spanning all four RCs. These deterministic random/boundary checks
establish implementation parity, not new hardware evidence. To repeat against
the preserved research programs, build their existing CLIs and run:

```sh
python3 tools/validation/compare_legacy.py build/x87trans-cli research/fsincos-re
```

`tests/data/baseline.json` records hashes and current paths for 285 pre-extraction
files. `tools/validation/check_baseline.py` verifies their preservation. The
original source snapshot and execution logs are retained locally under
`output/reorg-baseline/` and are not part of the source release.

API checks exercise argument validation, unchanged outputs on error, raw80 byte
round-trips, range returns, explicit metadata availability and concurrent calls
using one immutable context. Existing binary-family API tests also run against
compatibility adapters backed by the new library. A separate masked-writeback
fixture verifies caller-side stack behavior.

Release verification includes ordinary and sanitizer builds, a shared-library
export inspection, C and C++ consumers, installed and vendored builds, pkg-config
linking and a source archive built without the research tree. See the [reorganization receipt](reorganization-results.json) for the executed
configurations and results.

No numerical formula or constant was intentionally changed. Structural changes
include direct dispatch, explicit per-call metadata and sharing byte-identical
GMP primitives. The raw80 encodings previously mishandled by FPTAN/F2XM1 are
explicitly rejected as outside scope rather than passed through their lossy
decoder. Complete unary exception flags and unmasked completion remain separate
work under the [API scope](api.md).

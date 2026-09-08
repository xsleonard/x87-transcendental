# Research archive

The maintained library is in the repository's root `include/` and `src/`.
This directory preserves the historical implementations, experiments, capture
records and manuscripts. Do not apply new library fixes to these frozen copies.

- [Original project overview](PROJECT-README.md), [source map](SOURCE.md) and
  [research goal/history](GOAL.md).
- [Historical research tree](fsincos-re/), including its original internal paths.
- `make -C research check` replays the previous small offline acceptance suite.
- `make -C research/fsincos-re/src test` checks the separate Itanium reference.

Campaign data and research working files now live in `fsincos-re/tmp/` within
this archive. That directory moved after the H1725 worker and status watcher
finished; the temporary root `fsincos-re/` directory and compatibility links
have been retired. The move preserved the directory and its contents. No remote
jobs were started, stopped or modified during this migration.

Git includes research sources, notes and the bounded offline regression fixtures.
Bulk corpora, database catalogs, exported capture jobs, transfer bundles, full
observation banks and generated binaries remain local and are ignored. Historical
capture input/output banks are also excluded; their generators and provenance
remain in this archive. A fresh checkout supports the library and legacy offline
checks, but does not contain the full datasets needed for archival campaign
replays. See the root `.gitignore` for those data locations.

Historical manifests and captured files were not rewritten to change recorded
paths. Resolve a historical repository-relative `fsincos-re/...` source path
under `research/`; absolute paths inside sealed provenance are historical
identifiers. The baseline manifest in `../tests/data/baseline.json` includes
current locations and hashes for 285 preserved files.

Paper tools retain their original relative layout and pinned numerical sources.
Their historical output root is now `research/output/`. The existing generated
PDFs and review packages at repository `output/` remain preserved. Current
library source packaging is `tools/release/package.py`; historical publication
packaging remains archival and retains its original source/evidence claims.

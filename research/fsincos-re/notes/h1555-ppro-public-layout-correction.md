# H1555 Pentium Pro public-layout correction

Date: 2026-09-04

Status: **exact public-format replay; H1467's 19-by-eight body partition is
falsified and every dependent mapper theorem is restricted to that obsolete
partition. No selector or emulator change.**

## Correct public format

The public `ruikruik/patchtools_pub` implementation at commit
`4c05693873e93a662fb49e47d9c29c6947ef6151` supplies the missing Pentium Pro
format facts. H1555 transcribes and independently replays that implementation
against all five public updates:

- `0x611` uses base key `0x28d4fc58`;
- `0x612`, `0x616`, and `0x617` use base key `0x715f1f2f`;
- `0x619` uses base key `0x61dab85e`;
- the body is 148 dwords: 21 groups of seven dwords plus one spare dword;
- the control block contains 16 records; and
- the patch-RAM base is `0x3fac * 2`.

The first word that H1467 called body data is actually the leading `0x1B2`
control record. Under the corrected boundaries, all five updates decrypt
fully and pass all 17 per-patch integrity checks, 85/85 total. The previously
problematic `0x616` body is no longer a boundary case. The corrected bodies
for `0x612`, `0x616`, and `0x617` are byte-identical.

## Scope correction

H1467 partitioned 167 post-header dwords as 19 eight-dword groups followed by
15 controls. H1555 proves that partition is physically wrong. Consequently,
H1490--H1554 studies which consume those old 19-by-eight groups remain valid
only as theorems about the mispartitioned H1467 dataset. They cannot constrain
the actual Pentium Pro seven-dword groups, and their SAT witnesses are not
physical decoders.

This correction does not itself provide the logical 72-bit uop permutation,
an absolute base-ROM/control-state trace, or the unresolved R59 selector.

## Sources and artifacts

Primary source: [ruikruik/patchtools_pub at the pinned commit](https://github.com/ruikruik/patchtools_pub/tree/4c05693873e93a662fb49e47d9c29c6947ef6151).

- public source tarball SHA-256
  `2b1ed7024ef84ae8d07b97de7655a15e3cf2565528d38ab40bb01314a648b55f`;
- `cpukeys.c` SHA-256
  `7e1bd2a0a9c2efbf092fbc5122de4bcb80866c90b8b21ad33c35142fda58f643`;
- `patchfile.c` SHA-256
  `55faefdff39c56896d83c3600da8247a3ef47bbc8603428fc566e216316d2605`;
- `crypto.c` SHA-256
  `8fae236fda7dc147715cba248de0103967d2d195feb1d5151fbdb39063240123`;
- `experiments/h1555_ppro_public_layout_reaudit.py` SHA-256
  `158f724d6b924ac3040496952ff3f88b205da9252b0e1eb8d54a9483542186c9`;
- `tmp/ledger33/current/h1555_ppro_public_layout_reaudit.json` SHA-256
  `cfa72d316ffb6efd58770b820d79b9568fc459d26691f09d6f9842da952d6280`.

No update was loaded, no hardware or x87 instruction ran, no private ledger or
capture label was opened, and no academic paper/PDF changed. H1488 remains
`FROZEN_UNOPENED`, R96 remains empirical/incomplete, and the authoritative
frontier remains 11 rows over ten operands.

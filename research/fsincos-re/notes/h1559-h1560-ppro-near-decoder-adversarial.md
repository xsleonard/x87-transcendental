# H1559--H1560 Pentium Pro near-decoder adversarial audit

Date: 2026-09-04

Status: **no historical paired fixture; H1557's headline is tail-inflated but
its cross-body structural signal survives. No exact decoder or selector.**

## Complete public-history audit

H1559 clones the complete public `ruikruik/utools` history at pinned HEAD
`ab6aa24ed91de1c048313c10cb7546ea3397b827`: 50 commits, 252 reachable
object records. It enumerates every historical path, including deleted and
renamed paths.

No `.uhex`, `.hex`, `.dat`, `.bin`, or `.out` build product and no `p6as` or
`p6scrambler` executable/source path exists anywhere in reachable history.
The Makefile only references the unreleased sibling `p6microcode-tools`.
Commit `7729bb4f4186e12cb134cfbdf6d7e66f57aa7ec4` introduced the generic
MSROM transform; commit `6f53f32e7c109b827067d78fd4da8188104d1c8a`
added the seven-dword Pentium Pro transform. Neither commit includes a saved
logical/physical build product.

This exhausts the repository-history route to the missing validation fixture.

## Repeated-wall adversary

The full `0x619` H1557 score contains a 15-copy terminal group. Those 15
groups account for 45/45 recognized uops and every zero field in that region.
After removing them, the H1557 configuration scores only 7/18 recognized
opcodes on the six unique `0x619` groups; it is not the winner under H1557's
original lexicographic ranking. The active-only best vector is
`(12 recognized, 11 flow-zero, 17 U1-zero, 5 U2-zero)` and is shared by three
candidates. Thus the original 52/63 recognition headline must not be cited as
standalone proof.

That adversary does not reduce the entire signal to the repeated wall. H1560
then removes repeated groups and joins the unique public bodies once each:
21 `0x611` groups, 21 `0x612` groups, and six `0x619` groups, for 144 decoded
uops. The H1557 configuration scores:

```text
recognized opcodes = 64 / 144
flow == 0          = 134 / 144
U1 == 0            = 144 / 144
U2 == 0            = 71 / 144
```

Across all 322,560 candidates, exactly one configuration meets or exceeds all
four values componentwise: H1557 itself. There is no strict dominator and no
second equal vector. Four deterministic randomized connected-surface controls
have global per-metric maxima of only 39--43 recognized, 60--61 flow-zero,
126--128 U1-zero, and 31--35 U2-zero. These maxima already give each random
surface the benefit of selecting its best configuration.

The conclusion is therefore deliberately two-sided:

- the `0x619` repeated tail materially inflates H1557's opcode headline; but
- it does not explain the same configuration's unique multimetric alignment
  across the nonrepeated union.

The union still transfers the CPUID-`0x619` CRBUS transform to `0x611` and
`0x612`, so this is strong structural evidence, not an exact logical-decoder
proof. A paired Pentium Pro logical/physical fixture or the public release of
the old-format `p6scrambler` remains necessary.

## Artifacts

- `experiments/h1559_utools_history_audit.py` SHA-256
  `c46337e69b6c2320a9cb08c9197a9bb02290eef48ce7ddeb746ad2d87d7f94cc`;
- `tmp/ledger33/current/h1559_utools_history_audit.json` SHA-256
  `e78f9382030713e3df22d32f1b96c79bbea085fc195320cc05271d1671edc481`;
- `experiments/h1560_ppro_near_decoder_adversarial.py` SHA-256
  `72cae06f6aca66188694f1dee1c3516b28beb9c3a4556aed988315e6631be354`;
- `tmp/ledger33/current/h1560_ppro_near_decoder_adversarial.json` SHA-256
  `e83c3ff3728481c92bc1b96e4260cc25df31a2367202af5fb30ceb2f4a723d7f`.

No update was loaded, no hardware or x87 instruction ran, no private ledger or
capture label was opened, and no academic paper/PDF changed. H1488 remains
`FROZEN_UNOPENED`, R96 remains empirical/incomplete, and the authoritative
frontier remains 11 rows over ten operands.

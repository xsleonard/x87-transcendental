# h1459 recovery of the previously unsupported public P6 patches

Date: 2026-09-03

Status: source recovery succeeded; R59 result is negative; no selector or
emulator change.

## Question

h1457 could decrypt 19 current official P6-family microcode files but had to
exclude 06-03-02, 06-08-03, and 06-0d-06 because the public patch toolkit has
no enabled base key for signatures 0x632, 0x683, and 0x6D6.  h1458 confirmed
that the toolkit's two historical Klamath guesses fail on 0x632.  h1459 asks
whether the public cipher and the update payload's own inert padding are
enough to recover the actual keys without a blind 32-bit brute force.

The answer is yes.  All four formerly opaque update segments are recovered
and independently integrity-verified.  Their newly visible micro-ops still
contain no candidate control for the unresolved R59 carry.

## Sources and recovery method

The binary inputs are the current official Intel files at repository head
`927e65c8d5a6e4ec05cc74b1778283ab2284d0c1`:

<https://github.com/intel/Intel-Linux-Processor-Microcode-Data-Files>

The cipher, FPROM table, and physical-to-logical mapping are from the public
patchtools and p6tools sources used by h1457:

- <https://github.com/peterbjornx/patchtools_pub>
- <https://github.com/ruikruik/p6tools>

The cipher state is 32 bits.  For a fixed FPROM polynomial its update is
linear over GF(2).  The public scrambler maps the two inert logical words to
eight possible physical triads.  If one such triad occurs in a patch, any two
adjacent known plaintext dwords expose two consecutive cipher states, so the
correct polynomial can be selected directly from the sixteen FPROM values
reachable by the public key-index mask.  This is a sixteen-candidate exact
transition test, not an unconstrained key search.

The recovered padding runs are long and unique:

- 0x632: variant 7, groups 6 through 20 (15 triads);
- both 0x683 segments: variant 0, groups 5 through 20 (16 triads); and
- 0x6D6: variant 0, groups 9 through 20 (12 triads).

For 0x632 and 0x6D6, the selected block transform has full rank, so the first
padding state inverts to a unique IV.  The first 0x683 segment leaves 32 IV
preimages.  Requiring its two official segments to share one processor base,
then checking each segment's derived key index, entire padding run, MSRAM
integrity word, and sixteen control-operation integrity words leaves exactly
one common base.  No decoded opcode or endpoint label participates in key
recovery.

## Recovered values and validation

The exact recovered values are:

| Signature | Base | Segment key(s) | IV(s) |
|---|---:|---:|---:|
| 0x1632 | `17AE63A2` | `63B44194` | `AF3FF70C` |
| 0x0683 | `EEA11EFA` | `8E7BCD5E`, `55555555` | `AD41D141`, `8F81197D` |
| 0x06D6 | `61E342A6` | `63B44194` | `0468F02D` |

The 0x632 base is the same public constant already used for later
Deschutes-B signatures, but neither historical Klamath guess tested in h1458.
The recovered 0x683 and 0x6D6 bases were absent from the public enabled key
table.

Every official 2 KiB segment passes the standard Intel checksum.  Each of the
four recovered MSRAM integrity words equals the indexed public FPROM value,
and all 64 recovered control-operation integrity words also match.  Thus 68
independent encrypted integrity positions validate the plaintext.  The four
segments descramble into 252 logical words: 181 inert padding words and 71
active words.

## R59 result

The 71 newly visible active words contain:

- zero floating add/subtract-family words;
- zero floating multiply, divide, or normalize-family words;
- zero opcode `0x1C1` forms;
- zero explicit `ArithFLAGS` sources.

There is one adjacent opcode-0x120 sample, at 0x683 revision 8 address 0x3FAC,
but its raw modifier is `U2.140`, its operands/destination differ, and it is
not a candidate tail form.  The recovered controls provide nine ordinary
match-patch hooks.  None changes the fact that update patches expose
replacement MSRAM only, not the base mask-ROM FSINCOS tail.

Therefore h1459 expands h1457 from the decryptable subset to all 22 current
official legacy-P6 files—48 update segments in total—with the same
candidate-tail result: zero.  This is now a complete current official-patch
census under the public format, but still not a base-ROM result and still not
a selector for R59.

## Reproduction and boundary

The recovery driver is
`experiments/h1459_recover_unsupported_p6_patches.py`; its report is
`tmp/ledger33/current/h1459_recover_unsupported_p6_patches.txt`.

- script SHA-256:
  `a2f2914f7da1641b8a7ef3380719d190de7eac68938ecd770579810863631f12`
- report SHA-256:
  `2500c3a4cd6e2ce6bd843c2bbed9648a07b580a698762fe671f82abbf6a8bd30`
- independent reproduction:
  `/tmp/h1459-repro.3KYEqg/report.txt`, byte-for-byte equal (`cmp=0`)
- claim boundary: the three named current official files, the named public
  FPROM/cipher, and the named public physical layout

No update was loaded, no x87 instruction was executed, and no private source
or capture ledger was used.  No selector or emulator behavior changed.  The
academic paper/PDF remains frozen, and the ledger-free frontier remains eleven
mode rows over ten operands.

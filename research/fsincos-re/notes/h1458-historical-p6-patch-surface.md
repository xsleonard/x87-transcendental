# h1458 historical P6 patch surface audit

Date: 2026-09-03

Status: exact 0x612-history result remains negative; the predecessor-key
boundary is superseded by h1459; no selector or emulator change.

## Question

h1457 found no candidate tail-control word in the decryptable files at the
current head of Intel's official Linux microcode repository.  h1458 checks the
remaining historical possibility: whether an old official revision contained
an exact 0x611/0x612 update or a decryptable predecessor update omitted from
the current public toolkit.

The audit is static.  It reads Git history and update bytes, checks the
standard Intel checksums, and evaluates the public patch cipher's first MSRAM
integrity word.  It never loads a microcode update and never executes x87.

## Sources and method

The official binary history is:

<https://github.com/intel/Intel-Linux-Processor-Microcode-Data-Files>

The audited head is
`927e65c8d5a6e4ec05cc74b1778283ab2284d0c1`; all 51 commits visible in the
clone were included in the filename and per-path blob census.  The public
patch cipher, key table, and FPROM constants are from:

<https://github.com/peterbjornx/patchtools_pub>

at `3f46fa404a6edabeb8d268e52f5301b0d1cf318f`.  Its exact
`fprom_data.c` has SHA-256
`758ce01ac9a4cbd37c3d847186f1f287a50d1818eb7b213221cc464a43681bb5`.

`experiments/h1458_historical_p6_patch_surface.py` independently implements
the public 37-clock block function and its documented MSRAM integrity check.
Before testing an unsupported file, it calibrates the implementation on all
three segments of the supported official 06-05-00 file.  All three decrypt to
the exact expected public FPROM integrity values.  This makes a coding error
in the negative 0x632 test substantially less plausible than an uncalibrated
port would.

The script then enumerates every historical blob for the three current files
which h1457 could not decrypt: 06-03-02, 06-08-03, and 06-0d-06.  It reports
each standard header and checksum, and tests both public historical Klamath
base-key guesses on the 0x632 body.

## Result

The full official history contains 142 family-6 filenames and 22 in the
legacy P6 model range through model 0x0D.  It contains no 06-01-* or 06-02-*
filename in any commit.  In particular, there is no official historical
update payload for the exact 0x611/0x612 lineage to decrypt.

There is one unique historical 06-03-02 blob: a single checksum-valid segment
for signature 0x1632, revision 2.  The cipher replica accepts all three 0x650
calibration segments, but neither Klamath guess validates this 0x632 segment:

```
base 30000000: got 1F039540, expected FPROM[C0] = B8000000
base 3A000000: got 191DBB49, expected FPROM[78] = A93188EF
```

This directly reproduces the public tool's reason for leaving the Klamath
cases disabled.  It does not distinguish a wrong base key from a different
FPROM or patch format, and therefore does not turn failed decryption into
plaintext.

The 06-08-03 history has two file blobs, but they contain the same two 0x683
segments in opposite order; there is no additional payload.  The 06-0d-06
history has one 0x6D6 segment.  The public key table supplies no working key
for either signature, so neither can add a verified raw word to h1457's
candidate-tail census.

At the h1458 boundary, the historical guesses contributed no exact 0x612
payload, no newly decryptable predecessor payload, and no recovered raw
control state.  The exact history result remains: no 06-01-* or 06-02-* file
exists in the official Git history.  The decryption boundary is superseded by
h1459, which uses the public physical padding as a cipher-state crib and
recovers all three formerly unsupported current files.  Their expanded raw
word census still contains zero R59 candidate-tail forms.

## Reproduction and boundary

The report is
`tmp/ledger33/current/h1458_historical_p6_patch_surface.txt`.

- script SHA-256:
  `542545f8c8f23f01076bd71f90c618a804f0e72a6ff4062d7eab70db816eee06`
- report SHA-256:
  `510c5d9f147cf90b9267ad70bca88eeac2211a1d1ab6ffe6381f849c0a46f706`
- independent output:
  `/tmp/h1458-report.txt`, byte-for-byte equal (`cmp=0`)
- claim boundary: complete Git history visible in the named official Intel
  repository plus the named public patchtools key/FPROM material

No selector or emulator behavior changed.  The academic paper/PDF remains
frozen, and the ledger-free frontier remains eleven mode rows over ten
operands.

# h1457 public P6 update-patch surface audit

Date: 2026-09-03

Status: negative evidence only; no selector or emulator change.

## Question

Public update patches provide raw micro-operation samples, but cannot
reconstruct the complete base ROM. This audit checks the complete decryptable
public update corpus for floating arithmetic and explicit arithmetic-status
operations that could inform the unresolved cosine arithmetic.

## Sources and scope

The binary inputs are the official Intel Linux microcode files:

<https://github.com/intel/Intel-Linux-Processor-Microcode-Data-Files>

The audited repository tree head was
`927e65c8d5a6e4ec05cc74b1778283ab2284d0c1`.  h1457 includes all 19
officially distributed P6-family files for which the public patch toolkit has
a working key:

```
06-05-00  06-05-01  06-05-02  06-05-03
06-06-00  06-06-05  06-06-0a  06-06-0d
06-07-01  06-07-02  06-07-03
06-08-01  06-08-06  06-08-0a
06-09-05
06-0a-00  06-0a-01
06-0b-01  06-0b-04
```

The unsupported 06-03-02, 06-08-03, and 06-0d-06 files are excluded rather
than accepting unverified plaintext.  Exact SHA-256 values for every included
official file and every 2 KiB update segment are in the report.

The decryptor is the public `patchtools_pub` source at head
`3f46fa404a6edabeb8d268e52f5301b0d1cf318f`:

<https://github.com/peterbjornx/patchtools_pub>

It was compiled with the source's portable `USE_C_BLOCKFUNC` path instead of
the optional x86-64 NASM fast path.  The resulting local analysis binary had
SHA-256
`3d7e2ce74f9c0139020bc26bd75ae4f11101c7911c49c5c381ae4e319e0cad89`.
The Python 3 port of the public descrambler was audited at head
`3ef88bcacd67864d0cf87eb624aa80033ec15505`; the exact `descramble.py` input
had SHA-256
`cf28923ed5976affc797aa82bd09673da909055614ece4f17a43fe55a238768c`.

The match-patch register ranges and high-half source/low-half replacement
address encoding follow the public P6 control-register map and its decoded
update examples.

No microcode update was loaded.  The work is static decryption and decoding in
temporary files only, and no x87 instruction was executed.

## Result

The 19 files contain 44 standard 2 KiB update segments for 19 processor
signatures.  Every segment passes the standard Intel 32-bit update checksum.
The decryptor reported zero integrity warnings.  Descrambling produced 2,772
logical micro-op words: 871 active words and 1,901 words in the two inert
padding encodings present in this corpus.

The arithmetic census reports:

- floating add/subtract family: 0
- opcode `0x1C1`: 0
- explicit `ArithFLAGS` as source one or source two: 0 + 0

The raw corpus does contain 20 adjacent but non-candidate samples.  Seventeen
are opcode `0x120`, but they use `U2.00` or `U2.10`, different destinations,
and do not expose a floating arithmetic operation. Three are opcode `0x7E9`, which confirms a raw
multiply-family alias, but they use `U2.00`, have destination register 0x08,
and do not expose the terminal writeback form.  There are no floating divide
or normalize families; the only floating-family words are those three
multiply aliases.

The 44 segments also contain 704 decrypted control writes.  Ninety-two decode
as active match-patch hooks under the public register map.  The two update
segments for signature 0x6B4 contribute six hooks, repeating the three source
addresses 0x043C, 0x3624, and 0x36D0. These patch records do not
identify the corresponding complete base-ROM routines.

Thus the official update corpus demonstrates that the public decrypt/descramble
pipeline is operational, but it contributes no floating add/subtract
sample or explicit arithmetic-status transfer.  It cannot constrain the R59 carry selector.  This is a
corpus absence, not proof that those forms do not exist in the base mask ROM.

## Reproduction and boundary

The driver is `experiments/h1457_public_p6_patch_surface.py`; it accepts local
copies of the official MCU files plus the public decryptor and descrambler, so
no external source or binary is copied into the repository.  The report is
`tmp/ledger33/current/h1457_public_p6_patch_surface.txt`.

- script SHA-256:
  `3389bf5a20d54c851350354003238fdbe1b29605784787342a20119954be452c`
- report SHA-256:
  `f8fe0dad9597fe464d47c6ecce8bdbaf7448eb712d384a2705d30c01ade907a7`
- independent reproduction:
  `/tmp/h1457-repro.PgV1Ph/report.txt`, byte-for-byte equal (`cmp=0`)
- claim boundary: public decryptable MSRAM updates only, not the base mask ROM

No selector or emulator behavior changed.  The academic paper/PDF remains
frozen, the ledger-free frontier remains eleven mode rows over ten operands,
and the active goal remains open.  Further patch-file mining is not justified
without a newly discovered update containing a candidate-tail form.

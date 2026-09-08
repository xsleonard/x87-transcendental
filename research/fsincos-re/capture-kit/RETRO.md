# Running the capture on old machines (no OS install needed)

The kit now bundles **static binaries** (`bin/x87_capture_x86_64`,
`bin/x87_capture_i686`) so the target machine needs **no compiler and no
installed OS** — just boot a Linux live image, run
`sh ./run_capture_prebuilt.sh`, and copy one file back.

If this machine already supplied the original full capture, use
`sh ./run_constraints_prebuilt.sh` instead.  It runs the 57,399 targeted
h59-h108 executions under RN/RD/RU and produces a small
`constraint-capture-*.tar.gz`.

For the standalone FSIN/FCOS sibling campaign, use
`sh ./run_standalone_prebuilt.sh`.  It records RN/RD/RU values and
per-instruction status for standalone and paired FSINCOS paths plus a smaller
bare-metal timing probe and the focused h130/h135 standalone-FSIN
discriminators, producing `standalone-capture-*.tar.gz`.  It also requires
no compiler.

Both binaries were built on Debian 12 and verified **bit-identical to
each other and to the original Skylake baseline** on the reference
machine (9k samples, rn/rd/fsin, C2 cases included).  They require a
live-image kernel **>= 3.2** (any image from ~2012 on) — do *not* use a
2000s-era live CD; the binary will refuse to start.  A modern kernel on
ancient hardware is fine and does not affect the x87 results.
TinyLinux 11.1 is a prebuilt-only target: do not compile there; run the
bundled i686 binary through `run_constraints_prebuilt.sh` or
`run_standalone_prebuilt.sh`.
The byte-reproducible build recipe and toolchain versions are recorded in
`PREBUILT_PROVENANCE.md`.

## Preparation (once, on any machine)

Put the whole `capture-kit/` folder on a USB stick (FAT32 is fine).
Running from the stick means the output lands on the stick directly —
no juggling files out of a RAM-only live session.

## Pentium E5800 (Core 2 era, x86-64) — easiest

1. Boot any stock 64-bit live USB (Debian/Ubuntu/whatever, "Try" mode).
2. Open a terminal, `cd` to the kit folder on the stick.
3. `sh ./run_capture_prebuilt.sh`  (the `sh` prefix matters — FAT32 sticks drop exec bits)
4. Send back `capture-*.tar.gz`.  Total time: minutes; disk untouched.

For a targeted replay requested after an earlier full capture, substitute
`sh ./run_constraints_prebuilt.sh` and send back
`constraint-capture-*.tar.gz`.

## Pentium II (i686) — the prize

Same procedure, but the live image must be **32-bit i686 and light**:

- **antiX** (486/686 flavor) — runs in ~192 MB RAM, kernel is modern. Best bet.
- **Alpine Linux** x86 (i686) — tiny; boots on very little RAM.
- **Debian 11/12 i386 live** — fine if the machine has >= 512 MB.

Machine notes:
- P II-era boards usually **cannot boot from USB** — burn the live image
  to a CD-R instead, and keep the kit on the USB stick (USB 1.1 ports
  work fine under Linux once booted; they're just slow — the ~48 MB of
  output takes a minute or two to write).
- No network needed.  Nothing touches the hard disk.
- The capture itself is a few minutes at 300–450 MHz.

## Pentium 4 — check the exact model first

`cat /proc/cpuinfo` on it, or check the sSpec: **Prescott 6xx / Cedar
Mill** parts are x86-64 → treat like the E5800 (any 64-bit live USB).
Earlier P4s (Willamette/Northwood/early Prescott) are 32-bit → treat
like the Pentium II (i686 live image; most P4 boards *can* boot USB).
Either way the same `run_capture_prebuilt.sh` picks the right binary
automatically via `uname -m`.

## Troubleshooting

- `Permission denied` running the *binary* (not the script): the stick is
  mounted `noexec`. Copy the whole kit folder to `/tmp`, run it there,
  then copy the `capture-*.tar.gz` back onto the stick.
- Kernel too old / binary won't start: use a newer live image (see the
  kernel >= 3.2 note above).

## What to send back

One archive per requested campaign: `capture-*.tar.gz`,
`constraint-capture-*.tar.gz`, or `standalone-capture-*.tar.gz`.  If the
tarball step failed, the corresponding raw `out/`, `constraint-out/`, or
`standalone-out/` directory zipped another way is just as good.

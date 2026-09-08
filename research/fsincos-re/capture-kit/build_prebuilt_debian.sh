#!/bin/sh
# Reproduce the committed static x86-64 and i686 capture binaries.
# Verified byte-for-byte with the Debian 12 toolchain documented in
# PREBUILT_PROVENANCE.md.  Linking with -s is NOT equivalent: link first,
# then invoke strip separately as below.
set -eu
cd "$(dirname "$0")"

CC=${CC:-gcc}
STRIP=${STRIP:-strip}

"$CC" -O2 -static -o bin/x87_capture_x86_64 x87_capture.c
"$STRIP" bin/x87_capture_x86_64
"$CC" -m32 -O2 -static -o bin/x87_capture_i686 x87_capture.c
"$STRIP" bin/x87_capture_i686

( cd bin && sha256sum -c SHA256SUMS )

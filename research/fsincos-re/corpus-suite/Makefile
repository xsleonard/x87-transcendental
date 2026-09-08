CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror -fno-builtin

.PHONY: all pentium test

all: capture_numeric

capture_numeric: capture_numeric.c
	$(CC) $(CFLAGS) -o $@ $<

# Compile on/for the intended target with a libc and startup runtime that
# support that CPU and OS. An i586 code-generation flag alone cannot make a
# modern distribution's libc suitable for an original Pentium.
pentium: capture_numeric.c
	$(CC) $(CFLAGS) -m32 -march=pentium -mno-sse -mno-sse2 -mno-mmx -mfpmath=387 -o capture_numeric_i586 $<

test:
	python3 test_suite.py -v

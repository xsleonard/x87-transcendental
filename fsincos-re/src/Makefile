CC      ?= cc
CFLAGS  ?= -O2 -Wall -Wextra -std=c11
LDLIBS  ?= -lm

all: fsincos_itanium fsincos_skylake

# Explicit opt-in packaging of the fixed standalone numerical candidate.
# This does not replace the historical all/standalone targets or enable FSINCOS.
# H1708: all now also uses these kernels; this target adds a restricted CLI.
general-candidate:
	python3 ../experiments/h1707_build_standalone_candidate.py --root .. \
		--binary general/fsin_fcos_candidate --cc "$(CC)" --cflags="-O2"

standalone: standalone/fsin_model standalone/fptan_model standalone/f2xm1_model

standalone/fsin_model: standalone/fsin_model.c
	$(CC) $(CFLAGS) -Werror -o $@ $< $(LDLIBS)

standalone/fptan_model: standalone/fptan_model.c
	$(CC) $(CFLAGS) -Werror -o $@ $< $(LDLIBS)

standalone/f2xm1_model: standalone/f2xm1_model.c
	$(CC) $(CFLAGS) -Werror -o $@ $< $(LDLIBS)

fsincos_itanium: fsincos_itanium.c ia64_sf.h ../data/frcpa-recip-table.h
	$(CC) $(CFLAGS) -o $@ fsincos_itanium.c $(LDLIBS)

fsincos_skylake: fsincos_skylake.c ia64_sf.h p5_rom_constants.h f2xm1_constants.h ../data/frcpa-recip-table.h \
		general/standalone_polynomial.h general/standalone_table.h general/standalone_tiny.h general/paired.h
	$(CC) $(CFLAGS) -Wno-unused-const-variable -o $@ fsincos_skylake.c $(LDLIBS)

fsin_exhaustive: fsin_exhaustive.c fsincos_skylake.c ia64_sf.h p5_rom_constants.h f2xm1_constants.h ../data/frcpa-recip-table.h \
		general/standalone_polynomial.h general/standalone_table.h general/standalone_tiny.h general/paired.h
	$(CC) $(CFLAGS) -O3 -Wno-unused-function -Wno-unused-const-variable -o $@ fsin_exhaustive.c $(LDLIBS) -pthread

sibling_exhaustive: sibling_exhaustive.c fsincos_skylake.c ia64_sf.h p5_rom_constants.h f2xm1_constants.h ../data/frcpa-recip-table.h \
		general/standalone_polynomial.h general/standalone_table.h general/standalone_tiny.h general/paired.h
	$(CC) $(CFLAGS) -O3 -Wno-unused-function -Wno-unused-const-variable -o $@ sibling_exhaustive.c $(LDLIBS) -pthread

check-fsin-h377: fsincos_skylake
	python3 ../experiments/h377_fsin_binary64_residual_gate.py ./fsincos_skylake

test: fsincos_itanium
	./fsincos_itanium --selftest
	python3 test_fma_oracle.py ./fsincos_itanium
	python3 test_endtoend.py ./fsincos_itanium

clean:
	for file in fsincos_itanium fsincos_skylake fsincos_ref fsin_exhaustive sibling_exhaustive \
		standalone/fsin_model standalone/fptan_model standalone/f2xm1_model; do \
		[ ! -e "$$file" ] || rm "$$file"; \
	done

.PHONY: all standalone general-candidate check-fsin-h377 test clean

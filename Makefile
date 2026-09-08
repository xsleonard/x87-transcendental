# Repository entry point for the maintained numerical models.
# Family Makefiles retain their existing output paths and dependencies.
PYTHON ?= python3

.PHONY: all check check-itanium help

all:
	$(MAKE) -C fsincos-re/src all
	$(MAKE) -C fsincos-re/fpatan-re all
	$(MAKE) -C fsincos-re/fyl2x-re all

check: all
	fsincos-re/src/fsincos_skylake --selftest
	$(MAKE) -C fsincos-re/src check-paired-regressions
	$(MAKE) -C fsincos-re/src check-f2xm1-regressions
	$(MAKE) -C fsincos-re/fpatan-re check
	$(MAKE) -C fsincos-re/fyl2x-re check PYTHON="$(PYTHON)"
	$(PYTHON) fsincos-re/paper/check_witnesses.py

check-itanium:
	$(MAKE) -C fsincos-re/src test

help:
	@printf '%s\n' \
		'make                Build all numerical models and C libraries' \
		'make check          Run saved-example regressions and API checks' \
		'make check-itanium  Run the additional Itanium reference checks' \
		'Source files and entry functions: SOURCE.md'

# Convenience commands; CMake owns the source lists and compiler settings.
CMAKE ?= $(shell command -v cmake 2>/dev/null)
ifeq ($(strip $(CMAKE)),)
ifneq ($(wildcard .tools/cmake/bin/cmake),)
CMAKE := $(CURDIR)/.tools/cmake/bin/cmake
else
CMAKE := cmake
endif
endif
BUILD_DIR ?= build
PYTHON ?= python3
CMAKE_ARGS ?=

.PHONY: all configure check tools examples install package check-legacy check-itanium help
all: configure
	$(CMAKE) --build "$(BUILD_DIR)" --target x87trans
configure:
	$(CMAKE) -S . -B "$(BUILD_DIR)" $(CMAKE_ARGS)
check:
	$(CMAKE) -S . -B "$(BUILD_DIR)" -DX87TRANS_BUILD_TESTS=ON $(CMAKE_ARGS)
	$(CMAKE) --build "$(BUILD_DIR)"
	$(CMAKE) -E env CTEST_OUTPUT_ON_FAILURE=1 $(CMAKE) --build "$(BUILD_DIR)" --target test
tools:
	$(CMAKE) -S . -B "$(BUILD_DIR)" -DX87TRANS_BUILD_TOOLS=ON $(CMAKE_ARGS)
	$(CMAKE) --build "$(BUILD_DIR)" --target x87trans-cli x87trans-outcomes fsincos_skylake fpatan x87-log
examples:
	$(CMAKE) -S . -B "$(BUILD_DIR)" -DX87TRANS_BUILD_EXAMPLES=ON $(CMAKE_ARGS)
	$(CMAKE) --build "$(BUILD_DIR)" --target x87trans-example
install: all
	$(CMAKE) --install "$(BUILD_DIR)"
package:
	$(PYTHON) tools/release/package.py
check-legacy:
	$(MAKE) -C research check
check-itanium:
	$(MAKE) -C research/fsincos-re/src test
help:
	@printf '%s\n' 'make          Build the C library' 'make check    Run offline library tests' \
	  'make tools    Build raw80 and compatibility CLIs' 'make examples Build the C example' \
	  'make package  Create a source-only archive' 'See docs/api.md and docs/integration.md'

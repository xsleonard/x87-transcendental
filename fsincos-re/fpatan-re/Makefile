# Portable numerical model and optional library. No native x87 is executed.
# Compiler/sanitizer choices never select a different numerical algorithm.
CC ?= cc
AR ?= ar
CFLAGS ?= -O2
CFLAGS += -std=c11 -Wall -Wextra -Werror
CPPFLAGS += $(shell pkg-config --cflags gmp 2>/dev/null)
LDFLAGS += $(shell pkg-config --libs-only-L gmp 2>/dev/null)
LDLIBS += -lgmp
BUILD_DIR ?= build

.PHONY: all check
all: $(BUILD_DIR)/fpatan $(BUILD_DIR)/libfpatan.a $(BUILD_DIR)/fpatan_batch

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/fpatan: fpatan_candidate.c | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) $< $(LDFLAGS) $(LDLIBS) -o $@

$(BUILD_DIR)/fpatan_library.o: fpatan_library.c fpatan_library.h fpatan_candidate.c | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c fpatan_library.c -o $@

$(BUILD_DIR)/libfpatan.a: $(BUILD_DIR)/fpatan_library.o
	$(AR) rcs $@ $<

$(BUILD_DIR)/fpatan_batch: example_batch.c fpatan_library.h $(BUILD_DIR)/libfpatan.a
	$(CC) $(CPPFLAGS) $(CFLAGS) example_batch.c $(BUILD_DIR)/libfpatan.a $(LDFLAGS) $(LDLIBS) -o $@

$(BUILD_DIR)/test_library: test_library.c fpatan_library.h $(BUILD_DIR)/libfpatan.a
	$(CC) $(CPPFLAGS) $(CFLAGS) test_library.c $(BUILD_DIR)/libfpatan.a $(LDFLAGS) $(LDLIBS) -o $@

check: all $(BUILD_DIR)/test_library
	$(BUILD_DIR)/fpatan --selftest
	$(BUILD_DIR)/test_library

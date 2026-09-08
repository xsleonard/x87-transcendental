# Portable C model. No native x87 or remote capture is executed by this build.
CC ?= cc
AR ?= ar
PYTHON ?= python3
CFLAGS ?= -O2
CFLAGS += -std=c11 -Wall -Wextra -Werror
CPPFLAGS += $(shell pkg-config --cflags gmp 2>/dev/null)
LDFLAGS += $(shell pkg-config --libs-only-L gmp 2>/dev/null)
LDLIBS += -lgmp
BUILD_DIR ?= build

.PHONY: all check
all: $(BUILD_DIR)/x87-log $(BUILD_DIR)/libx87log.a $(BUILD_DIR)/log_batch

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/x87-log: log_model.c | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) $< $(LDFLAGS) $(LDLIBS) -o $@

$(BUILD_DIR)/log_library.o: log_library.c log_library.h log_model.c | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c log_library.c -o $@

$(BUILD_DIR)/libx87log.a: $(BUILD_DIR)/log_library.o
	$(AR) rcs $@ $<

$(BUILD_DIR)/log_batch: example_batch.c log_library.h $(BUILD_DIR)/libx87log.a
	$(CC) $(CPPFLAGS) $(CFLAGS) example_batch.c $(BUILD_DIR)/libx87log.a $(LDFLAGS) $(LDLIBS) -o $@

$(BUILD_DIR)/test_api: test_api.c log_library.h $(BUILD_DIR)/libx87log.a
	$(CC) $(CPPFLAGS) $(CFLAGS) test_api.c $(BUILD_DIR)/libx87log.a $(LDFLAGS) $(LDLIBS) -o $@

check: all $(BUILD_DIR)/test_api
	$(BUILD_DIR)/test_api
	$(PYTHON) check_witnesses.py --build $(BUILD_DIR)

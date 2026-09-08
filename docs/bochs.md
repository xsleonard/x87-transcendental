# Bochs integration

The adapter in `integrations/bochs/x87trans.inc` runs inside Bochs's existing
instruction handlers. It covers all eight functions and both masked and unmasked
outcomes. Bochs retains pending-exception checks, empty/full-stack priority,
TOP/tags, ES/B, instruction pointers and delivery. OUTSIDE_SCOPE and reserved PC
retain the original Bochs fallback policy.

The reproducible integration targets Bochs commit
`c4b78268fe79e03cbc04c512d2b47e40e03cdfb9`. Use a disposable checkout: the preparation
script validates the revision and insertion points and refuses repeat application.
It leaves the original handlers and their comments available as fallback.

```sh
git clone https://github.com/bochs-emu/Bochs.git /tmp/bochs-x87trans
git -C /tmp/bochs-x87trans checkout c4b78268fe79e03cbc04c512d2b47e40e03cdfb9
python3 tools/integration/prepare_bochs.py /tmp/bochs-x87trans
```

Build a static x87trans library first. Configure Bochs from its `bochs/` directory
using absolute include/library paths appropriate to the installation:

```sh
./configure --with-nogui --with-x=no --disable-readline \
  --enable-x86-64 --enable-avx --enable-debugger --enable-iodebug \
  CXXFLAGS='-O2 -std=c++11 -I/path/to/x87trans/include' \
  LIBS='/path/to/x87trans/build/libx87trans.a -L/path/to/gmp/lib -lgmp'
make -j4
```

The Bochs checkout keeps its original license. The source package includes our
adapter and preparation/guest-test scripts, not a redistributed Bochs tree.
Relink Bochs after changing the external static archive; its makefiles do not
track changes to that archive automatically.

Run the emulator integration against retained hardware witnesses:

```sh
python3 tools/integration/run_bochs.py /tmp/bochs-x87trans/bochs/bochs \
  tests/data/bochs-state-witnesses.json tests/data/outcome-witnesses.json.gz
```

The runner uses Clang's i386 assembler to build a 64 KiB real-mode ROM. Each case
restores raw operands and controls with FXRSTOR, executes the actual guest
instruction, saves state before FWAIT, and records the guest #MF handler's state.
It compares raw register bits, all eight register slots, TOP, abridged tags,
exception flags, ES/B, defined C1/C2 and delivery position. Evidence labels
separate full hardware state captures from older captures that measured only
results/flags and use the specified stack behavior for the expected state.
Bochs executes these tests in software; it is not used as the numerical oracle.

The much smaller `examples/emulator_adapter.c` is an all-masked logical-stack
fixture. It explicitly rejects unmasked completion and is not a substitute for
the Bochs instruction integration.

# Building and embedding

Prerequisites: CMake 3.20+, C11 with `unsigned __int128`, and GMP headers/library.
GCC/Clang are the initial compiler targets. The reorganization was exercised with
Apple Clang on AArch64 macOS; other platform coverage must be recorded separately.
The public header is usable from both C and C++ and contains no GMP types.
Python 3 is needed only for the saved-witness test target and development scripts.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

To vendor the source in a CMake consumer:

```cmake
add_subdirectory(path/to/x87-transcendental)
target_link_libraries(your_emulator PRIVATE x87trans::x87trans)
```

To install and consume separately:

```sh
cmake --install build --prefix /desired/prefix
```

```cmake
find_package(x87trans 0.1 CONFIG REQUIRED)
target_link_libraries(your_emulator PRIVATE x87trans::x87trans)
```

Pass the installation root in `CMAKE_PREFIX_PATH` when necessary. GMP discovery
uses pkg-config hints and ordinary CMake library/header searches. Explicit
`GMP_INCLUDE_DIR` and `GMP_LIBRARY` overrides are also supported. The static
export propagates GMP's link dependency. For non-CMake consumers:

```sh
cc client.c $(pkg-config --cflags --libs --static x87trans) -o client
```

Set `BUILD_SHARED_LIBS=ON` for a shared library. Only `x87t_` API functions are
exported; arithmetic helpers and constants remain private. Set build options
`X87TRANS_BUILD_TOOLS`, `X87TRANS_BUILD_EXAMPLES`, `X87TRANS_BUILD_TESTS` or
`X87TRANS_BUILD_COMPAT` to add those targets. These options do not select
numerical algorithms. Normal builds produce the library alone.

The optional compatibility libraries, `fpatan-compat` and `log-compat`, expose
the previous C headers from `tools/compat/`. They link the canonical library.
Their headers are not installed as part of the new API.

The [evaluation example](../examples/evaluate.c) shows ordinary C calls.
The [adapter fixture](../examples/emulator_adapter.c) demonstrates caller-side
writeback for a logical ST array. It checks metadata availability before
modifying state, preserves registers on a range return and keeps push/pop order
explicit. Its tests cover binary pop, paired push, full-stack rejection,
sticky flags and refusal to use incomplete metadata. It assumes the caller has
already handled pending exceptions and instruction-specific stack priority;
it is not a complete x87 execution engine.

For another arithmetic library's ext80 format, convert the sign/exponent and
significand fields explicitly. Do not alias structures, serialize their padding,
or assume its exception flag values equal x87 bit positions. Keep guest rounding
and exception handling explicit at the call site.

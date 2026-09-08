#include "emulator_adapter.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(c)                                                                                   \
    do {                                                                                           \
        if (!(c)) {                                                                                \
            fprintf(stderr, "adapter check: %d\n", __LINE__);                                      \
            abort();                                                                               \
        }                                                                                          \
    } while (0)
int main(void)
{
    x87t_context *ctx = x87t_create();
    CHECK(ctx);
    x87t_control control = X87T_CONTROL_INIT;
    example_fpu fpu = {{{0x3fff, UINT64_C(0x8000000000000000)},
                        {0x3ffe, UINT64_C(0x8000000000000000)},
                        {0x4002, UINT64_C(0xa000000000000000)}},
                       3,
                       1};
    x87t_raw80 deeper = fpu.st[2];
    x87t_result result;
    CHECK(x87t_fpatan(ctx, fpu.st[1], fpu.st[0], &control, &result) == X87T_OK);
    CHECK(example_apply_masked(&fpu, &result, X87T_C1) == EXAMPLE_APPLIED);
    CHECK(fpu.depth == 2 && fpu.st[0].sig == result.primary.sig && fpu.st[1].sig == deeper.sig);
    CHECK((fpu.status & 1) && (fpu.status & X87T_PE));
    CHECK(x87t_fsincos(ctx, fpu.st[0], &control, &result) == X87T_OK);
    example_fpu before = fpu;
    CHECK(example_apply_masked(&fpu, &result, X87T_C1 | X87T_C2) == EXAMPLE_NEEDS_METADATA);
    CHECK(!memcmp(&fpu, &before, sizeof(fpu)));
    x87t_raw80 large = {0x403e, UINT64_C(0x8000000000000000)};
    CHECK(x87t_fsincos(ctx, large, &control, &result) == X87T_OK);
    CHECK(example_apply_masked(&fpu, &result, X87T_C2) == EXAMPLE_APPLIED);
    CHECK(fpu.depth == before.depth && fpu.st[0].sig == before.st[0].sig && (fpu.status & X87T_C2));
    /* Synthetic complete metadata tests the adapter's pair ordering, not
     * additional production-library exception support. */
    memset(&result, 0, sizeof(result));
    result.values = X87T_PRIMARY | X87T_PUSHED;
    result.primary = deeper;
    result.pushed = large;
    result.exceptions_known = 63;
    result.destination = X87T_REPLACE_ST0_PUSH;
    CHECK(example_apply_masked(&fpu, &result, 0) == EXAMPLE_APPLIED);
    CHECK(fpu.depth == 3 && fpu.st[0].se == large.se && fpu.st[1].sig == deeper.sig);
    fpu.depth = 8;
    before = fpu;
    CHECK(example_apply_masked(&fpu, &result, 0) == EXAMPLE_BAD_STATE);
    CHECK(!memcmp(&fpu, &before, sizeof(fpu)));
    x87t_destroy(ctx);
    puts("PASS masked writeback fixture");
    return 0;
}

/* API boundaries and failure atomicity, separate from hardware replay tests. */
#include "log_library.h"
/* Keep these test checks active in Release builds. */
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    x87_log *ctx = x87_log_create();
    assert(ctx);
    x87_log_value one = {0x3fff, UINT64_C(0x8000000000000000)};
    x87_log_value zero = {0, 0}, bound = {0x3ffd, UINT64_C(0x95f619980c4336f7)};
    x87_log_result result;
    memset(&result, 0xa5, sizeof(result));
    x87_log_result sentinel = result;
    assert(x87_log_evaluate(NULL, X87_FYL2X, one, one, X87_LOG_RN, 64, &result) ==
           X87_LOG_BAD_ARGUMENT);
    assert(!memcmp(&result, &sentinel, sizeof(result)));
    assert(x87_log_evaluate(ctx, (x87_log_instruction)2, one, one, X87_LOG_RN, 64, &result) ==
           X87_LOG_BAD_ARGUMENT);
    assert(x87_log_evaluate(ctx, X87_FYL2X, one, one, (x87_log_round)4, 64, &result) ==
           X87_LOG_BAD_ARGUMENT);
    assert(x87_log_evaluate(ctx, X87_FYL2X, one, one, X87_LOG_RN, 25, &result) ==
           X87_LOG_BAD_ARGUMENT);
    assert(!memcmp(&result, &sentinel, sizeof(result)));
    assert(x87_log_evaluate(ctx, X87_FYL2XP1, one, one, X87_LOG_RN, 64, &result) ==
           X87_LOG_OUTSIDE_SCOPE);
    assert(!memcmp(&result, &sentinel, sizeof(result)));
    bound.sig++;
    assert(x87_log_evaluate(ctx, X87_FYL2XP1, one, bound, X87_LOG_RN, 64, &result) ==
           X87_LOG_OUTSIDE_SCOPE);
    assert(!memcmp(&result, &sentinel, sizeof(result)));
    bound.sig--;
    assert(x87_log_evaluate(ctx, X87_FYL2XP1, one, bound, X87_LOG_RN, 64, &result) == X87_LOG_OK);
    const unsigned pcs[] = {24, 53, 64};
    for (unsigned i = 0; i < 3; i++)
        for (int rc = 0; rc < 4; rc++) {
            assert(x87_log_evaluate(ctx, X87_FYL2X, one, one, (x87_log_round)rc, pcs[i], &result) ==
                   X87_LOG_OK);
            assert(!result.value.se && !result.value.sig && !result.c1 && !result.exceptions);
            assert(
                x87_log_evaluate(ctx, X87_FYL2XP1, one, zero, (x87_log_round)rc, pcs[i], &result) ==
                X87_LOG_OK);
            assert(!result.value.se && !result.value.sig && !result.c1 && !result.exceptions);
        }
    x87_log_destroy(ctx);
    x87_log_destroy(NULL);
    puts("PASS logarithm API validation, domain endpoints and failure atomicity");
    return 0;
}

/* Public API contracts and shared-context concurrency. Checks stay active
 * under NDEBUG so Release builds exercise the same assertions. */
#include "x87trans/x87trans.h"
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(c)                                                                                   \
    do {                                                                                           \
        if (!(c)) {                                                                                \
            fprintf(stderr, "check failed at line %d: %s\n", __LINE__, #c);                        \
            abort();                                                                               \
        }                                                                                          \
    } while (0)

typedef struct {
    x87t_error error;
    x87t_result result;
} answer;
static const x87t_raw80 inputs[] = {{0, 0},
                                    {0x8000, 0},
                                    {0x3ffe, UINT64_C(0x8000000000000000)},
                                    {0xbffe, UINT64_C(0xcccccccccccccccc)},
                                    {0x4000, UINT64_C(0xc90fdaa22168c235)},
                                    {0x403d, UINT64_MAX},
                                    {0x403e, UINT64_C(0x8000000000000000)},
                                    {0, 1},
                                    {0x8000, UINT64_MAX >> 1},
                                    {1, UINT64_C(0x8000000000000000)},
                                    {0, UINT64_C(0x8000000000000000)},
                                    {0x7fff, UINT64_C(0x8000000000000000)},
                                    {0xffff, UINT64_C(0xc000000000001234)},
                                    {0x7fff, UINT64_C(0x8000000000001234)},
                                    {0x3fff, 1},
                                    {0x3ffc, UINT64_C(0xe79000000c3e46e7)}};
enum { INPUTS = sizeof(inputs) / sizeof(inputs[0]), MODES = 4, OPS = 8 };
static answer expected[INPUTS][MODES][OPS];
static answer evaluate(const x87t_context *ctx, unsigned input, unsigned mode, unsigned op)
{
    x87t_control control = X87T_CONTROL_INIT;
    control.rounding = (x87t_round)mode;
    control.precision_bits = (unsigned[]){24, 53, 64, 64}[mode];
    x87t_raw80 x = inputs[input], y = inputs[(input + 2) % INPUTS];
    answer a = {0};
    switch (op) {
    case 0:
        a.error = x87t_fsin(ctx, x, &control, &a.result);
        break;
    case 1:
        a.error = x87t_fcos(ctx, x, &control, &a.result);
        break;
    case 2:
        a.error = x87t_fsincos(ctx, x, &control, &a.result);
        break;
    case 3:
        a.error = x87t_fptan(ctx, x, &control, &a.result);
        break;
    case 4:
        a.error = x87t_f2xm1(ctx, x, &control, &a.result);
        break;
    case 5:
        a.error = x87t_fpatan(ctx, y, x, &control, &a.result);
        break;
    case 6:
        a.error = x87t_fyl2x(ctx, y, x, &control, &a.result);
        break;
    default:
        a.error = x87t_fyl2xp1(ctx, y, x, &control, &a.result);
        break;
    }
    return a;
}
static int same(const x87t_result *a, const x87t_result *b)
{
    return a->primary.se == b->primary.se && a->primary.sig == b->primary.sig &&
           a->pushed.se == b->pushed.se && a->pushed.sig == b->pushed.sig &&
           a->values == b->values && a->cc == b->cc && a->cc_known == b->cc_known &&
           a->exceptions == b->exceptions && a->exceptions_known == b->exceptions_known &&
           a->first_unmasked == b->first_unmasked &&
           a->completion == b->completion && a->destination == b->destination;
}
static void *worker(void *pointer)
{
    const x87t_context *ctx = pointer;
    for (unsigned repeat = 0; repeat < 4; ++repeat)
        for (unsigned i = 0; i < INPUTS; ++i)
            for (unsigned rc = 0; rc < MODES; ++rc)
                for (unsigned op = 0; op < OPS; ++op) {
                    answer a = evaluate(ctx, i, rc, op), *b = &expected[i][rc][op];
                    CHECK(a.error == b->error);
                    if (!a.error)
                        CHECK(same(&a.result, &b->result));
                }
    return NULL;
}
int main(void)
{
    x87t_context *ctx = x87t_create();
    CHECK(ctx);
    x87t_control control = X87T_CONTROL_INIT;
    x87t_result result, before;
    memset(&result, 0xa5, sizeof(result));
    before = result;
    CHECK(x87t_fsin(NULL, inputs[0], &control, &result) == X87T_BAD_ARGUMENT);
    CHECK(!memcmp(&result, &before, sizeof(result)));
    CHECK(x87t_fsin(ctx, inputs[0], NULL, &result) == X87T_BAD_ARGUMENT);
    CHECK(x87t_fsin(ctx, inputs[0], &control, NULL) == X87T_BAD_ARGUMENT);
    control.rounding = (x87t_round)99;
    CHECK(x87t_fsin(ctx, inputs[0], &control, &result) == X87T_BAD_ARGUMENT);
    control.rounding = X87T_RN;
    control.precision_bits = 17;
    CHECK(x87t_fsin(ctx, inputs[0], &control, &result) == X87T_UNSUPPORTED_CONTROL);
    control.precision_bits = 64;
    control.exception_masks = 64;
    CHECK(x87t_fsin(ctx, inputs[0], &control, &result) == X87T_UNSUPPORTED_CONTROL);
    CHECK(!memcmp(&result, &before, sizeof(result)));
    control.exception_masks = 63;
    CHECK(x87t_f2xm1(ctx, inputs[11], &control, &result) == X87T_OUTSIDE_SCOPE);
    CHECK(!memcmp(&result, &before, sizeof(result)));
    CHECK(x87t_fptan(ctx, inputs[14], &control, &result) == X87T_OK);
    CHECK(result.exceptions == X87T_IE && result.exceptions_known == 63 &&
          result.primary.se == 0xffff && result.primary.sig == UINT64_C(0xc000000000000000));
    CHECK(x87t_fsin(ctx, inputs[6], &control, &result) == X87T_OK);
    CHECK(result.completion == X87T_RANGE_RETURN && result.values == 0 &&
          result.destination == X87T_NO_WRITE && result.cc == X87T_C2);
    CHECK(x87t_fsin(ctx, inputs[2], &control, &result) == X87T_OK);
    CHECK(result.exceptions_known == 63 && result.exceptions == X87T_PE);
    /* Unknown status is explicitly marked. */
    CHECK(result.cc_known == (X87T_C1 | X87T_C2));
    for (unsigned i = 0; i < INPUTS; ++i) {
        uint8_t memory[10];
        x87t_store_le(memory, inputs[i]);
        x87t_raw80 restored = x87t_load_le(memory);
        CHECK(restored.se == inputs[i].se && restored.sig == inputs[i].sig);
        CHECK(memory[0] == (uint8_t)inputs[i].sig && memory[9] == (uint8_t)(inputs[i].se >> 8));
        for (unsigned rc = 0; rc < MODES; ++rc)
            for (unsigned op = 0; op < OPS; ++op)
                expected[i][rc][op] = evaluate(ctx, i, rc, op);
    }
    pthread_t threads[4];
    for (unsigned i = 0; i < 4; ++i)
        CHECK(!pthread_create(&threads[i], NULL, worker, ctx));
    for (unsigned i = 0; i < 4; ++i)
        CHECK(!pthread_join(threads[i], NULL));
    x87t_destroy(ctx);
    x87t_destroy(NULL);
    puts("PASS public controls, failure atomicity, raw80, C2, metadata and concurrent calls");
    return 0;
}

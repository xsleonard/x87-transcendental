/* Exact residue enumeration for the analysis-only boundary filters.
 * Every input is bounded so intermediate products fit unsigned 128 bits.
 * This file contains no floating arithmetic, model constants or FPATAN.
 */
#include <assert.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef __uint128_t wide;

static wide floor_sum(uint64_t n, wide modulus, wide slope, wide intercept)
{
    wide total = 0;
    assert(n <= (UINT64_C(1) << 20) && modulus > 0);
    for (;;) {
        if (slope >= modulus) {
            total += (wide)n * (n ? n - 1 : 0) * (slope / modulus) / 2;
            slope %= modulus;
        }
        if (intercept >= modulus) {
            total += (wide)n * (intercept / modulus);
            intercept %= modulus;
        }
        wide maximum = slope * n + intercept;
        if (maximum < modulus)
            return total;
        n = (uint64_t)(maximum / modulus);
        intercept = maximum % modulus;
        wide next_modulus = slope;
        slope = modulus;
        modulus = next_modulus;
    }
}

static uint64_t below_count(uint64_t n, wide modulus, wide slope,
                            wide intercept, wide width)
{
    if (width == 0)
        return 0;
    if (width >= modulus)
        return n;
    wide difference = floor_sum(n, modulus, slope, intercept + modulus - width)
                    - floor_sum(n, modulus, slope, intercept);
    assert(difference <= n);
    return n - (uint64_t)difference;
}

typedef struct {
    wide modulus, slope, intercept, lower, upper;
    uint64_t *output, used;
} enumeration;

static uint64_t range_count(const enumeration *e, uint64_t start, uint64_t n)
{
    wide intercept = (e->intercept + e->slope * start) % e->modulus;
    return below_count(n, e->modulus, e->slope, intercept, e->lower + 1)
         + n - below_count(n, e->modulus, e->slope, intercept, e->modulus - e->upper);
}

static void enumerate(enumeration *e, uint64_t start, uint64_t n)
{
    if (!n || !range_count(e, start, n))
        return;
    if (n <= 32) {
        wide residue = (e->intercept + e->slope * start) % e->modulus;
        for (uint64_t i = 0; i < n; i++) {
            if (residue <= e->lower || residue >= e->modulus - e->upper)
                e->output[e->used++] = start + i;
            residue += e->slope;
            if (residue >= e->modulus)
                residue -= e->modulus;
        }
    } else {
        uint64_t left = n / 2;
        enumerate(e, start, left);
        enumerate(e, start + left, n - left);
    }
}

/* Return required capacity without writing when output is too small.
 * UINT64_MAX reports a rejected input, never a silently truncated search.
 * In addition to modulus<2^108 and n<=2^20, explicitly require
 * modulus*(n+1)<=UINT128_MAX, so slope*n+intercept cannot overflow.
 */
uint64_t d0060_offsets(uint64_t n, const uint64_t words[10],
                       uint64_t *output, uint64_t capacity)
{
    wide values[5];
    for (unsigned i = 0; i < 5; i++)
        values[i] = ((wide)words[2 * i] << 64) | words[2 * i + 1];
    enumeration e = {values[0], values[1], values[2], values[3], values[4], output, 0};
    if (n > (UINT64_C(1) << 20) || !e.modulus || e.modulus >= ((wide)1 << 108)
            || e.lower > e.modulus || e.upper > e.modulus
            || e.modulus > (~(wide)0) / (n + 1))
        return UINT64_MAX;
    e.slope %= e.modulus;
    e.intercept %= e.modulus;
    if (e.lower + e.upper + 1 >= e.modulus) {
        if (capacity >= n && output)
            for (uint64_t i = 0; i < n; i++)
                output[i] = i;
        return n;
    }
    uint64_t count = range_count(&e, 0, n);
    if (count > capacity || !output)
        return count;
    enumerate(&e, 0, n);
    assert(e.used == count);
    return count;
}

#ifdef D0060_TEST_MAIN
static wide parse_hex(const char *text)
{
    assert(strlen(text) <= 32);
    wide result = 0;
    for (const char *c = text; *c; c++) {
        unsigned digit = *c >= '0' && *c <= '9' ? (unsigned)(*c - '0')
                       : *c >= 'a' && *c <= 'f' ? (unsigned)(*c - 'a' + 10) : 16;
        assert(digit < 16);
        result = (result << 4) | digit;
    }
    return result;
}

int main(void)
{
    uint64_t n;
    char text[5][33];
    while (scanf("%" SCNu64 " %32s %32s %32s %32s %32s", &n,
                  text[0], text[1], text[2], text[3], text[4]) == 6) {
        uint64_t words[10];
        for (unsigned i = 0; i < 5; i++) {
            wide value = parse_hex(text[i]);
            words[2 * i] = (uint64_t)(value >> 64);
            words[2 * i + 1] = (uint64_t)value;
        }
        uint64_t count = d0060_offsets(n, words, NULL, 0);
        assert(count != UINT64_MAX);
        uint64_t *result = malloc((count ? count : 1) * sizeof(*result));
        assert(result);
        assert(d0060_offsets(n, words, result, count) == count);
        printf("%" PRIu64, count);
        for (uint64_t i = 0; i < count; i++)
            printf(" %" PRIu64, result[i]);
        putchar('\n');
        free(result);
    }
    return ferror(stdin) || ferror(stdout);
}
#endif

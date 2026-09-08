#ifndef X87TRANS_INTERNAL_FINITE_H
#define X87TRANS_INTERNAL_FINITE_H
#include "internal/api.h"

typedef x87t_raw80 raw80;
enum mode { RN, RD, RU, RZ, CHOP };

/* Exact finite dyadic: (-1)^negative * word * 2^exponent. Words are little
 * endian; nonzero values have an odd magnitude. Exponents are independent of
 * the host and of the raw80 exponent range. No allocation or host FP is used.
 * Products accept at most 128 bits per operand; sums are rounded explicitly.
 * See docs/finite-arithmetic.md for bounds and the signed-tail argument. */
typedef struct {
    uint64_t word[4];
    int exponent;
    unsigned negative;
} fv;

fv x87t_internal_fuint(uint64_t);
fv x87t_internal_fhex(const char *, int exponent, unsigned negative);
fv x87t_internal_fdecode(raw80);
fv x87t_internal_fscale(fv, int);
fv x87t_internal_fneg(fv);
fv x87t_internal_fabs(fv);
int x87t_internal_fsign(fv);
int x87t_internal_fexp(fv);
int x87t_internal_fcmp(fv, fv);
int x87t_internal_fratio_exp(fv, fv);
fv x87t_internal_fmul(fv, fv);
fv x87t_internal_fround(fv, int bits, enum mode);
fv x87t_internal_fadd(fv, fv, int bits, enum mode);
fv x87t_internal_fdiv(fv, fv, int bits, enum mode);
uint64_t x87t_internal_ffloor(fv);
raw80 x87t_internal_fencode(fv, enum mode, int *c1);
/* Quantize the exact sum once. FPATAN detects tininess before rounding and
 * adjusts a tiny unmasked result by 2^24576 before architectural encoding. */
raw80 x87t_internal_fencode_sum(fv, fv, enum mode, unsigned masks, int *c1, int *tiny);
#endif

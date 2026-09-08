#ifndef X87TRANS_INTERNAL_FINITE_H
#define X87TRANS_INTERNAL_FINITE_H
#include "internal/api.h"

typedef x87t_raw80 raw80;
/* RN rounds to nearest, with ties to even. RD rounds toward -infinity;
 * RU toward +infinity. RZ and CHOP truncate toward zero. Only the raw80
 * encoding functions return the rounding decision as C1.
 */
enum mode { RN, RD, RU, RZ, CHOP };

/* Exact finite dyadic: (-1)^negative * word * 2^exponent. Words are little
 * endian; nonzero values have an odd magnitude. Exponents are independent of
 * the host and of the raw80 exponent range. No allocation or host FP is used.
 * Products accept at most 128 bits per operand; sums are rounded explicitly.
 * Addition keeps a bounded integer prefix and records any discarded tail,
 * including its effect on a subtraction borrow, until the requested cut. */
/* The magnitude is sum(word[j]*2^(64*j), j=0..3). These four words can
 * hold an exact product; addition and division use a separately requested
 * result width. Normalization removes trailing zero bits and increases
 * exponent by the same amount. Zero has all fields zero, including its sign.
 * Assigning an fv never rounds. Addition uses 320 bits and a flag for any
 * discarded fraction, enough to round the sum to at most 128 bits.
 */
typedef struct {
    uint64_t word[4];
    int exponent;
    unsigned negative;
} fv;

/* These constructors do not round. fhex accepts hexadecimal digits without
 * a 0x or sign prefix, up to a 256-bit integer; exponent and sign are separate
 * arguments. An empty string gives zero. fdecode reads finite raw80 values,
 * including denormals and pseudo-denormals. The caller must first handle
 * NaNs, infinities and unsupported encodings. fdecode does not raise DE,
 * and the sign of a raw80 zero is lost.
 */
fv x87t_internal_fuint(uint64_t);
fv x87t_internal_fhex(const char *, int exponent, unsigned negative);
fv x87t_internal_fdecode(raw80);
fv x87t_internal_fscale(fv, int);
fv x87t_internal_fneg(fv);
fv x87t_internal_fabs(fv);
/* Sign, comparison and scaling are exact. For nonzero a, fexp returns
 * floor(log2(abs(a))); for zero it returns -1 by convention. fratio_exp
 * returns floor(log2(abs(a/b))) and requires both operands to be nonzero.
 * Exponents and scale adjustments must fit in a C int.
 */
int x87t_internal_fsign(fv);
int x87t_internal_fexp(fv);
int x87t_internal_fcmp(fv, fv);
int x87t_internal_fratio_exp(fv, fv);
/* fmul takes magnitudes of at most 128 bits each and returns their exact
 * product of at most 256 bits. fround and fadd round once to the requested
 * width, which must be in [1,128]. fadd does not round its operands first;
 * it keeps enough information to round the sum even when their exponents
 * are far apart. fdiv also requires magnitudes of at most 128 bits and a
 * nonzero divisor. It rounds the quotient using the exact remainder.
 * None of these operations limits the exponent to the raw80 range.
 */
fv x87t_internal_fmul(fv, fv);
fv x87t_internal_fround(fv, int bits, enum mode);
fv x87t_internal_fadd(fv, fv, int bits, enum mode);
fv x87t_internal_fdiv(fv, fv, int bits, enum mode);
/* ffloor requires 0 <= a < 2^64 and returns floor(a). fencode rounds to
 * raw80 using rc, handling subnormal values and overflow. It sets c1 when
 * rounding increments the magnitude; on overflow, c1 is 1 for infinity and
 * 0 for the largest finite value. The caller sets exception flags and
 * decides whether to write the result. A negative nonzero value keeps its
 * sign if rounded to zero; an exact fv zero has no sign to recover.
 */
uint64_t x87t_internal_ffloor(fv);
raw80 x87t_internal_fencode(fv, enum mode, int *c1);
/* Quantize the exact sum once. FPATAN detects tininess before rounding and
 * adjusts a tiny unmasked result by 2^24576 before architectural encoding. */
/* tiny is set if the nonzero sum has magnitude below 2^-16382 before the
 * adjustment. If it is tiny and UE is unmasked, C1 comes from rounding the
 * scaled sum. The logarithms use a different test: they round their final
 * product to 64 bits, with no exponent limit, before checking tininess. */
raw80 x87t_internal_fencode_sum(fv, fv, enum mode, unsigned masks, int *c1, int *tiny);
#endif

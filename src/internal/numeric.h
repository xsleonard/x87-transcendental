#ifndef X87TRANS_INTERNAL_NUMERIC_H
#define X87TRANS_INTERNAL_NUMERIC_H
#include "internal/api.h"
#include "constants/trig.h"
#include <assert.h>
typedef unsigned __int128 u128;
typedef x87t_raw80 x80_t;
typedef enum { SF_RN = 0, SF_RD = 1, SF_RU = 2, SF_RZ = 3 } sf_rc_t;
/* value = (-1)^sign * sig * 2^(exp-63); exp is the leading-bit exponent. */
typedef enum { SF_FIN, SF_INF, SF_NAN } sf_cls_t;
typedef struct {
    uint8_t cls, sign;
    int32_t exp;
    uint64_t sig;
} sf_t;
/* Wide value = (-1)^sign * sig * 2^e2. rh is retained materialization metadata. */
typedef struct {
    uint8_t sign;
    int32_t e2;
    u128 sig;
    int8_t rh;
} wv_t;
typedef struct {
    u128 hi, lo;
} u256;
typedef enum {
    P5_ROUND_RN,
    P5_ROUND_CHOP,
    P5_ROUND_AWAY,
    P5_ROUND_ODD,
    P5_ROUND_UP,
    P5_ROUND_DOWN
} p5_round_t;
typedef enum { FSINCOS_OK, FSINCOS_C2 } fsincos_status_t;
typedef struct {
    int c1, c1_known;
} numerical_metadata;
extern const sf_t x87t_internal_ONE, x87t_internal_ZERO, x87t_internal_PI_BY_4;
extern const x80_t x87t_internal_X87_INDEFINITE;
sf_t x87t_internal_sf_zero(int sign);
sf_t x87t_internal_sf_qnan(void);
int x87t_internal_sf_is_zero(const sf_t *a);
sf_t x87t_internal_sf_from_parts(int sign, uint32_t expfield, uint64_t sig);
void x87t_internal_sf_to_x87(const sf_t *a, uint16_t *se, uint64_t *sig);
sf_t x87t_internal_sf_neg(const sf_t *a);
sf_t x87t_internal_sf_abs(const sf_t *a);
int x87t_internal_sf_lt_abs(const sf_t *a, const sf_t *b);
int x87t_internal_sf_lt(const sf_t *a, const sf_t *b);
int x87t_internal_uint128_width(u128 v);
u256 x87t_internal_u128_mul_full(u128 a, u128 b);
sf_t x87t_internal_wv_rn64(wv_t v);
void x87t_internal_acc_add(u256 *acc, int neg, u128 mag_hi, u128 mag_lo);
void x87t_internal_acc_add_product(u256 *acc, int neg, u128 a, u128 b, int32_t e2, int scale);
wv_t x87t_internal_acc_round_wide(u256 acc, int32_t scale, int bits, p5_round_t mode);
wv_t x87t_internal_wide_mul(wv_t a, wv_t b, int bits, p5_round_t mode);
wv_t x87t_internal_constant_round(const p5c_t *constant, int bits, p5_round_t mode);
wv_t x87t_internal_wide_add_constant(wv_t value,
                       const p5c_t *constant,
                       int constant_bits,
                       p5_round_t constant_mode,
                       int bits,
                       p5_round_t mode);
wv_t x87t_internal_wide_add(wv_t left, wv_t right, int bits, p5_round_t mode);
sf_t x87t_internal_acc_round64_rc(u256 acc, int32_t scale, int neg_out, sf_rc_t rc);
sf_t x87t_internal_acc_round64_meta(u256, int32_t scale, int neg_out, sf_rc_t, int *c1);
wv_t x87t_internal_reduced_to_wide(const sf_t *r, const sf_t *c);
uint64_t x87t_internal_reduce_quotient(uint64_t sig, int32_t e);
void x87t_internal_reduce_remainder(const sf_t *x, uint64_t N, sf_t *r, sf_t *c);
wv_t x87t_internal_constant_exact(const p5c_t *c);
wv_t x87t_internal_mul_x67_y64_chop67(wv_t x, wv_t y);
wv_t x87t_internal_wide_add_plain(wv_t x, wv_t y, int bits, p5_round_t mode);
wv_t x87t_internal_standalone_chain(wv_t fourth, const p5c_t *c5, const p5c_t *c3, const p5c_t *c1);
sf_t x87t_internal_standalone_polynomial(
    wv_t magnitude, int residual_sign, int64_t signed_n, sf_rc_t rc, numerical_metadata *meta);
wv_t x87t_internal_mul_x67_y64_rn64(wv_t x, wv_t y);
wv_t x87t_internal_table_horner4(wv_t square, const p5c_t *c4, const p5c_t *c3, const p5c_t *c2, const p5c_t *c1);
sf_t x87t_internal_trig_table(
    wv_t residual, int residual_sign, int64_t signed_n, sf_rc_t rc, numerical_metadata *meta);
int x87t_internal_trig_tiny(x80_t in, int phase, sf_rc_t rc, x80_t *out, numerical_metadata *meta);
sf_t x87t_internal_paired_final(wv_t lead, wv_t tail, int negative, sf_rc_t rc, int *c1);
void x87t_internal_paired_polynomial(
    wv_t magnitude, int residual_sign, int64_t signed_n, sf_rc_t rc, x80_t out[2], int c1[2]);
fsincos_status_t
x87t_internal_paired_evaluate(x80_t in, x80_t *sin_out, x80_t *cos_out, sf_rc_t rc, numerical_metadata *meta);
sf_t x87t_internal_f2xm1_core(sf_t x, sf_rc_t rc, int *c1);
fsincos_status_t x87t_internal_fptan_core(sf_t x, sf_rc_t rc, sf_t *out, int *c1);
fsincos_status_t x87t_internal_standalone_evaluate(x80_t, int, x80_t *, sf_rc_t, numerical_metadata *);
#endif

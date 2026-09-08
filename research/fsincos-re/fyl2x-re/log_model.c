/* Source-guided Skylake FYL2X/FYL2XP1 numerical reconstruction.
 * Exact GMP arithmetic: no native logarithms, host floats or operand ledger.
 * Ken Shirriff's public P5 ROM supplies literal coefficients and split tables;
 * four transcription corrections are independently derived from log2 anchors
 * and corroborated by the public Goldmont ROM's upper-64-bit projections.
 * Rounding and operation order transfer from the public Goldmont listing,
 * tested against frozen Skylake captures. See ALGORITHM.md and ACCEPTANCE.md.
 * The exact arithmetic helpers originate in this repository's FPATAN model.
 */
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <gmp.h>

enum mode { RN = 0, RD = 1, RU = 2, RZ = 3, CHOP = 4 };
typedef struct { uint16_t se; uint64_t sig; } raw80;
typedef struct { mpq_t rom[270]; } log_context;

/* P5 row, sign, binary scale, full 67-bit significand. The original source
 * transcription remains ../data/pentium-rom/rom-constants.tsv.
 * Source: https://www.righto.com/2025/01/pentium-floating-point-ROM.html
 */
static const struct { int index, sign, scale; const char *sig; } constants[] = {
    {193, 0, -66, "48000000000000000"},
    {194, 0, -67, "70000000000000000"},
    {195, 0, -66, "5c551d94ae0bf85de"},
    {196, 0, -65, "5c551d94ae0bf85de"},
    {197, 0, -70, "7b1c2770e81287c11"},
    {198, 0, -72, "49ddb14064a5d30bd"},
    {199, 0, -75, "698879b87934f12e0"},
    {200, 0, -71, "51ff4ffeb20ed1749"},
    {201, 0, -75, "5e8cd07eb1827434a"},
    {202, 0, -78, "40e54061b26dd6dc2"},
    {203, 0, -82, "61008a69627c92fb9"},
    {204, 0, -85, "4c41e6ced287a2468"},
    {205, 0, -89, "7dadd4ea3c3fee620"},
    {206, 0, -72, "5b9e5a170b8000000"},
    /* Corrected transcription; independent mathematical/ROM provenance. */
    {207, 0, -70, "43ace27e8a8000000"},
    {208, 0, -70, "6f210902b68000000"},
    {209, 0, -69, "4caba789e28000000"},
    {210, 0, -69, "6130af40bc0000000"},
    {211, 0, -69, "7527b930c98000000"},
    {212, 0, -68, "444c1f6b4c0000000"},
    {213, 0, -68, "4dc4933a930000000"},
    {214, 0, -68, "570068e7ef8000000"},
    {215, 0, -68, "6002958c588000000"},
    {216, 0, -68, "68cdd829fd8000000"},
    {217, 0, -68, "7164beb4a58000000"},
    {218, 0, -68, "79c9aa879d8000000"},
    {219, 0, -67, "40ff6a2e5e8000000"},
    {220, 0, -67, "450327ea878000000"},
    {221, 0, -67, "48f107509c8000000"},
    {222, 0, -67, "4cc9f1aad28000000"},
    {223, 0, -67, "508ec1fa618000000"},
    {224, 0, -67, "5440461c228000000"},
    {225, 0, -67, "57df3fd0780000000"},
    {226, 0, -67, "5b6c65a9d88000000"},
    {227, 0, -67, "5ee863e4d40000000"},
    {228, 0, -67, "6253dd2c1b8000000"},
    {229, 0, -67, "65af6b4ab30000000"},
    {230, 0, -67, "68fb9fce388000000"},
    {231, 0, -67, "6c39049af30000000"},
    {232, 0, -67, "6f681c731a0000000"},
    {233, 0, -67, "72896372a50000000"},
    {234, 0, -67, "759d4f80cb8000000"},
    {235, 0, -67, "78a450b8380000000"},
    {236, 0, -67, "7b9ed1c6ce8000000"},
    {237, 0, -67, "7e8d3845df0000000"},
    {238, 1, -113, "6eb3ac8ec0ef73f7b"},
    {239, 1, -116, "654c308b454666de9"},
    {240, 0, -111, "5dd31d962d3728cbd"},
    {241, 0, -110, "70d0fa8f9603ad3a6"},
    {242, 0, -112, "765fba4491dcec753"},
    {243, 1, -111, "690370b4a9afdc5fb"},
    {244, 0, -109, "5bae584b82d3cad27"},
    /* Corrected transcription; independent mathematical/ROM provenance. */
    {245, 0, -109, "6f66cc899b64b03f7"},
    {246, 1, -109, "4bc302ffa76fafcba"},
    {247, 1, -111, "7579aa293ec16410a"},
    {248, 0, -114, "509d7c40d7979ec5b"},
    {249, 1, -110, "4a981811ab5110ccf"},
    {250, 1, -109, "596f9d730f685c776"},
    {251, 1, -109, "680cc6bcb9bfa9853"},
    {252, 0, -109, "5439e15a52a31604a"},
    {253, 0, -109, "7c8080ecc61a98814"},
    {254, 1, -110, "6b26f28dbf40b7bc0"},
    {255, 0, -108, "554b383b0e8a55627"},
    {256, 0, -108, "47c6ef4a49bc59135"},
    {257, 0, -108, "4d75c658d602e66b0"},
    {258, 1, -109, "6b626820f81ca95da"},
    /* Corrected transcription; independent mathematical/ROM provenance. */
    {259, 0, -110, "5c813d56efe4338fe"},
    {260, 0, -108, "7c5a0375163ec8d56"},
    {261, 1, -108, "5050809db75675c90"},
    {262, 1, -109, "7e12f8672e55de96c"},
    {263, 0, -108, "435ebd376a70d849b"},
    {264, 1, -111, "6492ba487dfb264b3"},
    {265, 1, -108, "674e5008e379faa7c"},
    {266, 0, -108, "5077f1f5f0cc82aab"},
    {267, 0, -111, "5007eeaa99f8ef14d"},
    /* Corrected transcription; independent mathematical/ROM provenance. */
    {268, 0, -108, "4a83eb6e0f93f7a44"},
    {269, 0, -110, "466c525173dae9cf5"},
};

/* Exact dyadic arithmetic and rounding primitives. */

/* All scaling here is exact; exponent fields are never host FP exponents. */
static void scale2(mpq_t out, const mpq_t in, int scale)
{
    if (scale >= 0)
        mpq_mul_2exp(out, in, (unsigned)scale);
    else
        mpq_div_2exp(out, in, (unsigned)-scale);
}

static int qexp(const mpq_t in)
{
    mpz_t n, d;
    mpz_inits(n, d, NULL);
    mpz_abs(n, mpq_numref(in));
    mpz_set(d, mpq_denref(in));
    int e = (int)mpz_sizeinbase(n, 2) - (int)mpz_sizeinbase(d, 2);
    if (e >= 0)
        mpz_mul_2exp(d, d, (unsigned)e);
    else
        mpz_mul_2exp(n, n, (unsigned)-e);
    if (mpz_cmp(n, d) < 0)
        e--;
    mpz_clears(n, d, NULL);
    return e;
}

static int increment(const mpz_t q, const mpz_t r, const mpz_t d, int negative, enum mode mode)
{
    if (!mpz_sgn(r))
        return 0;
    if (mode == RD)
        return negative;
    if (mode == RU)
        return !negative;
    if (mode != RN)
        return 0;
    mpz_t twice;
    mpz_init(twice);
    mpz_mul_2exp(twice, r, 1);
    int cmp = mpz_cmp(twice, d);
    mpz_clear(twice);
    return cmp > 0 || (cmp == 0 && mpz_odd_p(q));
}

static void at_step(mpq_t out, const mpq_t in, int scale, enum mode mode)
{
    int negative = mpq_sgn(in) < 0;
    mpz_t n, d, q, r;
    mpz_inits(n, d, q, r, NULL);
    mpz_abs(n, mpq_numref(in));
    mpz_set(d, mpq_denref(in));
    if (scale < 0)
        mpz_mul_2exp(n, n, (unsigned)-scale);
    else
        mpz_mul_2exp(d, d, (unsigned)scale);
    mpz_fdiv_qr(q, r, n, d);
    if (increment(q, r, d, negative, mode))
        mpz_add_ui(q, q, 1);
    if (negative)
        mpz_neg(q, q);
    mpq_set_z(out, q);
    scale2(out, out, scale);
    mpz_clears(n, d, q, r, NULL);
}

static void rounded(mpq_t out, const mpq_t in, int bits, enum mode mode)
{
    if (!mpq_sgn(in)) {
        mpq_set_ui(out, 0, 1);
        return;
    }
    at_step(out, in, qexp(in) - bits + 1, mode);
}

static void decode(mpq_t out, raw80 in)
{
    mpz_import(mpq_numref(out), 1, 1, sizeof(in.sig), 0, 0, &in.sig);
    mpz_set_ui(mpq_denref(out), 1);
    scale2(out, out, ((in.se & 0x7fff) ? (in.se & 0x7fff) : 1) - 16383 - 63);
    if (in.se & 0x8000)
        mpq_neg(out, out);
}

static raw80 encode(const mpq_t in, enum mode mode, int *c1)
{
    raw80 out = {0, 0};
    int sign = mpq_sgn(in) < 0;
    mpq_t q, a, b;
    mpq_inits(q, a, b, NULL);
    int e = mpq_sgn(in) ? qexp(in) : -16382;
    if (e < -16382)
        e = -16382;
    at_step(q, in, e - 63, mode);
    mpq_abs(a, q);
    mpq_abs(b, in);
    *c1 = mpq_cmp(a, b) > 0;
    if (mpq_sgn(q) && qexp(q) > 16383) {
        int inf = mode == RN || (mode == RD && sign) || (mode == RU && !sign);
        out.se = (uint16_t)((sign << 15) | (inf ? 0x7fff : 0x7ffe));
        out.sig = inf ? (UINT64_C(1) << 63) : UINT64_MAX;
        *c1 = inf;
        mpq_clears(q, a, b, NULL);
        return out;
    }
    if (mpq_sgn(q)) {
        e = qexp(q);
        if (e < -16382)
            e = -16382;
        scale2(a, a, 63 - e);
        if (mpz_cmp_ui(mpq_denref(a), 1))
            abort();
        if (mpz_sizeinbase(mpq_numref(a), 2) > 64)
            abort();
        size_t count = 0;
        mpz_export(&out.sig, &count, 1, sizeof(out.sig), 0, 0, mpq_numref(a));
        if (count > 1)
            abort();
    }
    out.se = (uint16_t)((sign << 15) | (out.sig < (UINT64_C(1) << 63) ? 0 : e + 16383));
    mpq_clears(q, a, b, NULL);
    return out;
}

static void context_init(log_context *ctx)
{
    for (int i = 0; i < 270; i++)
        mpq_init(ctx->rom[i]);
    for (size_t i = 0; i < sizeof(constants) / sizeof(constants[0]); i++) {
        int k = constants[i].index;
        if (mpz_set_str(mpq_numref(ctx->rom[k]), constants[i].sig, 16))
            abort();
        if (constants[i].sign)
            mpq_neg(ctx->rom[k], ctx->rom[k]);
        scale2(ctx->rom[k], ctx->rom[k], constants[i].scale);
    }
}

static void context_clear(log_context *ctx)
{
    for (int i = 0; i < 270; i++)
        mpq_clear(ctx->rom[i]);
}

enum operand_class { ZERO, NORMAL, DENORMAL, PSEUDO, INFINITY_VALUE, QNAN, SNAN, UNSUPPORTED };

/* Raw80 classification and masked architectural result/exception handling. */
static enum operand_class classify(raw80 v)
{
    unsigned e = v.se & 0x7fff;
    if (!e) {
        if (!v.sig)
            return ZERO;
        return v.sig >> 63 ? PSEUDO : DENORMAL;
    }
    if (!(v.sig >> 63))
        return UNSUPPORTED;
    if (e != 0x7fff)
        return NORMAL;
    if (v.sig == (UINT64_C(1) << 63))
        return INFINITY_VALUE;
    return v.sig & (UINT64_C(1) << 62) ? QNAN : SNAN;
}

/* The raw operation classes are distinct in the public operation listing.
 * M: 0x6e1 product, A: 0x649 add, W: 0x6c9 wide add.
 */
static void mul67(mpq_t out, const mpq_t a, const mpq_t b)
{
    mpq_mul(out,a,b); rounded(out,out,67,CHOP);
}
static void add64(mpq_t out, const mpq_t a, const mpq_t b)
{
    mpq_add(out,a,b); rounded(out,out,64,RN);
}
static void add67(mpq_t out, const mpq_t a, const mpq_t b)
{
    mpq_add(out,a,b); rounded(out,out,67,CHOP);
}

/* x is an exact finite raw80 value; op=0 is FYL2X, op=1 is FYL2XP1.
 * The caller handles exceptional classes and zero-logarithm cases.
 */
static void logarithm(const log_context *ctx, int op, const mpq_t input, mpq_t result)
{
    mpq_t x,z,u,v,odd,even,t,den,anchor;
    mpq_inits(x,z,u,v,odd,even,t,den,anchor,NULL);
    mpq_set(x,input);
    mpq_set_ui(t,1,8); mpq_abs(z,x);
    if (op && mpq_cmp(z,t)>0) {
        mpq_set_ui(t,1,1); add67(x,x,t); op=0;
    }
    if (op || (mpq_cmp(x,ctx->rom[194])>=0 && mpq_cmp(x,ctx->rom[193])<=0)) {
        if (op && qexp(x)<=-70) {
            mul67(result,ctx->rom[195],x);
            goto done;
        }
        mpq_set_ui(t,1,1);
        if (op) mpq_set(z,x);
        else { mpq_neg(t,t); add64(z,x,t); mpq_neg(t,t); }
        if (op) mpq_set_ui(t,2,1);
        add67(den,x,t);
        mul67(z,z,ctx->rom[196]); mpq_div(z,z,den); rounded(z,z,67,CHOP);
        /* Distinct 0x661 square: one input port is truncated to 64 bits. */
        rounded(u,z,64,CHOP); mpq_mul(u,u,z); rounded(u,u,64,RN);
        mul67(v,u,u);
        mul67(odd,ctx->rom[205],v); add64(odd,odd,ctx->rom[203]);
        mul67(odd,odd,v); add64(odd,odd,ctx->rom[201]);
        mul67(even,ctx->rom[204],v); add64(even,even,ctx->rom[202]);
        mul67(even,even,v); add64(even,even,ctx->rom[200]);
        mul67(odd,odd,v); mul67(even,even,u); add64(t,odd,even);
        mul67(t,t,z); add67(result,t,z);
    } else {
        int e=qexp(x); scale2(x,x,-e);
        mpq_set_ui(t,1,1); mpq_sub(t,x,t); scale2(t,t,5);
        mpz_fdiv_q(mpq_numref(t),mpq_numref(t),mpq_denref(t));
        int i=(int)mpz_get_ui(mpq_numref(t));
        if (i<0 || i>31) abort();
        mpq_set_ui(anchor,(unsigned)(65+2*i),64);
        mpq_neg(t,anchor); add64(z,x,t); add64(z,z,z);
        add64(den,x,anchor); mpq_div(z,z,den); rounded(z,z,64,RN);
        mul67(even,ctx->rom[195],z); mul67(u,z,z);
        mul67(t,ctx->rom[199],u); add64(t,t,ctx->rom[198]);
        mul67(t,t,u); add64(t,t,ctx->rom[197]);
        mul67(t,t,u); mul67(t,t,z); add64(t,t,even);
        add67(t,t,ctx->rom[238+i]);
        mpq_set_si(anchor,e,1); add64(anchor,anchor,ctx->rom[206+i]);
        add67(result,t,anchor);
    }
done:
    mpq_clears(x,z,u,v,odd,even,t,den,anchor,NULL);
}

/* Masked numerical contract: two valid stack entries, all exception latches
 * clear before FLD80 of y and x. PC is metadata; the kernel retains its own
 * fixed precisions. Undefined condition bits and arbitrary restore histories
 * are not modeled. FYL2XP1's guaranteed finite domain is Intel's stated range.
 */
static int log_raw80(const log_context *ctx, int op, raw80 y, raw80 x,
                     enum mode rc, raw80 *out, int *c1, unsigned *exceptions)
{
    enum operand_class ky=classify(y),kx=classify(x);
    raw80 invalid={0xffff,UINT64_C(0xc000000000000000)};
    *c1=0; *exceptions=0;
    if (ky==UNSUPPORTED || kx==UNSUPPORTED) goto invalid;
    int ny=ky==QNAN || ky==SNAN,nx=kx==QNAN || kx==SNAN;
    if (ny || nx) {
        raw80 pick;
        if (!ny) pick=x;
        else if (!nx) pick=y;
        else if (ky==QNAN && kx==SNAN) pick=y;
        else if (kx==QNAN && ky==SNAN) pick=x;
        else pick=y.sig>x.sig || (y.sig==x.sig && y.se<x.se) ? y:x;
        pick.sig|=UINT64_C(1)<<62; *out=pick;
        *exceptions=ky==SNAN || kx==SNAN; return 0;
    }
    /* Intel's guaranteed FYL2XP1 finite range is |x| <= 1-sqrt(1/2).
     * Its largest raw80 member is 0x3ffd:95f619980c4336f7. The bound is
     * checked by an exact integer inequality in the validation tooling.
     * Out-of-range finite/inf behavior is architecturally undefined.
     */
    if (op && ((x.se&0x7fff)>0x3ffd ||
        ((x.se&0x7fff)==0x3ffd && x.sig>UINT64_C(0x95f619980c4336f7)))) return 1;
    if (ky==DENORMAL || ky==PSEUDO || kx==DENORMAL || kx==PSEUDO) *exceptions=2;
    int sy=y.se>>15,sx=x.se>>15,logsign,logzero;
    if (!op) {
        if (sx && kx!=ZERO) goto invalid;
        if (kx==ZERO) {
            if (ky==ZERO) goto invalid;
            *out=(raw80){(uint16_t)(((sy^1)<<15)|0x7fff),UINT64_C(1)<<63};
            *exceptions=4; return 0;
        }
        if (kx==INFINITY_VALUE) {
            if (ky==ZERO) goto invalid;
            *out=(raw80){(uint16_t)((sy<<15)|0x7fff),UINT64_C(1)<<63}; return 0;
        }
        logzero=x.se==0x3fff && x.sig==(UINT64_C(1)<<63);
        logsign=x.se<0x3fff;
    } else {
        if (kx==INFINITY_VALUE) return 1;
        logzero=kx==ZERO; logsign=sx;
    }
    int sign=sy^logsign;
    if (logzero) {
        if (ky==INFINITY_VALUE) goto invalid;
        *out=(raw80){(uint16_t)(sign<<15),0}; return 0;
    }
    if (ky==INFINITY_VALUE) {
        *out=(raw80){(uint16_t)((sign<<15)|0x7fff),UINT64_C(1)<<63}; return 0;
    }
    if (ky==ZERO) { *out=(raw80){(uint16_t)(sign<<15),0}; return 0; }
    mpq_t qx,qy,v;
    mpq_inits(qx,qy,v,NULL); decode(qx,x); decode(qy,y);
    if (op && mpq_cmp_si(qx,-1,1)<=0) {
        mpq_clears(qx,qy,v,NULL); return 1;
    }
    logarithm(ctx,op,qx,v); mpq_mul(v,v,qy);
    *out=encode(v,rc,c1); *exceptions|=32;
    /* The final architectural multiply tests the 64-bit rounded value with
     * unbounded exponent, before the final raw80 denormalization. A stored
     * minimum normal can therefore still signal underflow (Intel SDM 8.5.5).
     * The logarithm kernel marks the result inexact even when this final
     * product is exact, so every tiny unbounded rounded result signals UE.
     */
    rounded(qx,v,64,rc);
    if (qexp(qx)<-16382) *exceptions|=16;
    if (qexp(v)>16383 || (out->se&0x7fff)==0x7fff) *exceptions|=8;
    mpq_clears(qx,qy,v,NULL); return 0;
invalid:
    *out=invalid; *exceptions=1; return 0;
}

#ifndef LOG_NO_MAIN
int main(void)
{
    log_context ctx; context_init(&ctx);
    char line[256],id[64],op[16],rc[4],extra;
    unsigned pc,ys,xs; uint64_t ym,xm;
    while (fgets(line,sizeof(line),stdin)) {
        if (sscanf(line,"%63s %15s %3s %u %x %" SCNx64 " %x %" SCNx64 " %c",
                   id,op,rc,&pc,&ys,&ym,&xs,&xm,&extra)!=8 || ys>65535 || xs>65535 ||
            (pc!=24 && pc!=53 && pc!=64)) return 2;
        int which=!strcmp(op,"fyl2xp1");
        if (!which && strcmp(op,"fyl2x")) return 2;
        enum mode mode;
        if (!strcmp(rc,"rn")) mode=RN; else if (!strcmp(rc,"rd")) mode=RD;
        else if (!strcmp(rc,"ru")) mode=RU; else if (!strcmp(rc,"rz")) mode=RZ;
        else return 2;
        raw80 out; int c1; unsigned exceptions;
        if (log_raw80(&ctx,which,(raw80){(uint16_t)ys,ym},(raw80){(uint16_t)xs,xm},mode,&out,&c1,&exceptions)) return 3;
        printf("%s %04x %016" PRIx64 " %d %02x 00\n",id,out.se,out.sig,c1,exceptions);
    }
    int status=ferror(stdin) || fflush(stdout);
    context_clear(&ctx); return status;
}
#endif

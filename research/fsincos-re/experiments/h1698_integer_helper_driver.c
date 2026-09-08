/* H1698 software-only carrier tests against the actual pinned C helpers.
 * No x87 capture, candidate adjustment or emulator-default promotion. */
#define main h1698_unused_emulator_main
#include "../src/fsincos_skylake.c"
#undef main

static u128 h1698_pair(unsigned long long hi, unsigned long long lo)
{
    return ((u128)hi << 64) | lo;
}

static void h1698_print256(u256 value)
{
    printf("%016llx%016llx%016llx%016llx\n",
        (unsigned long long)(value.hi >> 64), (unsigned long long)value.hi,
        (unsigned long long)(value.lo >> 64), (unsigned long long)value.lo);
}

int main(void)
{
    char op;
    int neg, bits, mode, shift;
    unsigned long long w[8];
    while (scanf(" %c %d %d %d %d %llx %llx %llx %llx %llx %llx %llx %llx",
        &op, &neg, &bits, &mode, &shift,
        &w[0], &w[1], &w[2], &w[3], &w[4], &w[5], &w[6], &w[7]) == 13) {
        u256 a = { h1698_pair(w[0], w[1]), h1698_pair(w[2], w[3]) };
        u256 b = { h1698_pair(w[4], w[5]), h1698_pair(w[6], w[7]) };
        if (op == 'M') h1698_print256(u128_mul_full(a.lo, b.lo));
        else if (op == 'A') {
            acc_add(&a, neg, b.hi, b.lo);
            h1698_print256(a);
        } else if (op == 'S') {
            /* Shift range is restricted by the Python bank to -255..255.
             * Right shifts mean floor division, not assumed exact alignment. */
            acc_add_product(&a, neg, b.hi, b.lo, shift, 0);
            h1698_print256(a);
        } else if (op == 'R') {
            wv_t result = acc_round_bits_mode(a, shift, bits, (p5_round_t)mode);
            printf("%u %d %016llx%016llx %d\n", result.sign, result.e2,
                (unsigned long long)(result.sig >> 64),
                (unsigned long long)result.sig, result.rh);
        } else if (op == 'F') {
            sf_t result = acc_round64_rc(a, shift, neg, (sf_rc_t)mode);
            printf("%u %d %016llx\n", result.sign, result.exp,
                (unsigned long long)result.sig);
        } else return 2;
    }
    return feof(stdin) ? 0 : 3;
}

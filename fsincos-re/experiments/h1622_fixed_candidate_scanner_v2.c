/* H1622 software-only challenge scanner, appended to an in-memory model
 * translation unit. Candidate arithmetic and canonical source are unchanged.
 * All selection uses model states, never a newly observed hardware label.
 */
int main(void)
{
    const sf_rc_t modes[4] = {SF_RN, SF_RD, SF_RU, SF_RZ};
    unsigned boundary_counts[2][8][6] = {{{0}}};
    unsigned long long checked = 0, separators = 0, controls = 0;
    unsigned se, origin;
    unsigned long long sig, ordinal;
    g_fcos_standalone_path = 1;
    puts("operand\torigin\tordinal\tkind\tchanged_mask\tsquare_low3\tfourth_cut\tfinal_shift\tfinal_remainder\tpre_scale\tpre_significand\tcandidate_rn\tcandidate_rd\tcandidate_ru\tcandidate_rz\tbaseline_rn\tbaseline_rd\tbaseline_ru\tbaseline_rz\tC1_bits");
    while (scanf("%x %llx %u %llu", &se, &sig, &origin, &ordinal) == 4) {
        if (se != 0x3ffc || !(sig >> 63) || origin > 4) return 2;
        x80_t input = {(uint16_t)se, (uint64_t)sig};
        x80_t baseline[4], proposed[4];
        h1622_enabled = 0;
        for (unsigned i = 0; i < 4; ++i)
            if (fcos_ref(input, &baseline[i], modes[i]) != FSINCOS_OK) return 3;
        h1622_enabled = 1;
        h1622_final_calls = 0;
        if (fcos_ref(input, &proposed[0], SF_RN) != FSINCOS_OK || h1622_final_calls != 1) return 4;
        if (h1622_pre.hi || h1622_neg) return 5;
        for (unsigned i = 1; i < 4; ++i) {
            sf_t result = acc_round64_rc(h1622_pre, h1622_scale, 0, modes[i]);
            sf_to_x87(&result, &proposed[i].se, &proposed[i].sig);
        }
        unsigned changed = 0;
        for (unsigned i = 0; i < 4; ++i) {
            if (baseline[i].se != proposed[i].se || baseline[i].sig != proposed[i].sig) changed |= 1u << i;
            if (proposed[i].se != 0x3ffe) return 6;
        }
        int shift = u128_width(h1622_pre.lo) - 64;
        if (shift < 1 || shift > 16) return 7;
        unsigned denominator = 1u << shift, half = denominator >> 1;
        unsigned remainder = (unsigned)(h1622_pre.lo & (denominator - 1));
        u128 full_square = (u128)sig * sig;
        u128 square = full_square >> (u128_width(full_square) - 67);
        u256 full_fourth = u128_mul_full(square, square);
        /* The normalization cut uses bit length, not width after removing trailing zeroes. */
        int fourth_cut = (full_fourth.hi ? 128 + u128_width(full_fourth.hi) : u128_width(full_fourth.lo)) - 67;
        if (fourth_cut < 66 || fourth_cut > 67) return 8;
        unsigned low3 = (unsigned)square & 7;
        int edge = remainder == 0 ? 0 : remainder == 1 ? 1 : remainder == half - 1 ? 2
                 : remainder == half ? 3 : remainder == half + 1 ? 4 : remainder == denominator - 1 ? 5 : -1;
        const char *kind = NULL;
        if (changed) { kind = "separator"; ++separators; }
        else if (origin == 2 && edge >= 0 && boundary_counts[fourth_cut - 66][low3][edge] < 4) {
            ++boundary_counts[fourth_cut - 66][low3][edge]; kind = "rounding_boundary_control"; ++controls;
        } else if (origin == 2 && ordinal % 4096 == 0) {
            kind = "uniform_control"; ++controls;
        } else if (origin == 1 && ordinal < 16) {
            kind = "domain_edge_control"; ++controls;
        }
        ++checked;
        if (kind) {
            printf("%04x %016llx\t%u\t%llu\t%s\t%u\t%u\t%d\t%d\t%u\t%d\t%016llx%016llx",
                   se, sig, origin, ordinal, kind, changed, low3, fourth_cut, shift, remainder, h1622_scale,
                   (unsigned long long)(h1622_pre.lo >> 64), (unsigned long long)h1622_pre.lo);
            for (unsigned i = 0; i < 4; ++i)
                printf("\t%04x:%016llx", proposed[i].se, (unsigned long long)proposed[i].sig);
            for (unsigned i = 0; i < 4; ++i)
                printf("\t%04x:%016llx", baseline[i].se, (unsigned long long)baseline[i].sig);
            putchar('\t');
            uint64_t floor_significand = (uint64_t)(h1622_pre.lo >> shift);
            for (unsigned i = 0; i < 4; ++i) putchar('0' + (proposed[i].sig > floor_significand));
            putchar('\n');
        }
        if (checked % 100000 == 0)
            fprintf(stderr, "checked=%llu separators=%llu controls=%llu\n", checked, separators, controls);
    }
    if (!feof(stdin) || ferror(stdin)) return 9;
    fprintf(stderr, "COMPLETE checked=%llu separators=%llu controls=%llu\n", checked, separators, controls);
    return 0;
}

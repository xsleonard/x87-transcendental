/* Restricted H1707 packaging of the unchanged H1638 standalone candidate.
 * The old laboratory CLI is callable only after this whitelist. No fitted
 * switches, paired FSINCOS, or sibling instruction can be selected here.
 * This is a numerical candidate interface, not a complete state emulator.
 */
#undef main

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--selftest")) {
        /* H1713 keeps the restricted selftest quiet after paired promotion. */
        g_general_trace = 0;
        return x87_candidate_laboratory_main(argc, argv);
    }
    if (argc == 2 && !strcmp(argv[1], "--help")) {
        puts("Usage: fsin_fcos_candidate --batch --fsin-standalone|--fcos-standalone [--rc=rn|rd|ru|rz]");
        puts("Input: hexadecimal sign/exponent and 64-bit significand, one pair per line.");
        puts("Output: existing OK/C2 numerical format; arithmetic/C1 trace on stderr.");
        puts("FSINCOS is not implemented by this candidate target.");
        return 0;
    }
    int instruction_count = 0, rounding_count = 0;
    if (argc < 3 || strcmp(argv[1], "--batch")) goto invalid;
    for (int i = 2; i < argc; ++i) {
        if (!strcmp(argv[i], "--fsin-standalone") || !strcmp(argv[i], "--fcos-standalone"))
            ++instruction_count;
        else if (!strcmp(argv[i], "--rc=rn") || !strcmp(argv[i], "--rc=rd")
            || !strcmp(argv[i], "--rc=ru") || !strcmp(argv[i], "--rc=rz"))
            ++rounding_count;
        else goto invalid;
    }
    if (instruction_count != 1 || rounding_count > 1) goto invalid;
    return x87_candidate_laboratory_main(argc, argv);
invalid:
    fputs("Unsupported candidate arguments; use --help. FSINCOS and experimental switches are unavailable.\n", stderr);
    return 2;
}

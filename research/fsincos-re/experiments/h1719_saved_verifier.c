/* H1719: saved-label verifier, never a hardware capture driver.
 * Embed the unchanged promoted translation unit so C1 is checked without
 * generating hundreds of millions of trace lines. The ordinary CLI is
 * cross-checked independently before launching the bank replay.
 */
#define main h1719_original_main
#include "../src/fsincos_skylake.c"
#undef main
#include <errno.h>
#include <inttypes.h>

static int fail(const char *reason, uint64_t row)
{
    fprintf(stderr, "ERROR row=%" PRIu64 " %s\n", row, reason);
    return 2;
}

static int words(char *line, char **out, int capacity)
{
    int n = 0;
    for (char *p = strtok(line, " \t\r\n"); p; p = strtok(NULL, " \t\r\n")) {
        if (n == capacity) return -1;
        out[n++] = p;
    }
    return n;
}

static int hexword(const char *s, size_t width, uint64_t *value)
{
    if (strlen(s) != width) return 0;
    for (size_t i = 0; i < width; ++i)
        if (!((s[i] >= '0' && s[i] <= '9') ||
              (s[i] >= 'a' && s[i] <= 'f') ||
              (s[i] >= 'A' && s[i] <= 'F'))) return 0;
    errno = 0;
    *value = strtoull(s, NULL, 16);
    return errno == 0;
}

static int encoding(char **v, x80_t *out)
{
    uint64_t se, sig;
    if (!hexword(v[0], 4, &se) || !hexword(v[1], 16, &sig)) return 0;
    out->se = (uint16_t)se; out->sig = sig;
    return 1;
}

static int same(x80_t a, x80_t b)
{
    return a.se == b.se && a.sig == b.sig;
}

int main(int argc, char **argv)
{
    int predict = argc == 5 && !strcmp(argv[1], "--predict");
    int offset = predict ? 1 : 0;
    if ((!predict && argc != 5) || (predict && argc != 5))
        return fail("usage: [--predict] fsin|fcos|fsincos rn|rd|ru|rz inputs [labels]", 0);
    const char *insn = argv[1 + offset], *mode = argv[2 + offset];
    int paired = !strcmp(insn, "fsincos");
    int cosine = !strcmp(insn, "fcos");
    if (!paired && !cosine && strcmp(insn, "fsin")) return fail("unknown instruction", 0);
    sf_rc_t rc;
    if (!strcmp(mode, "rn")) rc = SF_RN;
    else if (!strcmp(mode, "rd")) rc = SF_RD;
    else if (!strcmp(mode, "ru")) rc = SF_RU;
    else if (!strcmp(mode, "rz")) rc = SF_RZ;
    else return fail("unknown rounding mode", 0);
    FILE *inputs = fopen(argv[3 + offset], "r");
    FILE *labels = predict ? NULL : fopen(argv[4], "r");
    if (!inputs || (!predict && !labels)) return fail("cannot open inputs/labels", 0);
    g_fsin_standalone_path = !paired && !cosine;
    g_fcos_standalone_path = cosine;
    uint64_t rows = 0, lanes = 0, c1_checks = 0, c2_checks = 0;
    uint64_t output_misses = 0, c1_misses = 0, c2_misses = 0;
    uint64_t sw_rows = 0, c2_rows = 0, reported = 0;
    char input[512], label[512];
    while (fgets(input, sizeof input, inputs)) {
        if (!strchr(input, '\n') && !feof(inputs)) return fail("overlong input", rows);
        char *iv[4]; int ni = words(input, iv, 4); x80_t in, out[2];
        if (ni != 2 || !encoding(iv, &in)) return fail("malformed input", rows);
        ++h1630_row;
        fsincos_status_t st = paired ? fsincos_ref(in, &out[0], &out[1], rc)
            : cosine ? fcos_ref(in, &out[0], rc) : fsin_ref(in, &out[0], rc);
        int c2 = st == FSINCOS_C2;
        sf_t decoded = sf_from_parts(in.se >> 15, in.se & 0x7fff, in.sig);
        int known = !c2 && g_general_c1_known && !x87_invalid_encoding(in)
            && decoded.cls == SF_FIN && decoded.sig != 0;
        ++rows;
        if (predict) {
            if (c2) printf("C2");
            else {
                printf("OK %04x %016" PRIx64, out[0].se, out[0].sig);
                if (paired) printf(" %04x %016" PRIx64, out[1].se, out[1].sig);
            }
            printf(" META %d %d\n", known, g_general_c1);
            continue;
        }
        if (!fgets(label, sizeof label, labels)) return fail("labels shorter than inputs", rows);
        if (!strchr(label, '\n') && !feof(labels)) return fail("overlong label", rows);
        char *lv[10]; int nl = words(label, lv, 10);
        if (nl < 1) return fail("malformed label", rows);
        int expected_c2 = !strcmp(lv[0], "C2");
        int fields = expected_c2 ? 1 : paired ? 5 : 3;
        if ((nl != fields && nl != fields + 2) ||
            (!expected_c2 && strcmp(lv[0], "OK"))) return fail("unexpected label shape", rows);
        uint64_t sw = 0; int has_sw = nl == fields + 2;
        if (has_sw && (strcmp(lv[fields], "SW") || !hexword(lv[fields + 1], 4, &sw)))
            return fail("malformed status word", rows);
        x80_t expected[2];
        if (!expected_c2 && (!encoding(lv + 1, &expected[0]) ||
            (paired && !encoding(lv + 3, &expected[1])))) return fail("malformed output encoding", rows);
        int bad_output = c2 != expected_c2;
        if (!c2 && !expected_c2) {
            lanes += paired ? 2 : 1;
            bad_output |= !same(out[0], expected[0]) || (paired && !same(out[1], expected[1]));
        }
        int bad_c1 = 0, bad_c2 = 0;
        if (has_sw) {
            ++sw_rows; ++c2_checks;
            bad_c2 = c2 != !!(sw & 0x400);
            if (expected_c2 != !!(sw & 0x400)) return fail("label C2 disagrees with its SW", rows);
            if (known) { ++c1_checks; bad_c1 = g_general_c1 != !!(sw & 0x200); }
        }
        c2_rows += expected_c2;
        output_misses += bad_output; c1_misses += bad_c1; c2_misses += bad_c2;
        if ((bad_output || bad_c1 || bad_c2) && reported++ < 1000)
            fprintf(stderr, "MISS row=%" PRIu64 " %04x %016" PRIx64
                " output=%d C1=%d C2=%d\n", rows, in.se, in.sig, bad_output, bad_c1, bad_c2);
        if (!(rows % 1000000)) {
            fprintf(stderr, "PROGRESS rows=%" PRIu64 " misses=%" PRIu64 "\n",
                rows, output_misses + c1_misses + c2_misses);
            fflush(stderr);
        }
    }
    if (ferror(inputs)) return fail("input read error", rows);
    if (labels && (fgetc(labels) != EOF || ferror(labels))) return fail("extra labels or label read error", rows);
    fclose(inputs); if (labels) fclose(labels);
    if (predict) return 0;
    printf("{\"rows\":%" PRIu64 ",\"lanes\":%" PRIu64 ",\"C1_checks\":%" PRIu64
        ",\"C2_checks\":%" PRIu64 ",\"C2_rows\":%" PRIu64 ",\"SW_rows\":%" PRIu64
        ",\"output_misses\":%" PRIu64 ",\"C1_misses\":%" PRIu64 ",\"C2_misses\":%" PRIu64
        ",\"reported_misses\":%" PRIu64 ",\"hardware_executions\":0}\n",
        rows, lanes, c1_checks, c2_checks, c2_rows, sw_rows,
        output_misses, c1_misses, c2_misses, reported < 1000 ? reported : UINT64_C(1000));
    return !!(output_misses || c1_misses || c2_misses);
}

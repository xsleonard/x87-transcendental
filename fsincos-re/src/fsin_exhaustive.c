/*
 * Deterministic binary64-space comparison of hardware FSIN with the
 * reconstructed standalone-FSIN model.
 *
 * Each counter is mapped through a bijective 64-bit permutation.  A complete
 * 2^64 counter traversal therefore visits every IEEE-754 binary64 encoding
 * exactly once.  Smaller prefixes are deterministic samples spread throughout
 * that space.  Inputs are converted exactly to x87 extended format before both
 * implementations are called.
 *
 * Build only on the target x86 Linux host:
 *   make fsin_exhaustive
 */

#if !defined(__i386__) && !defined(__x86_64__)
#error "the exhaustive FSIN comparator requires native x87 hardware"
#endif

#define main fsincos_skylake_embedded_main
#include "fsincos_skylake.c"
#undef main

#include <errno.h>
#include <inttypes.h>
#include <pthread.h>
#include <time.h>

enum {
    FSIN_EXHAUSTIVE_RN = 0,
    FSIN_EXHAUSTIVE_RD = 1,
    FSIN_EXHAUSTIVE_RU = 2,
    FSIN_EXHAUSTIVE_MODE_COUNT = 3
};

static const char *const FSIN_EXHAUSTIVE_MODE_NAMES[] = {
    "rn", "rd", "ru"
};

static const sf_rc_t FSIN_EXHAUSTIVE_MODEL_MODES[] = {
    SF_RN, SF_RD, SF_RU
};

static const uint16_t FSIN_EXHAUSTIVE_CONTROL_WORDS[] = {
    0x037f, 0x077f, 0x0b7f
};

enum {
    FSIN_EXHAUSTIVE_STATUS_C1 = 0x0200,
    FSIN_EXHAUSTIVE_STATUS_C2 = 0x0400
};

typedef struct __attribute__((packed)) {
    uint64_t significand;
    uint16_t sign_exponent;
} fsin_exhaustive_x80_mem_t;

typedef struct {
    uint64_t inputs;
    uint64_t observations;
    uint64_t zeros;
    uint64_t subnormals;
    uint64_t finite_normals;
    uint64_t infinities;
    uint64_t quiet_nans;
    uint64_t signaling_nans;
    uint64_t output_misses;
    uint64_t c1_misses;
    uint64_t c2_misses;
    uint64_t c2_output_misses;
    uint64_t model_interval_failures;
} fsin_exhaustive_counts_t;

typedef struct {
    uint64_t start;
    uint64_t count;
    uint64_t seed;
    unsigned thread_index;
    unsigned thread_count;
    unsigned mode_mask;
    uint64_t report_limit;
    fsin_exhaustive_counts_t counts;
} fsin_exhaustive_worker_t;

static pthread_mutex_t g_fsin_exhaustive_report_lock =
    PTHREAD_MUTEX_INITIALIZER;
static uint64_t g_fsin_exhaustive_reports;

/*
 * bijective SplitMix64 output permutation.  Addition,
 * odd multiplication, and right-xor shifts are each invertible modulo 2^64.
 */
static uint64_t fsin_exhaustive_permute(uint64_t counter, uint64_t seed)
{
    uint64_t value = counter + seed + UINT64_C(0x9e3779b97f4a7c15);
    value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
}

/*
 * exact binary64-bit-pattern to x87-register value
 * conversion.  Binary64 subnormals become normalized extended values, as they
 * do after a successful FLD.
 */
static x80_t fsin_exhaustive_binary64_to_x80(uint64_t bits)
{
    unsigned sign = (unsigned)(bits >> 63);
    unsigned exponent = (unsigned)((bits >> 52) & 0x7ffu);
    uint64_t fraction = bits & UINT64_C(0x000fffffffffffff);
    x80_t result = { 0, 0 };

    if (exponent == 0) {
        if (!fraction) {
            result.se = (uint16_t)(sign << 15);
            return result;
        }
        int leading = 63 - __builtin_clzll(fraction);
        int unbiased = leading - 1074;
        result.se = (uint16_t)(
            (sign << 15) | (unsigned)(unbiased + 16383));
        result.sig = fraction << (63 - leading);
        return result;
    }
    if (exponent == 0x7ffu) {
        result.se = (uint16_t)((sign << 15) | 0x7fffu);
        result.sig = UINT64_C(0x8000000000000000) | (fraction << 11);
        return result;
    }
    result.se = (uint16_t)(
        (sign << 15) | (unsigned)((int)exponent - 1023 + 16383));
    result.sig = UINT64_C(0x8000000000000000) | (fraction << 11);
    return result;
}

/* inventory the binary64 classes actually sampled. */
static void fsin_exhaustive_count_class(
    fsin_exhaustive_counts_t *counts, uint64_t bits)
{
    unsigned exponent = (unsigned)((bits >> 52) & 0x7ffu);
    uint64_t fraction = bits & UINT64_C(0x000fffffffffffff);
    if (!exponent) {
        if (fraction)
            counts->subnormals++;
        else
            counts->zeros++;
    } else if (exponent != 0x7ffu) {
        counts->finite_normals++;
    } else if (!fraction) {
        counts->infinities++;
    } else if (fraction & UINT64_C(0x0008000000000000)) {
        counts->quiet_nans++;
    } else {
        counts->signaling_nans++;
    }
}

/*
 * execute one real FSIN and capture its result and
 * instruction-local status.  The x87 stack is balanced on every path.
 */
static uint16_t fsin_exhaustive_hardware(
    x80_t input, uint16_t control_word, x80_t *output)
{
    fsin_exhaustive_x80_mem_t in = {
        input.sig, input.se
    };
    fsin_exhaustive_x80_mem_t out;
    uint16_t status;

    __asm__ volatile(
        "fldcw  %[cw]\n\t"
        "fnclex\n\t"
        "fldt   %[in]\n\t"
        "fsin\n\t"
        "fwait\n\t"
        "fnstsw %%ax\n\t"
        "movw   %%ax, %[status]\n\t"
        "fstpt  %[out]"
        : [status] "=m" (status), [out] "=m" (out)
        : [cw] "m" (control_word), [in] "m" (in)
        : "ax", "st", "st(1)", "st(2)", "st(3)",
          "st(4)", "st(5)", "st(6)", "st(7)");

    output->se = out.sign_exponent;
    output->sig = out.significand;
    return status;
}

/* compare exact x87 result encodings. */
static int fsin_exhaustive_x80_equal(x80_t left, x80_t right)
{
    return left.se == right.se && left.sig == right.sig;
}

/*
 * derive the model's final magnitude-increment bit
 * from its directed bounds.  This is the same quantity exposed as x87 C1:
 * the away-from-zero bound is incrementing and the toward-zero bound is not.
 */
static int fsin_exhaustive_model_c1(
    const x80_t outputs[FSIN_EXHAUSTIVE_MODE_COUNT],
    const fsincos_status_t statuses[FSIN_EXHAUSTIVE_MODE_COUNT],
    unsigned mode)
{
    if (statuses[mode] == FSINCOS_C2)
        return 0;
    const x80_t rd = outputs[FSIN_EXHAUSTIVE_RD];
    const x80_t ru = outputs[FSIN_EXHAUSTIVE_RU];
    if (fsin_exhaustive_x80_equal(rd, ru))
        return 0;

    unsigned sign = outputs[mode].se >> 15;
    x80_t away = sign ? rd : ru;
    x80_t toward = sign ? ru : rd;
    if (fsin_exhaustive_x80_equal(outputs[mode], away))
        return 1;
    if (fsin_exhaustive_x80_equal(outputs[mode], toward))
        return 0;
    return -1;
}

/*
 * install the validated standalone-FSIN model
 * configuration once before worker threads begin.
 */
static void fsin_exhaustive_configure_model(void)
{
    /* the validated rounds are inlined unconditionally in
     * fsincos_skylake.c (2026-08-15 master-algorithm fold); only
     * the instruction-path selector remains configurable. */
    g_fsin_standalone_path = 1;
}

/*
 * report a bounded mismatch record.  Exhaustive
 * runs count every mismatch but never permit an unexpected failure population
 * to create unbounded output.
 */
static void fsin_exhaustive_report(
    const fsin_exhaustive_worker_t *worker,
    uint64_t counter, uint64_t raw, x80_t input, unsigned mode,
    const char *kind, x80_t model, fsincos_status_t model_status,
    int model_c1, x80_t hardware, uint16_t hardware_status)
{
    pthread_mutex_lock(&g_fsin_exhaustive_report_lock);
    if (g_fsin_exhaustive_reports < worker->report_limit) {
        printf(
            "MISMATCH kind=%s counter=%016" PRIx64
            " raw64=%016" PRIx64
            " input=%04x:%016" PRIx64
            " mode=%s model_class=%s model=%04x:%016" PRIx64
            " model_c1=%d hardware=%04x:%016" PRIx64
            " hardware_sw=%04x\n",
            kind,
            counter,
            raw,
            input.se,
            input.sig,
            FSIN_EXHAUSTIVE_MODE_NAMES[mode],
            model_status == FSINCOS_C2 ? "C2" : "OK",
            model.se,
            model.sig,
            model_c1,
            hardware.se,
            hardware.sig,
            hardware_status);
        fflush(stdout);
        g_fsin_exhaustive_reports++;
    }
    pthread_mutex_unlock(&g_fsin_exhaustive_report_lock);
}

/* independently process one counter shard. */
static void *fsin_exhaustive_worker(void *opaque)
{
    fsin_exhaustive_worker_t *worker = opaque;
    __asm__ volatile("fninit");

    for (
        uint64_t offset = worker->thread_index;
        offset < worker->count;
        offset += worker->thread_count
    ) {
        uint64_t counter = worker->start + offset;
        uint64_t raw = fsin_exhaustive_permute(counter, worker->seed);
        x80_t input = fsin_exhaustive_binary64_to_x80(raw);
        x80_t model[FSIN_EXHAUSTIVE_MODE_COUNT] = {{0, 0}};
        fsincos_status_t model_status[FSIN_EXHAUSTIVE_MODE_COUNT];

        for (unsigned mode = 0; mode < FSIN_EXHAUSTIVE_MODE_COUNT; mode++) {
            model_status[mode] = fsin_ref(
                input, &model[mode], FSIN_EXHAUSTIVE_MODEL_MODES[mode]);
        }

        worker->counts.inputs++;
        fsin_exhaustive_count_class(&worker->counts, raw);
        for (unsigned mode = 0; mode < FSIN_EXHAUSTIVE_MODE_COUNT; mode++) {
            if (!(worker->mode_mask & (1u << mode)))
                continue;
            x80_t hardware = { 0, 0 };
            uint16_t hardware_status = fsin_exhaustive_hardware(
                input, FSIN_EXHAUSTIVE_CONTROL_WORDS[mode], &hardware);
            int hardware_c2 = !!(
                hardware_status & FSIN_EXHAUSTIVE_STATUS_C2);
            int model_c2 = model_status[mode] == FSINCOS_C2;
            int model_c1 = fsin_exhaustive_model_c1(
                model, model_status, mode);
            worker->counts.observations++;

            if (model_c1 < 0) {
                worker->counts.model_interval_failures++;
                fsin_exhaustive_report(
                    worker, counter, raw, input, mode, "model-interval",
                    model[mode], model_status[mode], model_c1,
                    hardware, hardware_status);
                continue;
            }
            if (model_c2 != hardware_c2) {
                worker->counts.c2_misses++;
                fsin_exhaustive_report(
                    worker, counter, raw, input, mode, "C2",
                    model[mode], model_status[mode], model_c1,
                    hardware, hardware_status);
                continue;
            }
            if (hardware_c2) {
                if (!fsin_exhaustive_x80_equal(input, hardware)) {
                    worker->counts.c2_output_misses++;
                    fsin_exhaustive_report(
                        worker, counter, raw, input, mode, "C2-output",
                        model[mode], model_status[mode], model_c1,
                        hardware, hardware_status);
                }
                continue;
            }
            if (!fsin_exhaustive_x80_equal(model[mode], hardware)) {
                worker->counts.output_misses++;
                fsin_exhaustive_report(
                    worker, counter, raw, input, mode, "output",
                    model[mode], model_status[mode], model_c1,
                    hardware, hardware_status);
            }
            if (model_c1 != !!(
                    hardware_status & FSIN_EXHAUSTIVE_STATUS_C1)) {
                worker->counts.c1_misses++;
                fsin_exhaustive_report(
                    worker, counter, raw, input, mode, "C1",
                    model[mode], model_status[mode], model_c1,
                    hardware, hardware_status);
            }
        }
    }
    return NULL;
}

/* parse one unsigned command-line integer. */
static uint64_t fsin_exhaustive_parse_u64(const char *text, const char *name)
{
    char *end = NULL;
    errno = 0;
    unsigned long long value = strtoull(text, &end, 0);
    if (errno || !end || *end) {
        fprintf(stderr, "invalid %s: %s\n", name, text);
        exit(2);
    }
    return (uint64_t)value;
}

/* monotonic elapsed seconds. */
static double fsin_exhaustive_seconds(
    const struct timespec *start, const struct timespec *end)
{
    return (double)(end->tv_sec - start->tv_sec)
        + (double)(end->tv_nsec - start->tv_nsec) / 1000000000.0;
}

/* exhaustive comparison command-line entry point. */
int main(int argc, char **argv)
{
    uint64_t start = 0;
    uint64_t count = 0;
    uint64_t seed = UINT64_C(0xf51c05d1a64e2026);
    uint64_t report_limit = 64;
    unsigned threads = 1;
    unsigned mode_mask = (1u << FSIN_EXHAUSTIVE_MODE_COUNT) - 1;
    int have_count = 0;

    for (int index = 1; index < argc; index++) {
        const char *argument = argv[index];
        if (!strncmp(argument, "--bits=", 7)) {
            uint64_t bits = fsin_exhaustive_parse_u64(
                argument + 7, "bits");
            if (bits > 63) {
                fprintf(stderr, "--bits must be 0..63\n");
                return 2;
            }
            count = UINT64_C(1) << bits;
            have_count = 1;
        } else if (!strncmp(argument, "--start=", 8)) {
            start = fsin_exhaustive_parse_u64(argument + 8, "start");
        } else if (!strncmp(argument, "--count=", 8)) {
            count = fsin_exhaustive_parse_u64(argument + 8, "count");
            have_count = 1;
        } else if (!strncmp(argument, "--seed=", 7)) {
            seed = fsin_exhaustive_parse_u64(argument + 7, "seed");
        } else if (!strncmp(argument, "--threads=", 10)) {
            uint64_t parsed = fsin_exhaustive_parse_u64(
                argument + 10, "threads");
            if (!parsed || parsed > 1024) {
                fprintf(stderr, "--threads must be 1..1024\n");
                return 2;
            }
            threads = (unsigned)parsed;
        } else if (!strncmp(argument, "--max-report=", 13)) {
            report_limit = fsin_exhaustive_parse_u64(
                argument + 13, "max-report");
        } else if (!strcmp(argument, "--mode=rn")) {
            mode_mask = 1u << FSIN_EXHAUSTIVE_RN;
        } else if (!strcmp(argument, "--mode=rd")) {
            mode_mask = 1u << FSIN_EXHAUSTIVE_RD;
        } else if (!strcmp(argument, "--mode=ru")) {
            mode_mask = 1u << FSIN_EXHAUSTIVE_RU;
        } else if (!strcmp(argument, "--mode=all")) {
            mode_mask = (1u << FSIN_EXHAUSTIVE_MODE_COUNT) - 1;
        } else {
            fprintf(stderr, "unknown argument: %s\n", argument);
            return 2;
        }
    }
    if (!have_count || !count) {
        fprintf(
            stderr,
            "usage: %s (--bits=N|--count=N) [--start=N] [--seed=N] "
            "[--threads=N] [--mode=rn|rd|ru|all] [--max-report=N]\n",
            argv[0]);
        return 2;
    }
    if (start > UINT64_MAX - (count - 1)) {
        fprintf(stderr, "counter range wraps uint64_t\n");
        return 2;
    }

    fsin_exhaustive_configure_model();
    pthread_t *thread_ids = calloc(threads, sizeof(*thread_ids));
    fsin_exhaustive_worker_t *workers = calloc(
        threads, sizeof(*workers));
    if (!thread_ids || !workers) {
        fprintf(stderr, "worker allocation failed\n");
        return 2;
    }

    struct timespec begin, end;
    clock_gettime(CLOCK_MONOTONIC, &begin);
    for (unsigned index = 0; index < threads; index++) {
        workers[index] = (fsin_exhaustive_worker_t){
            start,
            count,
            seed,
            index,
            threads,
            mode_mask,
            report_limit,
            { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
        };
        int error = pthread_create(
            &thread_ids[index], NULL,
            fsin_exhaustive_worker, &workers[index]);
        if (error) {
            fprintf(stderr, "pthread_create: %s\n", strerror(error));
            return 2;
        }
    }

    fsin_exhaustive_counts_t total = {
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    };
    for (unsigned index = 0; index < threads; index++) {
        int error = pthread_join(thread_ids[index], NULL);
        if (error) {
            fprintf(stderr, "pthread_join: %s\n", strerror(error));
            return 2;
        }
        total.inputs += workers[index].counts.inputs;
        total.observations += workers[index].counts.observations;
        total.zeros += workers[index].counts.zeros;
        total.subnormals += workers[index].counts.subnormals;
        total.finite_normals += workers[index].counts.finite_normals;
        total.infinities += workers[index].counts.infinities;
        total.quiet_nans += workers[index].counts.quiet_nans;
        total.signaling_nans += workers[index].counts.signaling_nans;
        total.output_misses += workers[index].counts.output_misses;
        total.c1_misses += workers[index].counts.c1_misses;
        total.c2_misses += workers[index].counts.c2_misses;
        total.c2_output_misses += workers[index].counts.c2_output_misses;
        total.model_interval_failures +=
            workers[index].counts.model_interval_failures;
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    double elapsed = fsin_exhaustive_seconds(&begin, &end);
    uint64_t failures = total.output_misses
        + total.c1_misses
        + total.c2_misses
        + total.c2_output_misses
        + total.model_interval_failures;
    printf(
        "SUMMARY start=%016" PRIx64
        " count=%" PRIu64
        " seed=%016" PRIx64
        " threads=%u mode_mask=%x"
        " inputs=%" PRIu64
        " observations=%" PRIu64
        " classes=zero:%" PRIu64
        ",subnormal:%" PRIu64
        ",normal:%" PRIu64
        ",infinity:%" PRIu64
        ",qnan:%" PRIu64
        ",snan:%" PRIu64
        " output_misses=%" PRIu64
        " C1_misses=%" PRIu64
        " C2_misses=%" PRIu64
        " C2_output_misses=%" PRIu64
        " model_interval_failures=%" PRIu64
        " elapsed=%.6f inputs_per_second=%.3f\n",
        start,
        count,
        seed,
        threads,
        mode_mask,
        total.inputs,
        total.observations,
        total.zeros,
        total.subnormals,
        total.finite_normals,
        total.infinities,
        total.quiet_nans,
        total.signaling_nans,
        total.output_misses,
        total.c1_misses,
        total.c2_misses,
        total.c2_output_misses,
        total.model_interval_failures,
        elapsed,
        elapsed ? (double)total.inputs / elapsed : 0.0);

    free(thread_ids);
    free(workers);
    return failures ? 1 : 0;
}

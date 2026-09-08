/*
 * Deterministic binary64-space comparison of hardware F2XM1/FPTAN with the
 * reconstructed software entry points.
 *
 * Each counter is mapped through the same bijective SplitMix64 permutation as
 * fsin_exhaustive.c. A complete 2^64 traversal therefore visits every IEEE-754
 * binary64 encoding exactly once. Inputs are converted exactly to x87
 * extended-register values before either implementation is called.
 *
 * Build only on the target x86 Linux host:
 *   make sibling_exhaustive
 */

#if !defined(__i386__) && !defined(__x86_64__)
#error "the exhaustive sibling comparator requires native x87 hardware"
#endif

#define main fsincos_skylake_embedded_main
#include "fsincos_skylake.c"
#undef main

#include <errno.h>
#include <inttypes.h>
#include <pthread.h>
#include <time.h>

typedef enum {
    SIBLING_F2XM1,
    SIBLING_FPTAN
} sibling_instruction_t;

enum {
    SIBLING_RN = 0,
    SIBLING_RD = 1,
    SIBLING_RU = 2,
    SIBLING_MODE_COUNT = 3
};

static const char *const SIBLING_MODE_NAMES[] = {
    "rn", "rd", "ru"
};

static const sf_rc_t SIBLING_MODEL_MODES[] = {
    SF_RN, SF_RD, SF_RU
};

static const uint16_t SIBLING_CONTROL_WORDS[] = {
    0x037f, 0x077f, 0x0b7f
};

enum {
    SIBLING_STATUS_C1 = 0x0200,
    SIBLING_STATUS_C2 = 0x0400
};

typedef struct __attribute__((packed)) {
    uint64_t significand;
    uint16_t sign_exponent;
} sibling_x80_mem_t;

typedef enum {
    SIBLING_SCOPE_DEFINED,
    SIBLING_SCOPE_OUT_OF_RANGE,
    SIBLING_SCOPE_SPECIAL
} sibling_scope_t;

typedef struct {
    uint64_t inputs;
    uint64_t observations;
    uint64_t zeros;
    uint64_t subnormals;
    uint64_t finite_normals;
    uint64_t infinities;
    uint64_t quiet_nans;
    uint64_t signaling_nans;
    uint64_t defined_inputs;
    uint64_t out_of_range_inputs;
    uint64_t special_inputs;
    uint64_t output_misses;
    uint64_t defined_output_misses;
    uint64_t c1_misses;
    uint64_t defined_c1_misses;
    uint64_t c2_misses;
    uint64_t c2_output_misses;
    uint64_t pushed_one_misses;
    uint64_t model_interval_failures;
} sibling_counts_t;

typedef struct {
    uint64_t start;
    uint64_t count;
    uint64_t seed;
    unsigned thread_index;
    unsigned thread_count;
    unsigned mode_mask;
    uint64_t report_limit;
    sibling_instruction_t instruction;
    sibling_counts_t counts;
} sibling_worker_t;

static pthread_mutex_t g_sibling_report_lock = PTHREAD_MUTEX_INITIALIZER;
static uint64_t g_sibling_reports;

/* bijective SplitMix64 output permutation. */
static uint64_t sibling_permute(uint64_t counter, uint64_t seed)
{
    uint64_t value = counter + seed + UINT64_C(0x9e3779b97f4a7c15);
    value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
}

/*
 * exact binary64-bit-pattern to x87-register value
 * conversion, including normalization of successfully loaded subnormals.
 */
static x80_t sibling_binary64_to_x80(uint64_t bits)
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

/* inventory the binary64 classes sampled. */
static void sibling_count_class(sibling_counts_t *counts, uint64_t bits)
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
 * classify the architecturally documented finite
 * input range separately from empirical out-of-range and special behavior.
 */
static sibling_scope_t sibling_scope(
    sibling_instruction_t instruction, uint64_t bits)
{
    unsigned exponent = (unsigned)((bits >> 52) & 0x7ffu);
    uint64_t fraction = bits & UINT64_C(0x000fffffffffffff);
    if (exponent == 0x7ffu)
        return SIBLING_SCOPE_SPECIAL;
    if (instruction == SIBLING_F2XM1) {
        if (exponent < 1023 || (exponent == 1023 && !fraction))
            return SIBLING_SCOPE_DEFINED;
        return SIBLING_SCOPE_OUT_OF_RANGE;
    }
    if (exponent < 1086)
        return SIBLING_SCOPE_DEFINED;
    return SIBLING_SCOPE_OUT_OF_RANGE;
}

/* execute and balance one hardware F2XM1. */
static uint16_t sibling_hardware_f2xm1(
    x80_t input, uint16_t control_word, x80_t *output)
{
    sibling_x80_mem_t in = { input.sig, input.se };
    sibling_x80_mem_t out;
    uint16_t status;

    __asm__ volatile(
        "fldcw  %[cw]\n\t"
        "fnclex\n\t"
        "fldt   %[in]\n\t"
        "f2xm1\n\t"
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

/*
 * execute one hardware FPTAN, retaining the input on
 * C2 and recording both the tangent and pushed exact-one on success.
 */
static uint16_t sibling_hardware_fptan(
    x80_t input, uint16_t control_word, x80_t *output, x80_t *pushed_one)
{
    sibling_x80_mem_t in = { input.sig, input.se };
    sibling_x80_mem_t out = { 0, 0 };
    sibling_x80_mem_t one = { 0, 0 };
    uint16_t status;

    __asm__ volatile(
        "fldcw  %[cw]\n\t"
        "fnclex\n\t"
        "fldt   %[in]\n\t"
        "fptan\n\t"
        "fwait\n\t"
        "fnstsw %%ax\n\t"
        "movw   %%ax, %[status]"
        : [status] "=m" (status)
        : [cw] "m" (control_word), [in] "m" (in)
        : "ax", "st", "st(1)", "st(2)", "st(3)",
          "st(4)", "st(5)", "st(6)", "st(7)");

    if (status & SIBLING_STATUS_C2) {
        __asm__ volatile(
            "fstpt %[out]"
            : [out] "=m" (out)
            :
            : "st");
    } else {
        __asm__ volatile(
            "fstpt %[one]\n\t"
            "fstpt %[out]"
            : [one] "=m" (one), [out] "=m" (out)
            :
            : "st", "st(1)");
    }

    output->se = out.sign_exponent;
    output->sig = out.significand;
    pushed_one->se = one.sign_exponent;
    pushed_one->sig = one.significand;
    return status;
}

/* compare exact x87 result encodings. */
static int sibling_x80_equal(x80_t left, x80_t right)
{
    return left.se == right.se && left.sig == right.sig;
}

/*
 * derive the model's magnitude-increment/C1 bit from
 * its directed bounds.
 */
static int sibling_model_c1(
    const x80_t outputs[SIBLING_MODE_COUNT],
    const fsincos_status_t statuses[SIBLING_MODE_COUNT],
    unsigned mode)
{
    if (statuses[mode] == FSINCOS_C2)
        return 0;
    const x80_t rd = outputs[SIBLING_RD];
    const x80_t ru = outputs[SIBLING_RU];
    if (sibling_x80_equal(rd, ru))
        return 0;

    unsigned sign = outputs[mode].se >> 15;
    x80_t away = sign ? rd : ru;
    x80_t toward = sign ? ru : rd;
    if (sibling_x80_equal(outputs[mode], away))
        return 1;
    if (sibling_x80_equal(outputs[mode], toward))
        return 0;
    return -1;
}

/* bounded mismatch reporting. */
static void sibling_report(
    const sibling_worker_t *worker,
    uint64_t counter, uint64_t raw, x80_t input, unsigned mode,
    const char *kind, x80_t model, fsincos_status_t model_status,
    int model_c1, x80_t hardware, uint16_t hardware_status)
{
    pthread_mutex_lock(&g_sibling_report_lock);
    if (g_sibling_reports < worker->report_limit) {
        printf(
            "MISMATCH instruction=%s kind=%s counter=%016" PRIx64
            " raw64=%016" PRIx64
            " input=%04x:%016" PRIx64
            " mode=%s model_class=%s model=%04x:%016" PRIx64
            " model_c1=%d hardware=%04x:%016" PRIx64
            " hardware_sw=%04x\n",
            worker->instruction == SIBLING_F2XM1 ? "f2xm1" : "fptan",
            kind,
            counter,
            raw,
            input.se,
            input.sig,
            SIBLING_MODE_NAMES[mode],
            model_status == FSINCOS_C2 ? "C2" : "OK",
            model.se,
            model.sig,
            model_c1,
            hardware.se,
            hardware.sig,
            hardware_status);
        fflush(stdout);
        g_sibling_reports++;
    }
    pthread_mutex_unlock(&g_sibling_report_lock);
}

/* process one deterministic counter shard. */
static void *sibling_worker(void *opaque)
{
    sibling_worker_t *worker = opaque;
    const x80_t exact_one = {
        0x3fff, UINT64_C(0x8000000000000000)
    };
    __asm__ volatile("fninit");

    for (
        uint64_t offset = worker->thread_index;
        offset < worker->count;
        offset += worker->thread_count
    ) {
        uint64_t counter = worker->start + offset;
        uint64_t raw = sibling_permute(counter, worker->seed);
        x80_t input = sibling_binary64_to_x80(raw);
        sibling_scope_t scope = sibling_scope(worker->instruction, raw);
        x80_t model[SIBLING_MODE_COUNT] = {
            input, input, input
        };
        fsincos_status_t model_status[SIBLING_MODE_COUNT];

        for (unsigned mode = 0; mode < SIBLING_MODE_COUNT; mode++) {
            if (worker->instruction == SIBLING_F2XM1) {
                model_status[mode] = f2xm1_ref(
                    input, &model[mode], SIBLING_MODEL_MODES[mode]);
            } else {
                model_status[mode] = fptan_ref(
                    input, &model[mode], SIBLING_MODEL_MODES[mode]);
            }
        }

        worker->counts.inputs++;
        sibling_count_class(&worker->counts, raw);
        if (scope == SIBLING_SCOPE_DEFINED)
            worker->counts.defined_inputs++;
        else if (scope == SIBLING_SCOPE_OUT_OF_RANGE)
            worker->counts.out_of_range_inputs++;
        else
            worker->counts.special_inputs++;

        for (unsigned mode = 0; mode < SIBLING_MODE_COUNT; mode++) {
            if (!(worker->mode_mask & (1u << mode)))
                continue;
            x80_t hardware = { 0, 0 };
            x80_t pushed_one = { 0, 0 };
            uint16_t hardware_status;
            if (worker->instruction == SIBLING_F2XM1) {
                hardware_status = sibling_hardware_f2xm1(
                    input, SIBLING_CONTROL_WORDS[mode], &hardware);
            } else {
                hardware_status = sibling_hardware_fptan(
                    input, SIBLING_CONTROL_WORDS[mode],
                    &hardware, &pushed_one);
            }
            int hardware_c2 = (
                worker->instruction == SIBLING_FPTAN
                && (hardware_status & SIBLING_STATUS_C2)
            );
            int model_c2 = model_status[mode] == FSINCOS_C2;
            int model_c1 = sibling_model_c1(
                model, model_status, mode);
            worker->counts.observations++;

            if (model_c1 < 0) {
                worker->counts.model_interval_failures++;
                sibling_report(
                    worker, counter, raw, input, mode, "model-interval",
                    model[mode], model_status[mode], model_c1,
                    hardware, hardware_status);
                continue;
            }
            if (model_c2 != hardware_c2) {
                worker->counts.c2_misses++;
                sibling_report(
                    worker, counter, raw, input, mode, "C2",
                    model[mode], model_status[mode], model_c1,
                    hardware, hardware_status);
                continue;
            }
            if (hardware_c2) {
                if (!sibling_x80_equal(input, hardware)) {
                    worker->counts.c2_output_misses++;
                    sibling_report(
                        worker, counter, raw, input, mode, "C2-output",
                        model[mode], model_status[mode], model_c1,
                        hardware, hardware_status);
                }
                continue;
            }
            if (!sibling_x80_equal(model[mode], hardware)) {
                worker->counts.output_misses++;
                if (scope == SIBLING_SCOPE_DEFINED)
                    worker->counts.defined_output_misses++;
                sibling_report(
                    worker, counter, raw, input, mode, "output",
                    model[mode], model_status[mode], model_c1,
                    hardware, hardware_status);
            }
            /* NaN/indefinite tangents push a second copy of the result
             * rather than exact one. */
            x80_t expected_push =
                (model[mode].se & 0x7fff) == 0x7fff
                    ? model[mode]
                    : exact_one;
            if (
                worker->instruction == SIBLING_FPTAN
                && !sibling_x80_equal(pushed_one, expected_push)
            ) {
                worker->counts.pushed_one_misses++;
                sibling_report(
                    worker, counter, raw, input, mode, "pushed-one",
                    model[mode], model_status[mode], model_c1,
                    pushed_one, hardware_status);
            }
            if (model_c1 != !!(
                    hardware_status & SIBLING_STATUS_C1)) {
                worker->counts.c1_misses++;
                if (scope == SIBLING_SCOPE_DEFINED)
                    worker->counts.defined_c1_misses++;
                sibling_report(
                    worker, counter, raw, input, mode, "C1",
                    model[mode], model_status[mode], model_c1,
                    hardware, hardware_status);
            }
        }
    }
    return NULL;
}

/* parse one unsigned command-line integer. */
static uint64_t sibling_parse_u64(const char *text, const char *name)
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
static double sibling_seconds(
    const struct timespec *start, const struct timespec *end)
{
    return (double)(end->tv_sec - start->tv_sec)
        + (double)(end->tv_nsec - start->tv_nsec) / 1000000000.0;
}

/* add one worker's counters to the total. */
static void sibling_add_counts(
    sibling_counts_t *total, const sibling_counts_t *part)
{
#define SIBLING_ADD(field) total->field += part->field
    SIBLING_ADD(inputs);
    SIBLING_ADD(observations);
    SIBLING_ADD(zeros);
    SIBLING_ADD(subnormals);
    SIBLING_ADD(finite_normals);
    SIBLING_ADD(infinities);
    SIBLING_ADD(quiet_nans);
    SIBLING_ADD(signaling_nans);
    SIBLING_ADD(defined_inputs);
    SIBLING_ADD(out_of_range_inputs);
    SIBLING_ADD(special_inputs);
    SIBLING_ADD(output_misses);
    SIBLING_ADD(defined_output_misses);
    SIBLING_ADD(c1_misses);
    SIBLING_ADD(defined_c1_misses);
    SIBLING_ADD(c2_misses);
    SIBLING_ADD(c2_output_misses);
    SIBLING_ADD(pushed_one_misses);
    SIBLING_ADD(model_interval_failures);
#undef SIBLING_ADD
}

/* exhaustive comparison command-line entry point. */
int main(int argc, char **argv)
{
    uint64_t start = 0;
    uint64_t count = 0;
    uint64_t seed = UINT64_C(0xf51c05d1a64e2026);
    uint64_t report_limit = 64;
    unsigned threads = 1;
    unsigned mode_mask = (1u << SIBLING_MODE_COUNT) - 1;
    sibling_instruction_t instruction = SIBLING_F2XM1;
    int have_count = 0;
    int have_instruction = 0;

    for (int index = 1; index < argc; index++) {
        const char *argument = argv[index];
        if (!strncmp(argument, "--bits=", 7)) {
            uint64_t bits = sibling_parse_u64(argument + 7, "bits");
            if (bits > 63) {
                fprintf(stderr, "--bits must be 0..63\n");
                return 2;
            }
            count = UINT64_C(1) << bits;
            have_count = 1;
        } else if (!strncmp(argument, "--start=", 8)) {
            start = sibling_parse_u64(argument + 8, "start");
        } else if (!strncmp(argument, "--count=", 8)) {
            count = sibling_parse_u64(argument + 8, "count");
            have_count = 1;
        } else if (!strncmp(argument, "--seed=", 7)) {
            seed = sibling_parse_u64(argument + 7, "seed");
        } else if (!strncmp(argument, "--threads=", 10)) {
            uint64_t parsed = sibling_parse_u64(
                argument + 10, "threads");
            if (!parsed || parsed > 1024) {
                fprintf(stderr, "--threads must be 1..1024\n");
                return 2;
            }
            threads = (unsigned)parsed;
        } else if (!strncmp(argument, "--max-report=", 13)) {
            report_limit = sibling_parse_u64(
                argument + 13, "max-report");
        } else if (!strcmp(argument, "--instruction=f2xm1")) {
            instruction = SIBLING_F2XM1;
            have_instruction = 1;
        } else if (!strcmp(argument, "--instruction=fptan")) {
            instruction = SIBLING_FPTAN;
            have_instruction = 1;
        } else if (!strcmp(argument, "--mode=rn")) {
            mode_mask = 1u << SIBLING_RN;
        } else if (!strcmp(argument, "--mode=rd")) {
            mode_mask = 1u << SIBLING_RD;
        } else if (!strcmp(argument, "--mode=ru")) {
            mode_mask = 1u << SIBLING_RU;
        } else if (!strcmp(argument, "--mode=all")) {
            mode_mask = (1u << SIBLING_MODE_COUNT) - 1;
        } else {
            fprintf(stderr, "unknown argument: %s\n", argument);
            return 2;
        }
    }
    if (!have_instruction || !have_count || !count) {
        fprintf(
            stderr,
            "usage: %s --instruction=f2xm1|fptan "
            "(--bits=N|--count=N) [--start=N] [--seed=N] "
            "[--threads=N] [--mode=rn|rd|ru|all] [--max-report=N]\n",
            argv[0]);
        return 2;
    }
    if (start > UINT64_MAX - (count - 1)) {
        fprintf(stderr, "counter range wraps uint64_t\n");
        return 2;
    }

    pthread_t *thread_ids = calloc(threads, sizeof(*thread_ids));
    sibling_worker_t *workers = calloc(threads, sizeof(*workers));
    if (!thread_ids || !workers) {
        fprintf(stderr, "worker allocation failed\n");
        return 2;
    }

    struct timespec begin, end;
    clock_gettime(CLOCK_MONOTONIC, &begin);
    for (unsigned index = 0; index < threads; index++) {
        workers[index] = (sibling_worker_t){
            .start = start,
            .count = count,
            .seed = seed,
            .thread_index = index,
            .thread_count = threads,
            .mode_mask = mode_mask,
            .report_limit = report_limit,
            .instruction = instruction,
            .counts = { 0 }
        };
        int error = pthread_create(
            &thread_ids[index], NULL, sibling_worker, &workers[index]);
        if (error) {
            fprintf(stderr, "pthread_create: %s\n", strerror(error));
            return 2;
        }
    }

    sibling_counts_t total = { 0 };
    for (unsigned index = 0; index < threads; index++) {
        int error = pthread_join(thread_ids[index], NULL);
        if (error) {
            fprintf(stderr, "pthread_join: %s\n", strerror(error));
            return 2;
        }
        sibling_add_counts(&total, &workers[index].counts);
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    double elapsed = sibling_seconds(&begin, &end);
    uint64_t failures = total.output_misses
        + total.c1_misses
        + total.c2_misses
        + total.c2_output_misses
        + total.pushed_one_misses
        + total.model_interval_failures;
    printf(
        "SUMMARY instruction=%s"
        " start=%016" PRIx64
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
        " scope=defined:%" PRIu64
        ",out_of_range:%" PRIu64
        ",special:%" PRIu64
        " output_misses=%" PRIu64
        " defined_output_misses=%" PRIu64
        " C1_misses=%" PRIu64
        " defined_C1_misses=%" PRIu64
        " C2_misses=%" PRIu64
        " C2_output_misses=%" PRIu64
        " pushed_one_misses=%" PRIu64
        " model_interval_failures=%" PRIu64
        " elapsed=%.6f inputs_per_second=%.3f\n",
        instruction == SIBLING_F2XM1 ? "f2xm1" : "fptan",
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
        total.defined_inputs,
        total.out_of_range_inputs,
        total.special_inputs,
        total.output_misses,
        total.defined_output_misses,
        total.c1_misses,
        total.defined_c1_misses,
        total.c2_misses,
        total.c2_output_misses,
        total.pushed_one_misses,
        total.model_interval_failures,
        elapsed,
        elapsed ? (double)total.inputs / elapsed : 0.0);

    free(thread_ids);
    free(workers);
    return failures ? 1 : 0;
}

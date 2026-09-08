/* Exact compiled CSP for the H1504 fixed-polarity opcode mapper.
 *
 * The input supplies recovered physical rows and the complete allowed opcode
 * list.  Each logical opcode bit selects one signed physical channel, with
 * distinct underlying channels.  Per-row allowed-opcode bitsets are narrowed
 * exactly as assignments are made.  Empty domains prune; reaching depth 12 is
 * a validated SAT witness; exhausting the tree is UNSAT; a time bound is
 * reported only as UNKNOWN.
 *
 * This intentionally omits H1543's Hall check.  Matching H1544's result and
 * node count therefore provides an independent compiled replay of the core
 * row-domain search.
 */

#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

enum {
    MAX_ROWS = 64,
    MAX_ALLOWED = 4096,
    MAX_WORDS = MAX_ALLOWED / 64,
    DWORDS = 8,
    BITS_PER_DWORD = 31,
    CHANNELS = DWORDS * BITS_PER_DWORD,
    LITERALS = CHANNELS * 2,
    LOGICAL_BITS = 12,
};

typedef struct {
    int logical_bit;
    int count;
    uint64_t ambiguity;
    uint16_t literals[LITERALS];
} Domain;

typedef struct {
    uint64_t score;
    uint16_t literal;
} Ranked;

typedef struct {
    int row_count;
    int allowed_count;
    int word_count;
    uint32_t rows[MAX_ROWS][DWORDS];
    uint16_t allowed[MAX_ALLOWED];
    uint64_t allowed_by_bit[LOGICAL_BITS][2][MAX_WORDS];
    uint64_t literal_patterns[LITERALS];
    double deadline;
    uint64_t nodes;
    uint64_t dead_ends;
    uint64_t domain_failures;
    int maximum_depth;
    int timed_out;
    int assignment[LOGICAL_BITS];
    int solution[LOGICAL_BITS];
} Solver;

static double monotonic_seconds(void) {
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) {
        perror("clock_gettime");
        exit(2);
    }
    return (double)value.tv_sec + (double)value.tv_nsec / 1000000000.0;
}

static int bitset_nonzero(const uint64_t *value, int words) {
    for (int word = 0; word < words; ++word) {
        if (value[word] != 0) {
            return 1;
        }
    }
    return 0;
}

static uint64_t intersection_count(
    const uint64_t *left, const uint64_t *right, int words
) {
    uint64_t result = 0;
    for (int word = 0; word < words; ++word) {
        result += (uint64_t)__builtin_popcountll(left[word] & right[word]);
    }
    return result;
}

static int channel_used(const uint64_t used[4], int channel) {
    return (int)((used[channel / 64] >> (channel % 64)) & UINT64_C(1));
}

static void set_channel(uint64_t used[4], int channel) {
    used[channel / 64] |= UINT64_C(1) << (channel % 64);
}

static int compare_ranked(const void *left_value, const void *right_value) {
    const Ranked *left = left_value;
    const Ranked *right = right_value;
    if (left->score < right->score) {
        return -1;
    }
    if (left->score > right->score) {
        return 1;
    }
    return (int)left->literal - (int)right->literal;
}

static int build_domains(
    Solver *solver,
    uint16_t unassigned,
    const uint64_t used[4],
    const uint64_t masks[MAX_ROWS][MAX_WORDS],
    Domain domains[LOGICAL_BITS],
    int *domain_count
) {
    int produced = 0;
    for (int logical_bit = 0; logical_bit < LOGICAL_BITS; ++logical_bit) {
        if (((unassigned >> logical_bit) & 1U) == 0) {
            continue;
        }
        uint64_t forced_zero = 0;
        uint64_t forced_one = 0;
        uint64_t ambiguity = 0;
        for (int row = 0; row < solver->row_count; ++row) {
            uint64_t zero_count = intersection_count(
                masks[row], solver->allowed_by_bit[logical_bit][0],
                solver->word_count
            );
            uint64_t one_count = intersection_count(
                masks[row], solver->allowed_by_bit[logical_bit][1],
                solver->word_count
            );
            if (zero_count == 0 && one_count == 0) {
                fprintf(stderr, "empty row domain escaped pruning\n");
                exit(2);
            }
            if (zero_count == 0) {
                forced_one |= UINT64_C(1) << row;
            } else if (one_count == 0) {
                forced_zero |= UINT64_C(1) << row;
            } else {
                ambiguity += zero_count < one_count ? zero_count : one_count;
            }
        }

        Domain *domain = &domains[produced];
        domain->logical_bit = logical_bit;
        domain->count = 0;
        domain->ambiguity = ambiguity;
        for (int literal = 0; literal < LITERALS; ++literal) {
            int channel = literal / 2;
            uint64_t pattern = solver->literal_patterns[literal];
            if (channel_used(used, channel)) {
                continue;
            }
            if ((pattern & forced_zero) != 0) {
                continue;
            }
            if ((pattern & forced_one) != forced_one) {
                continue;
            }
            domain->literals[domain->count++] = (uint16_t)literal;
        }
        if (domain->count == 0) {
            return 0;
        }
        ++produced;
    }
    *domain_count = produced;
    return 1;
}

static int search(
    Solver *solver,
    uint16_t unassigned,
    const uint64_t used[4],
    const uint64_t masks[MAX_ROWS][MAX_WORDS]
) {
    ++solver->nodes;
    int depth = LOGICAL_BITS - __builtin_popcount((unsigned)unassigned);
    if (depth > solver->maximum_depth) {
        solver->maximum_depth = depth;
    }
    if ((solver->nodes & UINT64_C(0x3fff)) == 0
        && monotonic_seconds() >= solver->deadline) {
        solver->timed_out = 1;
        return 0;
    }
    if (unassigned == 0) {
        memcpy(solver->solution, solver->assignment, sizeof(solver->solution));
        return 1;
    }

    Domain domains[LOGICAL_BITS];
    int domain_count = 0;
    if (!build_domains(
            solver, unassigned, used, masks, domains, &domain_count)) {
        ++solver->dead_ends;
        ++solver->domain_failures;
        return 0;
    }

    int chosen = 0;
    for (int index = 1; index < domain_count; ++index) {
        const Domain *candidate = &domains[index];
        const Domain *incumbent = &domains[chosen];
        if (candidate->count < incumbent->count
            || (candidate->count == incumbent->count
                && candidate->ambiguity < incumbent->ambiguity)
            || (candidate->count == incumbent->count
                && candidate->ambiguity == incumbent->ambiguity
                && candidate->logical_bit < incumbent->logical_bit)) {
            chosen = index;
        }
    }
    Domain *domain = &domains[chosen];
    Ranked ranked[LITERALS];
    for (int index = 0; index < domain->count; ++index) {
        int literal = domain->literals[index];
        uint64_t pattern = solver->literal_patterns[literal];
        uint64_t score = 0;
        for (int row = 0; row < solver->row_count; ++row) {
            int value = (int)((pattern >> row) & UINT64_C(1));
            score += intersection_count(
                masks[row],
                solver->allowed_by_bit[domain->logical_bit][value],
                solver->word_count
            );
        }
        ranked[index].score = score;
        ranked[index].literal = (uint16_t)literal;
    }
    qsort(
        ranked, (size_t)domain->count, sizeof(ranked[0]), compare_ranked
    );

    uint16_t next_unassigned = (uint16_t)(
        unassigned & (uint16_t)~(UINT16_C(1) << domain->logical_bit)
    );
    for (int choice = 0; choice < domain->count; ++choice) {
        int literal = ranked[choice].literal;
        uint64_t pattern = solver->literal_patterns[literal];
        uint64_t child[MAX_ROWS][MAX_WORDS];
        memset(child, 0, sizeof(child));
        for (int row = 0; row < solver->row_count; ++row) {
            int value = (int)((pattern >> row) & UINT64_C(1));
            for (int word = 0; word < solver->word_count; ++word) {
                child[row][word] = masks[row][word]
                    & solver->allowed_by_bit[domain->logical_bit][value][word];
            }
            if (!bitset_nonzero(child[row], solver->word_count)) {
                fprintf(stderr, "ranked literal emptied a row domain\n");
                exit(2);
            }
        }
        uint64_t child_used[4];
        memcpy(child_used, used, sizeof(child_used));
        set_channel(child_used, literal / 2);
        solver->assignment[domain->logical_bit] = literal;
        if (search(solver, next_unassigned, child_used, child)) {
            return 1;
        }
        if (solver->timed_out) {
            return 0;
        }
        solver->assignment[domain->logical_bit] = -1;
    }
    ++solver->dead_ends;
    return 0;
}

static void load_instance(Solver *solver, const char *path) {
    FILE *input = fopen(path, "r");
    if (input == NULL) {
        fprintf(stderr, "cannot open %s: %s\n", path, strerror(errno));
        exit(2);
    }
    char magic[64];
    if (fscanf(input, "%63s", magic) != 1
        || strcmp(magic, "FSINCOS_H1546_CSP_V1") != 0) {
        fprintf(stderr, "bad instance magic\n");
        exit(2);
    }
    if (fscanf(input, "%d %d", &solver->row_count, &solver->allowed_count) != 2
        || solver->row_count < 0 || solver->row_count > MAX_ROWS
        || solver->allowed_count < 1 || solver->allowed_count > MAX_ALLOWED) {
        fprintf(stderr, "bad instance dimensions\n");
        exit(2);
    }
    for (int row = 0; row < solver->row_count; ++row) {
        char label[64];
        if (fscanf(input, "%63s", label) != 1) {
            fprintf(stderr, "missing row label\n");
            exit(2);
        }
        for (int dword = 0; dword < DWORDS; ++dword) {
            if (fscanf(input, " %" SCNx32, &solver->rows[row][dword]) != 1) {
                fprintf(stderr, "bad row payload\n");
                exit(2);
            }
        }
    }
    for (int index = 0; index < solver->allowed_count; ++index) {
        unsigned value;
        if (fscanf(input, "%x", &value) != 1 || value >= (1U << LOGICAL_BITS)) {
            fprintf(stderr, "bad allowed opcode\n");
            exit(2);
        }
        solver->allowed[index] = (uint16_t)value;
    }
    if (fclose(input) != 0) {
        perror("fclose");
        exit(2);
    }
}

static void initialize(Solver *solver) {
    solver->word_count = (solver->allowed_count + 63) / 64;
    for (int index = 0; index < solver->allowed_count; ++index) {
        int word = index / 64;
        int offset = index % 64;
        for (int bit = 0; bit < LOGICAL_BITS; ++bit) {
            int value = (solver->allowed[index] >> bit) & 1;
            solver->allowed_by_bit[bit][value][word]
                |= UINT64_C(1) << offset;
        }
    }
    uint64_t row_mask = solver->row_count == 64
        ? UINT64_MAX
        : ((UINT64_C(1) << solver->row_count) - 1);
    for (int dword = 0; dword < DWORDS; ++dword) {
        for (int bit = 0; bit < BITS_PER_DWORD; ++bit) {
            int channel = dword * BITS_PER_DWORD + bit;
            uint64_t pattern = 0;
            for (int row = 0; row < solver->row_count; ++row) {
                pattern |= (uint64_t)((solver->rows[row][dword] >> bit) & 1U)
                    << row;
            }
            solver->literal_patterns[2 * channel] = pattern;
            solver->literal_patterns[2 * channel + 1] = pattern ^ row_mask;
        }
    }
    for (int bit = 0; bit < LOGICAL_BITS; ++bit) {
        solver->assignment[bit] = -1;
        solver->solution[bit] = -1;
    }
}

static int validate_solution(const Solver *solver) {
    uint64_t used[4] = {0, 0, 0, 0};
    for (int bit = 0; bit < LOGICAL_BITS; ++bit) {
        int literal = solver->solution[bit];
        if (literal < 0 || literal >= LITERALS
            || channel_used(used, literal / 2)) {
            return 0;
        }
        set_channel(used, literal / 2);
    }
    for (int row = 0; row < solver->row_count; ++row) {
        unsigned opcode = 0;
        for (int bit = 0; bit < LOGICAL_BITS; ++bit) {
            opcode |= (unsigned)(
                (solver->literal_patterns[solver->solution[bit]] >> row) & 1
            ) << bit;
        }
        int found = 0;
        for (int index = 0; index < solver->allowed_count; ++index) {
            if (solver->allowed[index] == opcode) {
                found = 1;
                break;
            }
        }
        if (!found) {
            return 0;
        }
    }
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s INSTANCE TIMEOUT_SECONDS\n", argv[0]);
        return 2;
    }
    char *end = NULL;
    errno = 0;
    double timeout = strtod(argv[2], &end);
    if (errno != 0 || end == argv[2] || *end != '\0' || timeout <= 0) {
        fprintf(stderr, "bad timeout\n");
        return 2;
    }
    Solver *solver = calloc(1, sizeof(*solver));
    if (solver == NULL) {
        perror("calloc");
        return 2;
    }
    load_instance(solver, argv[1]);
    initialize(solver);

    uint64_t masks[MAX_ROWS][MAX_WORDS];
    memset(masks, 0, sizeof(masks));
    for (int row = 0; row < solver->row_count; ++row) {
        for (int index = 0; index < solver->allowed_count; ++index) {
            masks[row][index / 64] |= UINT64_C(1) << (index % 64);
        }
    }
    uint64_t used[4] = {0, 0, 0, 0};
    double started = monotonic_seconds();
    solver->deadline = started + timeout;
    int found = search(solver, UINT16_C(0x0fff), used, masks);
    double elapsed = monotonic_seconds() - started;
    const char *status = found ? "SAT" : (solver->timed_out ? "UNKNOWN" : "UNSAT");
    if (found && !validate_solution(solver)) {
        fprintf(stderr, "solution replay failed\n");
        free(solver);
        return 2;
    }

    printf("{\"status\":\"%s\",\"elapsed_seconds\":%.9f,", status, elapsed);
    printf("\"nodes\":%" PRIu64 ",\"dead_ends\":%" PRIu64 ",",
           solver->nodes, solver->dead_ends);
    printf("\"domain_failures\":%" PRIu64 ",\"maximum_depth\":%d,",
           solver->domain_failures, solver->maximum_depth);
    printf("\"hall_pruning\":false");
    if (found) {
        printf(",\"solution_literals\":[");
        for (int bit = 0; bit < LOGICAL_BITS; ++bit) {
            printf("%s%d", bit == 0 ? "" : ",", solver->solution[bit]);
        }
        printf("]");
    }
    printf("}\n");
    free(solver);
    return 0;
}

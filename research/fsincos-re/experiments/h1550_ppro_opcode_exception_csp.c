/* Exact bounded-row-exception extension of H1546.
 *
 * A row remains active while its recognized-opcode domain is nonempty.  If an
 * assignment empties that domain, the row is necessarily unrecognized for all
 * completions of that mapping and is deterministically charged to the bounded
 * exception budget.  No choice to discard a still-compatible row is needed:
 * every completed mapping is represented, and its charged rows are exactly
 * those whose final opcodes are outside the supplied recognized set.
 */

#define main h1546_original_main
#include "h1546_ppro_opcode_csp.c"
#undef main

typedef struct {
    Solver base;
    int maximum_exceptions;
    uint64_t solution_active_rows;
    int use_preferred_literals;
    int preferred_literals[LOGICAL_BITS];
} ExceptionSolver;

typedef struct {
    uint64_t score;
    uint16_t literal;
    uint8_t new_exceptions;
} ExceptionRanked;

static int compare_exception_ranked(
    const void *left_value, const void *right_value
) {
    const ExceptionRanked *left = left_value;
    const ExceptionRanked *right = right_value;
    if (left->new_exceptions > right->new_exceptions) {
        return -1;
    }
    if (left->new_exceptions < right->new_exceptions) {
        return 1;
    }
    if (left->score < right->score) {
        return -1;
    }
    if (left->score > right->score) {
        return 1;
    }
    return (int)left->literal - (int)right->literal;
}

static int build_exception_domains(
    ExceptionSolver *solver,
    uint16_t unassigned,
    const uint64_t used[4],
    const uint64_t masks[MAX_ROWS][MAX_WORDS],
    uint64_t active_rows,
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
        for (int row = 0; row < solver->base.row_count; ++row) {
            if (((active_rows >> row) & UINT64_C(1)) == 0) {
                continue;
            }
            uint64_t zero_count = intersection_count(
                masks[row], solver->base.allowed_by_bit[logical_bit][0],
                solver->base.word_count
            );
            uint64_t one_count = intersection_count(
                masks[row], solver->base.allowed_by_bit[logical_bit][1],
                solver->base.word_count
            );
            if (zero_count == 0 && one_count == 0) {
                fprintf(stderr, "active row has empty opcode domain\n");
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
        int current_exceptions = solver->base.row_count
            - __builtin_popcountll(active_rows);
        for (int literal = 0; literal < LITERALS; ++literal) {
            int channel = literal / 2;
            uint64_t pattern = solver->base.literal_patterns[literal];
            if (channel_used(used, channel)) {
                continue;
            }
            uint64_t forced_conflicts = (pattern & forced_zero)
                | ((~pattern) & forced_one);
            if (current_exceptions + __builtin_popcountll(forced_conflicts)
                > solver->maximum_exceptions) {
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

static int exception_search(
    ExceptionSolver *solver,
    uint16_t unassigned,
    const uint64_t used[4],
    const uint64_t masks[MAX_ROWS][MAX_WORDS],
    uint64_t active_rows
) {
    Solver *base = &solver->base;
    ++base->nodes;
    int depth = LOGICAL_BITS - __builtin_popcount((unsigned)unassigned);
    if (depth > base->maximum_depth) {
        base->maximum_depth = depth;
    }
    if ((base->nodes & UINT64_C(0x3fff)) == 0
        && monotonic_seconds() >= base->deadline) {
        base->timed_out = 1;
        return 0;
    }
    if (unassigned == 0) {
        memcpy(base->solution, base->assignment, sizeof(base->solution));
        solver->solution_active_rows = active_rows;
        return 1;
    }

    Domain domains[LOGICAL_BITS];
    int domain_count = 0;
    if (!build_exception_domains(
            solver, unassigned, used, masks, active_rows,
            domains, &domain_count)) {
        ++base->dead_ends;
        ++base->domain_failures;
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
    ExceptionRanked ranked[LITERALS];
    for (int index = 0; index < domain->count; ++index) {
        int literal = domain->literals[index];
        uint64_t pattern = base->literal_patterns[literal];
        uint64_t score = 0;
        int new_exceptions = 0;
        for (int row = 0; row < base->row_count; ++row) {
            if (((active_rows >> row) & UINT64_C(1)) == 0) {
                continue;
            }
            int value = (int)((pattern >> row) & UINT64_C(1));
            uint64_t remaining = intersection_count(
                masks[row], base->allowed_by_bit[domain->logical_bit][value],
                base->word_count
            );
            score += remaining;
            new_exceptions += remaining == 0;
        }
        ranked[index].score = score;
        ranked[index].literal = (uint16_t)literal;
        ranked[index].new_exceptions = (uint8_t)new_exceptions;
    }
    qsort(
        ranked,
        (size_t)domain->count,
        sizeof(ranked[0]),
        compare_exception_ranked
    );
    if (solver->use_preferred_literals) {
        int preferred = solver->preferred_literals[domain->logical_bit];
        for (int index = 0; index < domain->count; ++index) {
            if (ranked[index].literal == preferred) {
                ExceptionRanked swap = ranked[0];
                ranked[0] = ranked[index];
                ranked[index] = swap;
                break;
            }
        }
    }

    uint16_t next_unassigned = (uint16_t)(
        unassigned & (uint16_t)~(UINT16_C(1) << domain->logical_bit)
    );
    for (int choice = 0; choice < domain->count; ++choice) {
        int literal = ranked[choice].literal;
        uint64_t pattern = base->literal_patterns[literal];
        uint64_t child[MAX_ROWS][MAX_WORDS];
        memcpy(child, masks, sizeof(child));
        uint64_t child_active = active_rows;
        for (int row = 0; row < base->row_count; ++row) {
            if (((active_rows >> row) & UINT64_C(1)) == 0) {
                continue;
            }
            int value = (int)((pattern >> row) & UINT64_C(1));
            for (int word = 0; word < base->word_count; ++word) {
                child[row][word] = masks[row][word]
                    & base->allowed_by_bit[domain->logical_bit][value][word];
            }
            if (!bitset_nonzero(child[row], base->word_count)) {
                child_active &= ~(UINT64_C(1) << row);
            }
        }
        int exception_count = base->row_count
            - __builtin_popcountll(child_active);
        if (exception_count > solver->maximum_exceptions) {
            continue;
        }
        uint64_t child_used[4];
        memcpy(child_used, used, sizeof(child_used));
        set_channel(child_used, literal / 2);
        base->assignment[domain->logical_bit] = literal;
        if (exception_search(
                solver, next_unassigned, child_used, child, child_active)) {
            return 1;
        }
        if (base->timed_out) {
            return 0;
        }
        base->assignment[domain->logical_bit] = -1;
    }
    ++base->dead_ends;
    return 0;
}

static int validate_exception_solution(const ExceptionSolver *solver) {
    const Solver *base = &solver->base;
    uint64_t used[4] = {0, 0, 0, 0};
    int unrecognized = 0;
    for (int bit = 0; bit < LOGICAL_BITS; ++bit) {
        int literal = base->solution[bit];
        if (literal < 0 || literal >= LITERALS
            || channel_used(used, literal / 2)) {
            return 0;
        }
        set_channel(used, literal / 2);
    }
    for (int row = 0; row < base->row_count; ++row) {
        unsigned opcode = 0;
        for (int bit = 0; bit < LOGICAL_BITS; ++bit) {
            opcode |= (unsigned)(
                (base->literal_patterns[base->solution[bit]] >> row) & 1
            ) << bit;
        }
        int recognized = 0;
        for (int index = 0; index < base->allowed_count; ++index) {
            if (base->allowed[index] == opcode) {
                recognized = 1;
                break;
            }
        }
        int active = (int)(
            (solver->solution_active_rows >> row) & UINT64_C(1)
        );
        if (recognized != active) {
            return 0;
        }
        unrecognized += !recognized;
    }
    return unrecognized <= solver->maximum_exceptions;
}

int main(int argc, char **argv) {
    if (argc != 4 && argc != 5) {
        fprintf(
            stderr,
            "usage: %s INSTANCE TIMEOUT_SECONDS MAX_EXCEPTIONS "
            "[PREFERRED_LITERAL_CSV]\n",
            argv[0]
        );
        return 2;
    }
    char *timeout_end = NULL;
    char *exception_end = NULL;
    errno = 0;
    double timeout = strtod(argv[2], &timeout_end);
    long maximum_exceptions = strtol(argv[3], &exception_end, 10);
    if (errno != 0 || timeout_end == argv[2] || *timeout_end != '\0'
        || timeout <= 0 || exception_end == argv[3] || *exception_end != '\0'
        || maximum_exceptions < 0 || maximum_exceptions > MAX_ROWS) {
        fprintf(stderr, "bad timeout or exception bound\n");
        return 2;
    }

    ExceptionSolver *solver = calloc(1, sizeof(*solver));
    if (solver == NULL) {
        perror("calloc");
        return 2;
    }
    solver->maximum_exceptions = (int)maximum_exceptions;
    if (argc == 5) {
        const char *cursor = argv[4];
        solver->use_preferred_literals = 1;
        for (int bit = 0; bit < LOGICAL_BITS; ++bit) {
            char *literal_end = NULL;
            errno = 0;
            long literal = strtol(cursor, &literal_end, 10);
            if (errno != 0 || literal_end == cursor
                || literal < 0 || literal >= LITERALS
                || (bit < LOGICAL_BITS - 1 && *literal_end != ',')
                || (bit == LOGICAL_BITS - 1 && *literal_end != '\0')) {
                fprintf(stderr, "bad preferred literal list\n");
                free(solver);
                return 2;
            }
            solver->preferred_literals[bit] = (int)literal;
            cursor = literal_end + (bit < LOGICAL_BITS - 1);
        }
    }
    load_instance(&solver->base, argv[1]);
    initialize(&solver->base);

    uint64_t masks[MAX_ROWS][MAX_WORDS];
    memset(masks, 0, sizeof(masks));
    for (int row = 0; row < solver->base.row_count; ++row) {
        for (int index = 0; index < solver->base.allowed_count; ++index) {
            masks[row][index / 64] |= UINT64_C(1) << (index % 64);
        }
    }
    uint64_t active_rows = solver->base.row_count == 64
        ? UINT64_MAX
        : ((UINT64_C(1) << solver->base.row_count) - 1);
    uint64_t used[4] = {0, 0, 0, 0};
    double started = monotonic_seconds();
    solver->base.deadline = started + timeout;
    int found = exception_search(
        solver, UINT16_C(0x0fff), used, masks, active_rows
    );
    double elapsed = monotonic_seconds() - started;
    const char *status = found
        ? "SAT" : (solver->base.timed_out ? "UNKNOWN" : "UNSAT");
    if (found && !validate_exception_solution(solver)) {
        fprintf(stderr, "exception solution replay failed\n");
        free(solver);
        return 2;
    }

    printf("{\"status\":\"%s\",\"elapsed_seconds\":%.9f,", status, elapsed);
    printf("\"maximum_exceptions\":%d,", solver->maximum_exceptions);
    printf("\"nodes\":%" PRIu64 ",\"dead_ends\":%" PRIu64 ",",
           solver->base.nodes, solver->base.dead_ends);
    printf("\"domain_failures\":%" PRIu64 ",\"maximum_depth\":%d,",
           solver->base.domain_failures, solver->base.maximum_depth);
    printf(
        "\"hall_pruning\":false,\"preferred_literal_order\":%s",
        solver->use_preferred_literals ? "true" : "false"
    );
    if (found) {
        uint64_t full_rows = solver->base.row_count == 64
            ? UINT64_MAX
            : ((UINT64_C(1) << solver->base.row_count) - 1);
        uint64_t ignored = full_rows ^ solver->solution_active_rows;
        printf(",\"solution_literals\":[");
        for (int bit = 0; bit < LOGICAL_BITS; ++bit) {
            printf(
                "%s%d", bit == 0 ? "" : ",", solver->base.solution[bit]
            );
        }
        printf("],\"ignored_rows_hex\":\"%016" PRIx64 "\"", ignored);
        printf(",\"ignored_row_count\":%d", __builtin_popcountll(ignored));
    }
    printf("}\n");
    free(solver);
    return 0;
}

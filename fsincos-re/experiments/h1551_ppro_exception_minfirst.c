/* Minimum-new-exception value order for the exact H1550 CSP.
 *
 * H1550 deliberately ranks candidates that consume more exception rows first,
 * which is useful for finding its known K=4 witness.  This translation unit
 * keeps every domain and recursive branch unchanged but replaces qsort with a
 * deterministic order that ranks fewer newly forced exceptions first, then
 * the same remaining-opcode mass and literal index.  It changes search order
 * only: SAT/UNSAT/UNKNOWN retain H1550's exact semantics.
 */

#include <stddef.h>

static void h1551_qsort(
    void *base,
    size_t element_count,
    size_t element_size,
    int (*comparison)(const void *, const void *)
);

#define qsort h1551_qsort
#include "h1550_ppro_opcode_exception_csp.c"
#undef qsort

static int h1551_compare(const ExceptionRanked *left,
                         const ExceptionRanked *right) {
    if (left->new_exceptions < right->new_exceptions) {
        return -1;
    }
    if (left->new_exceptions > right->new_exceptions) {
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

static void h1551_qsort(
    void *base,
    size_t element_count,
    size_t element_size,
    int (*comparison)(const void *, const void *)
) {
    (void)comparison;
    if (element_size != sizeof(ExceptionRanked)) {
        fprintf(stderr, "unexpected H1551 sort element size\n");
        exit(2);
    }
    ExceptionRanked *values = base;
    for (size_t index = 1; index < element_count; ++index) {
        ExceptionRanked value = values[index];
        size_t insertion = index;
        while (insertion > 0
               && h1551_compare(&value, &values[insertion - 1]) < 0) {
            values[insertion] = values[insertion - 1];
            --insertion;
        }
        values[insertion] = value;
    }
}

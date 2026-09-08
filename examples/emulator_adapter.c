/* Caller-side writeback example; this is not a complete x87 instruction handler. */
#include "emulator_adapter.h"
example_apply_status
example_apply_masked(example_fpu *fpu, const x87t_result *result, uint16_t required_cc)
{
    if (!fpu || !result || fpu->depth < 1 || fpu->depth > 8)
        return EXAMPLE_BAD_STATE;
    if (result->completion == X87T_RANGE_RETURN) {
        if (result->destination != X87T_NO_WRITE || result->values != 0 ||
            !(result->cc_known & X87T_C2) || !(result->cc & X87T_C2))
            return EXAMPLE_BAD_STATE;
        /* The range return preserves every register and leaves other status
         * handling to the caller's established instruction contract. */
        fpu->status |= X87T_C2;
        return EXAMPLE_APPLIED;
    }
    if (result->exceptions_known != 0x3f || (result->cc_known & required_cc) != required_cc)
        return EXAMPLE_NEEDS_METADATA;
    if (!(result->values & X87T_PRIMARY))
        return EXAMPLE_BAD_STATE;
    if (result->destination == X87T_REPLACE_ST0_PUSH &&
        (fpu->depth == 8 || !(result->values & X87T_PUSHED)))
        return EXAMPLE_BAD_STATE;
    if (result->destination == X87T_REPLACE_ST1_POP && fpu->depth < 2)
        return EXAMPLE_BAD_STATE;
    if (result->destination != X87T_REPLACE_ST0 && result->destination != X87T_REPLACE_ST0_PUSH &&
        result->destination != X87T_REPLACE_ST1_POP)
        return EXAMPLE_BAD_STATE;
    if (result->destination == X87T_REPLACE_ST0)
        fpu->st[0] = result->primary;
    else if (result->destination == X87T_REPLACE_ST0_PUSH) {
        for (unsigned i = fpu->depth; i > 1; --i)
            fpu->st[i] = fpu->st[i - 1];
        fpu->st[1] = result->primary;
        fpu->st[0] = result->pushed;
        ++fpu->depth;
    } else {
        fpu->st[0] = result->primary;
        for (unsigned i = 1; i + 1 < fpu->depth; ++i)
            fpu->st[i] = fpu->st[i + 1];
        --fpu->depth;
    }
    fpu->status =
        (uint16_t)((fpu->status & ~required_cc) | (result->cc & required_cc) | result->exceptions);
    return EXAMPLE_APPLIED;
}

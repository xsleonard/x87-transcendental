/* Constants are initialized once; no evaluation state lives in the context. */
#include "internal/binary.h"
#include <stdlib.h>
#include <string.h>

x87t_context *x87t_create(void)
{
    x87t_context *context = malloc(sizeof(*context));
    if (context) {
        x87t_internal_atan_constants_init(&context->atan);
        x87t_internal_log_constants_init(&context->log);
    }
    return context;
}

void x87t_destroy(x87t_context *context)
{
    if (!context)
        return;
    free(context);
}

const char *x87t_version(void)
{
    return "0.2.0";
}
const char *x87t_profile(void)
{
    return "skylake-emulation-preview";
}

x87t_error
x87t_internal_validate_call(const x87t_context *context, const x87t_control *control, x87t_result *result)
{
    if (!context || !control || !result || control->rounding < X87T_RN ||
        control->rounding > X87T_RZ)
        return X87T_BAD_ARGUMENT;
    if (control->precision_bits != 24 && control->precision_bits != 53 &&
        control->precision_bits != 64)
        return X87T_UNSUPPORTED_CONTROL;
    if (control->exception_masks & ~0x3f)
        return X87T_UNSUPPORTED_CONTROL;
    return X87T_OK;
}

void x87t_internal_result_begin(x87t_result *result, x87t_destination destination)
{
    memset(result, 0, sizeof(*result));
    result->values = X87T_PRIMARY;
    result->exceptions_known = 0x3f;
    result->completion = X87T_COMPLETE;
    result->destination = destination;
}

void x87t_internal_result_range(x87t_result *result)
{
    x87t_internal_result_begin(result, X87T_NO_WRITE);
    result->values = 0;
    result->cc = X87T_C2;
    result->cc_known = X87T_C2;
    result->completion = X87T_RANGE_RETURN;
}

/* Early operand exceptions suppress all numerical writes and later flags.
 * Register-destination overflow/underflow and precision complete their writes;
 * their numerical entry points supply the appropriate rounded endpoint. */
/* Choose the first new unmasked exception in IE, DE, ZE, OE, UE, PE order.
 * IE, DE or ZE stops the instruction before it writes a result: keep only
 * the selected flag, clear C1, and cancel the register update, push or pop.
 * OE, UE or PE allows the write, keeping the calculated flags and C1.
 *
 * This function does no arithmetic. For unmasked OE or UE, the numerical
 * routine must already have scaled and rounded the result. The caller
 * updates registers and handles existing flags, stack state and exception
 * delivery after any permitted write. */
void x87t_internal_result_finish(x87t_result *result, const x87t_control *control)
{
    unsigned unmasked = result->exceptions & ~control->exception_masks & 0x3f;
    if (!unmasked)
        return;
    unsigned first = unmasked & (0u - unmasked);
    result->first_unmasked = (uint8_t)first;
    if (first & (X87T_IE | X87T_DE | X87T_ZE)) {
        result->exceptions = (uint8_t)first;
        result->primary = result->pushed = (x87t_raw80){0, 0};
        result->values = 0;
        result->destination = X87T_NO_WRITE;
        result->completion = X87T_UNMASKED_NO_WRITE;
        result->cc = 0;
    } else {
        result->completion = X87T_UNMASKED_WRITE;
    }
}

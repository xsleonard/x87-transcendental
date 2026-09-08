/* Constants are initialized once; no evaluation state lives in the context. */
#include "internal/binary.h"
#include <stdlib.h>
#include <string.h>

x87t_context *x87t_create(void)
{
    x87t_context *context = malloc(sizeof(*context));
    if (context) {
        atan_constants_init(&context->atan);
        log_constants_init(&context->log);
    }
    return context;
}

void x87t_destroy(x87t_context *context)
{
    if (!context)
        return;
    atan_constants_clear(&context->atan);
    log_constants_clear(&context->log);
    free(context);
}

const char *x87t_version(void)
{
    return "0.1.0";
}
const char *x87t_profile(void)
{
    return "skylake-numerical-preview";
}

x87t_error
validate_call(const x87t_context *context, const x87t_control *control, x87t_result *result)
{
    if (!context || !control || !result || control->rounding < X87T_RN ||
        control->rounding > X87T_RZ)
        return X87T_BAD_ARGUMENT;
    if (control->precision_bits != 24 && control->precision_bits != 53 &&
        control->precision_bits != 64)
        return X87T_UNSUPPORTED_CONTROL;
    if (control->exception_masks != 0x3f)
        return X87T_UNSUPPORTED_CONTROL;
    return X87T_OK;
}

void result_begin(x87t_result *result, x87t_destination destination)
{
    memset(result, 0, sizeof(*result));
    result->values = X87T_PRIMARY;
    result->completion = X87T_COMPLETE;
    result->destination = destination;
}

void result_range(x87t_result *result)
{
    result_begin(result, X87T_NO_WRITE);
    result->values = 0;
    result->cc = X87T_C2;
    result->cc_known = X87T_C2;
    result->completion = X87T_RANGE_RETURN;
}

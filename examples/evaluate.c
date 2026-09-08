/* Minimal consumer: raw80 +0.5, rounded toward nearest, all exceptions masked. */
#include <x87trans/x87trans.h>
#include <inttypes.h>
#include <stdio.h>
int main(void)
{
    x87t_context *context = x87t_create();
    if (!context)
        return 1;
    x87t_control control = X87T_CONTROL_INIT;
    x87t_raw80 half = {0x3ffe, UINT64_C(0x8000000000000000)};
    x87t_result result;
    x87t_error error = x87t_fsincos(context, half, &control, &result);
    if (!error && result.completion == X87T_COMPLETE) {
        printf("sine=%04x:%016" PRIx64 " cosine=%04x:%016" PRIx64 "\n",
               result.primary.se,
               result.primary.sig,
               result.pushed.se,
               result.pushed.sig);
        printf("known condition bits=%04x, known exception bits=%02x\n",
               result.cc_known,
               result.exceptions_known);
    }
    x87t_destroy(context);
    return error != X87T_OK;
}

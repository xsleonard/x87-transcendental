/* Minimal client for the existing FPATAN numerical library.
 * Build from the repository root using the programmer guide.
 * The input order is y=ST(1), x=ST(0); these literal encodings are both +1.
 */
#include <inttypes.h>
#include <stdio.h>
#include "fpatan_library.h"

int main(void)
{
    x87_fpatan *context = x87_fpatan_create();
    if (context == NULL) {
        fputs("Could not create the FPATAN context.\n", stderr);
        return 1;
    }

    const x87_fpatan_value one = {0x3fff, UINT64_C(0x8000000000000000)};
    x87_fpatan_result result;
    x87_fpatan_error error = x87_fpatan_evaluate(
        context, one, one, X87_FPATAN_RN, 64, &result);
    x87_fpatan_destroy(context);
    if (error != X87_FPATAN_OK) {
        fputs("FPATAN rejected the API arguments.\n", stderr);
        return 1;
    }

    printf("%04x %016" PRIx64 " C1=%u exceptions=%02x\n",
           (unsigned)result.value.se, result.value.sig,
           (unsigned)result.c1, (unsigned)result.exceptions);
    return 0;
}

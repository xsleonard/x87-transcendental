#ifndef X87TRANS_EXAMPLE_ADAPTER_H
#define X87TRANS_EXAMPLE_ADAPTER_H
#include <x87trans/x87trans.h>
/* Logical ST order for a small integration fixture. A real emulator retains
 * its physical register file, TOP/tag representation and exception machinery. */
typedef struct {
    x87t_raw80 st[8];
    unsigned depth;
    uint16_t status;
} example_fpu;
typedef enum { EXAMPLE_APPLIED, EXAMPLE_NEEDS_METADATA, EXAMPLE_BAD_STATE } example_apply_status;
/* Caller has already checked pending exceptions and instruction-specific
 * stack priority. This fixture applies only all-masked numerical completion.
 * Required condition bits come from the caller's instruction contract.
 */
example_apply_status example_apply_masked(example_fpu *, const x87t_result *, uint16_t required_cc);
#endif

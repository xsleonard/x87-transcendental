/* Portable Skylake logarithm numerical model. No native x87 execution. */
#ifndef X87_LOG_LIBRARY_H
#define X87_LOG_LIBRARY_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef struct x87_log x87_log;
typedef struct {
    uint16_t se;
    uint64_t sig;
} x87_log_value;
typedef enum { X87_FYL2X = 0, X87_FYL2XP1 = 1 } x87_log_instruction;
typedef enum { X87_LOG_RN = 0, X87_LOG_RD = 1, X87_LOG_RU = 2, X87_LOG_RZ = 3 } x87_log_round;
typedef struct {
    x87_log_value value;
    uint8_t c1;
    uint8_t exceptions; /* IE, DE, ZE, OE, UE, PE in x87 bit positions 0..5. */
} x87_log_result;
typedef enum { X87_LOG_OK = 0, X87_LOG_BAD_ARGUMENT = 1, X87_LOG_OUTSIDE_SCOPE = 2 } x87_log_error;

/* Create once and reuse; temporaries are private to each evaluation.
 * Destroy after all evaluations finish. Destroy(NULL) is valid. Allocation
 * failure returns NULL, subject to GMP's allocator behavior.
 */
x87_log *x87_log_create(void);
void x87_log_destroy(x87_log *context);

/* y=ST(1), x=ST(0); the hardware replaces ST(1) and pops ST(0).
 * Numerical contract: masked exceptions, valid two-deep stack, clear initial
 * exception latches, raw80 loads. PC=24/53/64 is accepted and checked.
 * Unsupported raw80 encodings are hardware operands, returning indefinite
 * NaN and IE, rather than API errors. NaN payloads/signs are preserved by the
 * modeled selection rule. FYL2XP1's finite domain is |x|<=1-sqrt(1/2);
 * other finite arguments and infinite x return OUTSIDE_SCOPE. FYL2X includes
 * its defined zero, negative, infinity and NaN exception behavior.
 * API errors leave *result unchanged. No unmasked trap delivery, FPU pointer
 * image or undefined condition bits are modeled.
 */
x87_log_error x87_log_evaluate(const x87_log *context,
                               x87_log_instruction instruction,
                               x87_log_value y,
                               x87_log_value x,
                               x87_log_round rounding,
                               unsigned precision_control,
                               x87_log_result *result);

#ifdef __cplusplus
}
#endif
#endif

/* Numerical FPATAN reconstruction interface. See README/HANDOFF for status.
 * The implementation uses one fixed algorithm, with no experimental flags.
 */
#ifndef X87_FPATAN_LIBRARY_H
#define X87_FPATAN_LIBRARY_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef struct x87_fpatan x87_fpatan;
typedef struct {
    uint16_t se;
    uint64_t sig;
} x87_fpatan_value;
typedef enum {
    X87_FPATAN_RN = 0,
    X87_FPATAN_RD = 1,
    X87_FPATAN_RU = 2,
    X87_FPATAN_RZ = 3
} x87_fpatan_round;
typedef struct {
    x87_fpatan_value value;
    uint8_t c1;
    uint8_t exceptions; /* IE, DE, ZE, OE, UE, PE in x87 bit positions 0..5. */
} x87_fpatan_result;
typedef enum { X87_FPATAN_OK = 0, X87_FPATAN_BAD_ARGUMENT = 1 } x87_fpatan_error;

/* Create once and reuse. Destroy only after evaluations finish. No mutable
 * evaluation state is retained in the initialized context. NULL is accepted
 * by destroy. Allocation failure returns NULL (subject to GMP's allocator).
 */
x87_fpatan *x87_fpatan_create(void);
void x87_fpatan_destroy(x87_fpatan *context);

/* y=ST(1), x=ST(0). Raw80 includes zeros, denormals, NaNs and unsupported
 * encodings. Unsupported encodings are hardware operands, not API errors:
 * they return the indefinite QNaN and IE. The supported PC values are 24,
 * 53 and 64; they are checked even though the recovered result is PC-invariant.
 * Exception flags assume a valid two-deep stack, masked exceptions and clear
 * initial latches. Bad arguments leave *result unchanged. No pointer-register
 * image, unmasked trap delivery or undefined condition bits are modeled.
 */
x87_fpatan_error x87_fpatan_evaluate(const x87_fpatan *context,
                                     x87_fpatan_value y,
                                     x87_fpatan_value x,
                                     x87_fpatan_round rounding,
                                     unsigned precision_control,
                                     x87_fpatan_result *result);

#ifdef __cplusplus
}
#endif
#endif

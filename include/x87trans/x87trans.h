/* Reconstructed Skylake x87 transcendental functions.
 * See docs/api.md for the numerical preview's supported status fields.
 */
#ifndef X87TRANS_H
#define X87TRANS_H

#include <stdint.h>

#if defined(_WIN32) && defined(X87TRANS_SHARED)
#if defined(X87TRANS_BUILDING)
#define X87T_API __declspec(dllexport)
#else
#define X87T_API __declspec(dllimport)
#endif
#elif defined(__GNUC__)
#define X87T_API __attribute__((visibility("default")))
#else
#define X87T_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct x87t_context x87t_context;

/* Value fields, not a packed memory image. Preserve original operand bits. */
typedef struct {
    uint16_t se;
    uint64_t sig;
} x87t_raw80;
typedef enum { X87T_RN, X87T_RD, X87T_RU, X87T_RZ } x87t_round;
typedef struct {
    x87t_round rounding;
    unsigned precision_bits; /* 24, 53 or 64 */
    uint8_t exception_masks; /* IM..PM, one means masked */
} x87t_control;

#define X87T_CONTROL_INIT {X87T_RN, 64, 0x3f}
enum { X87T_IE = 1, X87T_DE = 2, X87T_ZE = 4, X87T_OE = 8, X87T_UE = 16, X87T_PE = 32 };
enum { X87T_C1 = 0x0200, X87T_C2 = 0x0400 };
enum { X87T_PRIMARY = 1, X87T_PUSHED = 2 };
typedef enum { X87T_COMPLETE, X87T_RANGE_RETURN } x87t_completion;
typedef enum {
    X87T_NO_WRITE,
    X87T_REPLACE_ST0,
    X87T_REPLACE_ST0_PUSH,
    X87T_REPLACE_ST1_POP
} x87t_destination;

typedef struct {
    x87t_raw80 primary; /* Sine, tangent, or single result */
    x87t_raw80 pushed;  /* Cosine or the modeled FPTAN push */
    uint8_t values;     /* Valid numerical fields */
    uint8_t exceptions;
    uint8_t exceptions_known; /* Implemented flags; unknown is not zero */
    uint16_t cc;
    uint16_t cc_known; /* Implemented bits, not an ISA defined mask */
    x87t_completion completion;
    x87t_destination destination;
} x87t_result;

typedef enum {
    X87T_OK,
    X87T_BAD_ARGUMENT,
    X87T_UNSUPPORTED_CONTROL,
    X87T_OUTSIDE_SCOPE
} x87t_error;

/* Initialize once. Constants are immutable; scratch is private to each call.
 * Destroy after all evaluations finish. destroy(NULL) is valid. Allocation
 * failure returns NULL subject to GMP's allocator/failure behavior.
 */
X87T_API x87t_context *x87t_create(void);
X87T_API void x87t_destroy(x87t_context *context);
X87T_API const char *x87t_version(void);
X87T_API const char *x87t_profile(void);
X87T_API x87t_raw80 x87t_load_le(const uint8_t bytes[10]);
X87T_API void x87t_store_le(uint8_t bytes[10], x87t_raw80 value);

/* All calls require a context, controls and output. Errors leave output
 * unchanged. Only all-masked execution is supported in this preview.
 * The caller checks stack and pending exceptions before calling, and applies
 * results only after handling any metadata the library does not yet provide.
 */
X87T_API x87t_error x87t_fsin(const x87t_context *,
                              x87t_raw80 x,
                              const x87t_control *,
                              x87t_result *);
X87T_API x87t_error x87t_fcos(const x87t_context *,
                              x87t_raw80 x,
                              const x87t_control *,
                              x87t_result *);
X87T_API x87t_error x87t_fsincos(const x87t_context *,
                                 x87t_raw80 x,
                                 const x87t_control *,
                                 x87t_result *);
X87T_API x87t_error x87t_fptan(const x87t_context *,
                               x87t_raw80 x,
                               const x87t_control *,
                               x87t_result *);
X87T_API x87t_error x87t_f2xm1(const x87t_context *,
                               x87t_raw80 x,
                               const x87t_control *,
                               x87t_result *);

/* Binary order: y = ST(1), x = ST(0); replace ST(1), then pop. */
X87T_API x87t_error
x87t_fpatan(const x87t_context *, x87t_raw80 y, x87t_raw80 x, const x87t_control *, x87t_result *);
X87T_API x87t_error
x87t_fyl2x(const x87t_context *, x87t_raw80 y, x87t_raw80 x, const x87t_control *, x87t_result *);
X87T_API x87t_error
x87t_fyl2xp1(const x87t_context *, x87t_raw80 y, x87t_raw80 x, const x87t_control *, x87t_result *);

#ifdef __cplusplus
}
#endif
#endif

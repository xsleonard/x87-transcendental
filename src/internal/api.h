#ifndef X87TRANS_INTERNAL_API_H
#define X87TRANS_INTERNAL_API_H
#include "x87trans/x87trans.h"

/* Classify before normalization. Numeric backends share this partition. */
typedef enum {
    RAW_ZERO,
    RAW_NORMAL,
    RAW_DENORMAL,
    RAW_PSEUDO,
    RAW_INFINITY,
    RAW_QNAN,
    RAW_SNAN,
    RAW_UNSUPPORTED
} raw_class;
raw_class x87t_internal_raw80_classify(x87t_raw80 value);
x87t_error x87t_internal_validate_call(const x87t_context *, const x87t_control *, x87t_result *);
void x87t_internal_result_begin(x87t_result *, x87t_destination);
void x87t_internal_result_range(x87t_result *);
/* Newly raised flags for a completed trig instruction; classification uses
 * the original encoding, including pseudo-denormals. */
uint8_t x87t_internal_trig_flags(x87t_raw80, int range_return, int sine_component);
void x87t_internal_result_finish(x87t_result *, const x87t_control *);
void x87t_internal_wrap_trig_underflow(x87t_raw80, x87t_result *, const x87t_control *);
#endif

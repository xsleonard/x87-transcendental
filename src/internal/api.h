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
raw_class raw80_classify(x87t_raw80 value);
x87t_error validate_call(const x87t_context *, const x87t_control *, x87t_result *);
void result_begin(x87t_result *, x87t_destination);
void result_range(x87t_result *);
#endif

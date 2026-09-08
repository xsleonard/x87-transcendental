#ifndef X87TRANS_INTERNAL_BINARY_H
#define X87TRANS_INTERNAL_BINARY_H
#include "internal/rational.h"
#include <stddef.h>
typedef struct {
    mpq_t rom[157];
} atan_constants;
typedef struct {
    mpq_t rom[270];
} log_constants;
struct x87t_context {
    atan_constants atan;
    log_constants log;
};
void atan_constants_init(atan_constants *);
void atan_constants_clear(atan_constants *);
void log_constants_init(log_constants *);
void log_constants_clear(log_constants *);
int fpatan_raw80(
    const atan_constants *, raw80 y, raw80 x, enum mode, raw80 *, int *c1, unsigned *exceptions);
int log_raw80(const log_constants *,
              int instruction,
              raw80 y,
              raw80 x,
              enum mode,
              raw80 *,
              int *c1,
              unsigned *exceptions);
x87t_error evaluate_log(
    const x87t_context *, int instruction, raw80 y, raw80 x, const x87t_control *, x87t_result *);
#endif

/* fyl2xp1 entry; the shared logarithm program owns the finite-domain policy. */
#include "internal/binary.h"
x87t_error x87t_fyl2xp1(const x87t_context *context,
                        x87t_raw80 y,
                        x87t_raw80 x,
                        const x87t_control *control,
                        x87t_result *out)
{
    return x87t_internal_evaluate_log(context, 1, y, x, control, out);
}

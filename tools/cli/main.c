/* A plain library client. Line protocol:
 * id instruction rc pc x_se x_sig [y_se y_sig]
 * Output: id error completion values primary_se primary_sig pushed_se pushed_sig
 *         cc cc_known exceptions exceptions_known destination
 */
#include "x87trans/x87trans.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef x87t_error (*unary_fn)(const x87t_context *,
                               x87t_raw80,
                               const x87t_control *,
                               x87t_result *);
typedef x87t_error (*binary_fn)(
    const x87t_context *, x87t_raw80, x87t_raw80, const x87t_control *, x87t_result *);
static const struct {
    const char *name;
    unary_fn call;
} unary[] = {{"fsin", x87t_fsin},
             {"fcos", x87t_fcos},
             {"fsincos", x87t_fsincos},
             {"fptan", x87t_fptan},
             {"f2xm1", x87t_f2xm1}};
static const struct {
    const char *name;
    binary_fn call;
} binary[] = {{"fpatan", x87t_fpatan}, {"fyl2x", x87t_fyl2x}, {"fyl2xp1", x87t_fyl2xp1}};
int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--help")) {
        puts("Input: id instruction rn|rd|ru|rz pc x_se x_sig [y_se y_sig]");
        return 0;
    }
    if (argc != 1)
        return 2;
    x87t_context *context = x87t_create();
    if (!context)
        return 3;
    char line[512], id[64], instruction[16], rounding[8], extra;
    int status = 0;
    while (fgets(line, sizeof(line), stdin)) {
        unsigned pc, xs, ys = 0;
        uint64_t xm, ym = 0;
        int count = sscanf(line,
                           "%63s %15s %7s %u %x %" SCNx64 " %x %" SCNx64 " %c",
                           id,
                           instruction,
                           rounding,
                           &pc,
                           &xs,
                           &xm,
                           &ys,
                           &ym,
                           &extra);
        if ((count != 6 && count != 8) || xs > 65535 || ys > 65535) {
            status = 2;
            break;
        }
        x87t_control control = X87T_CONTROL_INIT;
        const char *modes[] = {"rn", "rd", "ru", "rz"};
        unsigned mode;
        for (mode = 0; mode < 4 && strcmp(rounding, modes[mode]); ++mode) {
        }
        if (mode == 4) {
            status = 2;
            break;
        }
        control.rounding = (x87t_round)mode;
        control.precision_bits = pc;
        x87t_raw80 x = {(uint16_t)xs, xm}, y = {(uint16_t)ys, ym};
        x87t_result result = {0};
        x87t_error error = X87T_BAD_ARGUMENT;
        int found = 0;
        for (unsigned i = 0; i < sizeof(unary) / sizeof(unary[0]); ++i)
            if (!strcmp(instruction, unary[i].name) && count == 6) {
                error = unary[i].call(context, x, &control, &result);
                found = 1;
                break;
            }
        for (unsigned i = 0; i < sizeof(binary) / sizeof(binary[0]); ++i)
            if (!strcmp(instruction, binary[i].name) && count == 8) {
                error = binary[i].call(context, y, x, &control, &result);
                found = 1;
                break;
            }
        if (!found) {
            status = 2;
            break;
        }
        printf("%s %d %d %u %04x %016" PRIx64 " %04x %016" PRIx64 " %04x %04x %02x %02x %d\n",
               id,
               error,
               result.completion,
               result.values,
               result.primary.se,
               result.primary.sig,
               result.pushed.se,
               result.pushed.sig,
               result.cc,
               result.cc_known,
               result.exceptions,
               result.exceptions_known,
               result.destination);
    }
    if (ferror(stdin) || fflush(stdout))
        status = 3;
    x87t_destroy(context);
    return status;
}

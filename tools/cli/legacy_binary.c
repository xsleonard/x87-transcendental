#include "legacy_binary.h"
#include "x87trans/x87trans.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
int legacy_binary_cli(int logarithms)
{
    x87t_context *context = x87t_create();
    if (!context)
        return 3;
    char line[256], id[64], instruction[16], rounding[4], extra;
    int status = 0;
    while (fgets(line, sizeof(line), stdin)) {
        unsigned pc, ys, xs;
        uint64_t ym, xm;
        int count = logarithms ? sscanf(line,
                                        "%63s %15s %3s %u %x %" SCNx64 " %x %" SCNx64 " %c",
                                        id,
                                        instruction,
                                        rounding,
                                        &pc,
                                        &ys,
                                        &ym,
                                        &xs,
                                        &xm,
                                        &extra)
                               : sscanf(line,
                                        "%63s %3s %u %x %" SCNx64 " %x %" SCNx64 " %c",
                                        id,
                                        rounding,
                                        &pc,
                                        &ys,
                                        &ym,
                                        &xs,
                                        &xm,
                                        &extra);
        if (count != (logarithms ? 8 : 7) || ys > 65535 || xs > 65535) {
            status = 2;
            break;
        }
        const char *names[] = {"rn", "rd", "ru", "rz"};
        unsigned rc;
        for (rc = 0; rc < 4 && strcmp(rounding, names[rc]); ++rc) {
        }
        if (rc == 4) {
            status = 2;
            break;
        }
        x87t_control control = {(x87t_round)rc, pc, 63};
        x87t_result result;
        x87t_raw80 x = {(uint16_t)xs, xm}, y = {(uint16_t)ys, ym};
        x87t_error error;
        if (!logarithms)
            error = x87t_fpatan(context, y, x, &control, &result);
        else if (!strcmp(instruction, "fyl2x"))
            error = x87t_fyl2x(context, y, x, &control, &result);
        else if (!strcmp(instruction, "fyl2xp1"))
            error = x87t_fyl2xp1(context, y, x, &control, &result);
        else {
            status = 2;
            break;
        }
        if (error) {
            fprintf(stderr, "Unsupported operand/control: %d\n", error);
            status = 2;
            break;
        }
        printf("%s %04x %016" PRIx64 " %u %02x 00\n",
               id,
               result.primary.se,
               result.primary.sig,
               !!(result.cc & X87T_C1),
               result.exceptions);
    }
    if (ferror(stdin) || fflush(stdout))
        status = 3;
    x87t_destroy(context);
    return status;
}

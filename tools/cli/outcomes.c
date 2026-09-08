/* Full outcome client: id op rc pc masks x_se x_sig y_se y_sig.
 * Unary instructions ignore y. The final output field is first_unmasked;
 * preceding fields retain the ordinary CLI's ordering. */
#include <x87trans/x87trans.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    x87t_context *context = x87t_create();
    if (!context)
        return 3;
    char line[512], id[64], op[16], rc[8], extra;
    int status = 0;
    while (fgets(line, sizeof(line), stdin)) {
        unsigned pc, masks, xs, ys;
        uint64_t xm, ym;
        if (sscanf(line, "%63s %15s %7s %u %x %x %" SCNx64 " %x %" SCNx64 " %c",
                   id, op, rc, &pc, &masks, &xs, &xm, &ys, &ym, &extra) != 9 ||
            masks > 255 || xs > 65535 || ys > 65535) {
            status = 2;
            break;
        }
        const char *modes[] = {"rn", "rd", "ru", "rz"};
        unsigned mode;
        for (mode = 0; mode < 4 && strcmp(rc, modes[mode]); ++mode) {}
        x87t_control control = {(x87t_round)mode, pc, (uint8_t)masks};
        x87t_raw80 x = {(uint16_t)xs, xm}, y = {(uint16_t)ys, ym};
        x87t_result r = {0};
        x87t_error error;
        if (!strcmp(op, "fsin")) error = x87t_fsin(context, x, &control, &r);
        else if (!strcmp(op, "fcos")) error = x87t_fcos(context, x, &control, &r);
        else if (!strcmp(op, "fsincos")) error = x87t_fsincos(context, x, &control, &r);
        else if (!strcmp(op, "fptan")) error = x87t_fptan(context, x, &control, &r);
        else if (!strcmp(op, "f2xm1")) error = x87t_f2xm1(context, x, &control, &r);
        else if (!strcmp(op, "fpatan")) error = x87t_fpatan(context, y, x, &control, &r);
        else if (!strcmp(op, "fyl2x")) error = x87t_fyl2x(context, y, x, &control, &r);
        else if (!strcmp(op, "fyl2xp1")) error = x87t_fyl2xp1(context, y, x, &control, &r);
        else { status = 2; break; }
        printf("%s %d %d %u %04x %016" PRIx64 " %04x %016" PRIx64
               " %04x %04x %02x %02x %d %02x\n", id, error, r.completion, r.values,
               r.primary.se, r.primary.sig, r.pushed.se, r.pushed.sig, r.cc, r.cc_known,
               r.exceptions, r.exceptions_known, r.destination, r.first_unmasked);
    }
    if (ferror(stdin) || fflush(stdout)) status = 3;
    x87t_destroy(context);
    return status;
}

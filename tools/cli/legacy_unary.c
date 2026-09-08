/* Compatibility for ordinary --batch raw80 invocations. Historical kernel
 * experiments and trace protocols remain in the archived research program. */
#include "x87trans/x87trans.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
int main(int argc, char **argv)
{
    x87t_error (*call)(const x87t_context *, x87t_raw80, const x87t_control *, x87t_result *) =
        x87t_fsincos;
    x87t_control control = X87T_CONTROL_INIT;
    int batch = 0, selected = 0;
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--batch"))
            batch = 1;
        else if (!strncmp(argv[i], "--rc=", 5)) {
            const char *names[] = {"rn", "rd", "ru", "rz"};
            unsigned rc;
            for (rc = 0; rc < 4 && strcmp(argv[i] + 5, names[rc]); ++rc) {
            }
            if (rc == 4)
                return 2;
            control.rounding = (x87t_round)rc;
        } else {
            if (selected++)
                return 2;
            if (!strcmp(argv[i], "--fsin-standalone"))
                call = x87t_fsin;
            else if (!strcmp(argv[i], "--fcos-standalone"))
                call = x87t_fcos;
            else if (!strcmp(argv[i], "--fptan"))
                call = x87t_fptan;
            else if (!strcmp(argv[i], "--f2xm1"))
                call = x87t_f2xm1;
            else {
                fprintf(stderr, "Unsupported option; experimental modes are in research.\n");
                return 2;
            }
        }
    }
    if (!batch)
        return 2;
    x87t_context *context = x87t_create();
    if (!context)
        return 3;
    char line[128], extra;
    unsigned se;
    uint64_t sig;
    int status = 0;
    while (fgets(line, sizeof(line), stdin)) {
        if (sscanf(line, "%x %" SCNx64 " %c", &se, &sig, &extra) != 2 || se > 65535) {
            status = 2;
            break;
        }
        x87t_result result;
        x87t_error error = call(context, (x87t_raw80){(uint16_t)se, sig}, &control, &result);
        if (error) {
            fprintf(stderr, "Unsupported operand/control: %d\n", error);
            status = 2;
            break;
        }
        if (result.completion == X87T_RANGE_RETURN) {
            puts("C2");
            continue;
        }
        printf("OK %04x %016" PRIx64, result.primary.se, result.primary.sig);
        if (result.values & X87T_PUSHED)
            printf(" %04x %016" PRIx64, result.pushed.se, result.pushed.sig);
        putchar('\n');
    }
    if (ferror(stdin) || fflush(stdout))
        status = 3;
    x87t_destroy(context);
    return status;
}

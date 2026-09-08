/* Public two-operand FPATAN capture harness. No mathematical model here.
 * Exactly one FPATAN per accepted line; never runs a warmup or self-test.
 * A persistent external guard must validate/reserve the WHOLE input first.
 * Input: id rc pc y_se y_sig x_se x_sig (hex encodings, decimal PC).
 * FNINIT, masked exceptions, two loads, status before/after, one 80-bit store.
 * Loading special encodings can affect state; the pre-instruction status is
 * retained rather than silently attributing load exceptions to FPATAN.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <cpuid.h>
#if !defined(__i386__) && !defined(__x86_64__)
#error Build on the capture x86 host
#endif
typedef struct { unsigned char b[10]; } raw80;
static raw80 pack(unsigned se, unsigned long long sig)
{
    raw80 r; uint16_t s=(uint16_t)se; uint64_t m=(uint64_t)sig;
    memcpy(r.b,&m,8); memcpy(r.b+8,&s,2); return r;
}
int main(int argc,char **argv)
{
    if(argc==2 && !strcmp(argv[1],"--identity")) {
        unsigned a,b,c,d; __cpuid(1,a,b,c,d);
        printf("CPUID1 %08x %08x %08x %08x\n",a,b,c,d); return 0;
    }
    if(argc!=1) return 2;
    char line[256],id[64],rc[4],extra; unsigned pc,ys,xs;
    unsigned long long ym,xm; unsigned long count=0;
    while(fgets(line,sizeof(line),stdin)) {
        if(sscanf(line,"%63s %3s %u %x %llx %x %llx %c",
                  id,rc,&pc,&ys,&ym,&xs,&xm,&extra)!=7 ||
           ys>65535 || xs>65535) return 2;
        uint16_t cw=0x007f,actual,before,after;
        if(!strcmp(rc,"rd")) cw|=0x400; else if(!strcmp(rc,"ru")) cw|=0x800;
        else if(!strcmp(rc,"rz")) cw|=0xc00; else if(strcmp(rc,"rn")) return 2;
        if(pc==64) cw|=0x300; else if(pc==53) cw|=0x200;
        else if(pc!=24) return 2;
        raw80 y=pack(ys,ym),x=pack(xs,xm),out;
        __asm__ volatile("fninit\n\tfldcw %[cw]\n\tfldt %[y]\n\tfldt %[x]\n\t"
                         "fnstsw %[before]\n\tfpatan\n\tfwait\n\t"
                         "fnstsw %[after]\n\tfnstcw %[actual]\n\tfstpt %[out]"
            : [before] "=m"(before),[after] "=m"(after),
              [actual] "=m"(actual),[out] "=m"(out)
            : [cw] "m"(cw),[y] "m"(y),[x] "m"(x)
            : "st","st(1)","memory");
        uint16_t se; uint64_t sig;
        memcpy(&sig,out.b,8); memcpy(&se,out.b+8,2);
        printf("%s %s %u %04x %016llx %04x %016llx %04x %04x %04x %04x %016llx\n",
               id,rc,pc,ys,ym,xs,xm,actual,before,after,se,(unsigned long long)sig);
        count++; if(ferror(stdout)) return 3;
    }
    if(ferror(stdin) || fflush(stdout)) return 3;
    fprintf(stderr,"COMPLETE %lu\n",count); return 0;
}

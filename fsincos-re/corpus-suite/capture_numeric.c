/* CPU-independent x87 numerical capture protocol v1.
 * Exactly one requested FSIN/FCOS/FSINCOS per input. No warmup, timing,
 * FXSAVE, SSE, or numerical library calls are required by the capture core.
 * Inputs use: case instruction rc pc masks depth prior se sig.
 * Only the numerical contract (masked exceptions, depth1, clear state) is
 * accepted. Full arbitrary-state snapshots belong to a different harness.
 * Status is saved BEFORE popping the 80-bit results. Extended stores do not
 * narrow the significand. C2 preserves and records the original stack top.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <cpuid.h>

#if !defined(__i386__) && !defined(__x86_64__)
#error "Build this numerical capture program for the target x86 CPU"
#endif

struct raw80 { unsigned char bytes[10]; };

static void print_raw(const struct raw80 *value)
{
    uint16_t se;uint64_t sig;
    memcpy(&sig,value->bytes,8);memcpy(&se,value->bytes+8,2);
    printf("%04x:%016llx",(unsigned)se,(unsigned long long)sig);
}

static void identity(void)
{
    unsigned signature=0,max=__get_cpuid_max(0,&signature),a,b,c,d;
    if (!max) {fprintf(stderr,"CPUID leaf1 is required\n");exit(2);}
    __cpuid(0,a,b,c,d);
    char vendor[13];memcpy(vendor,&b,4);memcpy(vendor+4,&d,4);memcpy(vendor+8,&c,4);vendor[12]=0;
    printf("CPUID 00000000 00000000 %08x %08x %08x %08x\n",a,b,c,d);
    __cpuid(1,a,b,c,d);
    unsigned family=(a>>8)&15,model=(a>>4)&15,step=a&15;
    if (family==6 || family==15) model|=((a>>16)&15)<<4;
    if (family==15) family+=(a>>20)&255;
    printf("IDENTITY %s %08x %u %u %u %u\n",vendor,a,family,model,step,(c>>31)&1);
    printf("CPUID 00000001 00000000 %08x %08x %08x %08x\n",a,b,c,d);
    unsigned hypervisor=(c>>31)&1;
    if (!(d&1)) {fprintf(stderr,"CPUID does not report an x87 FPU\n");exit(2);}
    if (max>=7) {__cpuid_count(7,0,a,b,c,d);printf("CPUID 00000007 00000000 %08x %08x %08x %08x\n",a,b,c,d);}
    if (max>=0x1a) {__cpuid_count(0x1a,0,a,b,c,d);printf("CPUID 0000001a 00000000 %08x %08x %08x %08x\n",a,b,c,d);}
    unsigned extended=__get_cpuid_max(0x80000000,0);
    for(unsigned leaf=0x80000000;leaf<=0x80000004 && leaf<=extended;leaf++) {
        __cpuid(leaf,a,b,c,d);printf("CPUID %08x 00000000 %08x %08x %08x %08x\n",leaf,a,b,c,d);
    }
    if(hypervisor) {__cpuid_count(0x40000000,0,a,b,c,d);printf("CPUID 40000000 00000000 %08x %08x %08x %08x\n",a,b,c,d);}
}

static int capture(void)
{
    char line[512];unsigned long line_number=0;
    while(fgets(line,sizeof(line),stdin)) {
        line_number++;
        if(line[0]=='#' || line[0]=='\n') continue;
        char id[96],insn[16],mode[8],pc[8],prior[8],extra;
        unsigned masks,depth,se;unsigned long long sig;
        if(sscanf(line,"%95s %15s %7s %7s %x %u %7s %x %llx %c",id,insn,mode,pc,&masks,&depth,prior,&se,&sig,&extra)!=9 ||
            se>0xffff || masks!=0x3f || depth!=1 || strcmp(prior,"clear")) {
            fprintf(stderr,"line %lu: malformed or unsupported capture contract\n",line_number);return 2;
        }
        uint16_t cw=0x007f,bsw,sw,actual_cw;int phase;
        if(!strcmp(mode,"rd"))cw|=0x400;else if(!strcmp(mode,"ru"))cw|=0x800;
        else if(!strcmp(mode,"rz"))cw|=0xc00;else if(strcmp(mode,"rn"))return 2;
        if(!strcmp(pc,"pc53"))cw|=0x200;else if(!strcmp(pc,"pc64"))cw|=0x300;
        else if(strcmp(pc,"pc24"))return 2;
        if(!strcmp(insn,"fsin"))phase=0;else if(!strcmp(insn,"fcos"))phase=1;
        else if(!strcmp(insn,"fsincos"))phase=2;else return 2;
        struct raw80 input,sine={{0}},cosine={{0}},preserved={{0}};uint16_t short_se=(uint16_t)se;uint64_t word=(uint64_t)sig;
        memcpy(input.bytes,&word,8);memcpy(input.bytes+8,&short_se,2);
        __asm__ volatile("fninit\n\tfldcw %[cw]\n\tfldt %[x]\n\tfnstsw %[bsw]"
            : [bsw] "=m" (bsw) : [cw] "m" (cw),[x] "m" (input) : "st","memory");
        if(phase==0) __asm__ volatile("fsin\n\tfwait\n\tfnstsw %[sw]\n\tfnstcw %[cw]"
            : [sw] "=m" (sw),[cw] "=m" (actual_cw) :: "st","st(1)","memory");
        else if(phase==1) __asm__ volatile("fcos\n\tfwait\n\tfnstsw %[sw]\n\tfnstcw %[cw]"
            : [sw] "=m" (sw),[cw] "=m" (actual_cw) :: "st","st(1)","memory");
        else __asm__ volatile("fsincos\n\tfwait\n\tfnstsw %[sw]\n\tfnstcw %[cw]"
            : [sw] "=m" (sw),[cw] "=m" (actual_cw) :: "st","st(1)","memory");
        if(sw&0x400) __asm__ volatile("fstpt %0" : "=m" (preserved) :: "st","memory");
        else if(phase==2) __asm__ volatile("fstpt %0\n\tfstpt %1" : "=m" (cosine),"=m" (sine) :: "st","st(1)","memory");
        else if(phase==0) __asm__ volatile("fstpt %0" : "=m" (sine) :: "st","memory");
        else __asm__ volatile("fstpt %0" : "=m" (cosine) :: "st","memory");
        printf("CASE=%s INSN=%s MODE=%s PC=%s IN=%04x:%016llx CW=%04x B_SW=%04x A_SW=%04x SIN=",
            id,insn,mode,pc,se,sig,(unsigned)actual_cw,(unsigned)bsw,(unsigned)sw);
        if(!(sw&0x400) && phase!=1)print_raw(&sine);else putchar('-');
        printf(" COS=");if(!(sw&0x400) && phase!=0)print_raw(&cosine);else putchar('-');
        printf(" PRESERVED=");if(sw&0x400)print_raw(&preserved);else putchar('-');putchar('\n');
        if(ferror(stdout))return 3;
    }
    if(ferror(stdin) || fflush(stdout))return 3;
    return 0;
}

int main(int argc,char **argv)
{
    if(argc==2 && !strcmp(argv[1],"--identity")) {identity();return 0;}
    if(argc!=1) {fprintf(stderr,"usage: capture_numeric [--identity]\n");return 2;}
    return capture();
}

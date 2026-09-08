/* One-attempt x87 outcome capture on Linux x86-64. No warmup or retry.
 * Input: id op rc pc masks x_se x_sig y_se y_sig (unary y must be zero).
 * Restore raw operands, execute exactly one instruction, snapshot before
 * FWAIT, record any #MF context, then clear solely to continue the harness.
 * Use only through the durable guard after history clearance and freezing.
 */
#define _GNU_SOURCE
#include <inttypes.h>
#include <signal.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ucontext.h>
#include <unistd.h>

typedef struct { unsigned char bytes[512]; } __attribute__((aligned(16))) state;
_Static_assert(sizeof(struct _libc_fpstate) == 512, "Linux signal FP layout");
volatile sig_atomic_t x87t_capture_after_valid;
static volatile sig_atomic_t armed, fault_at;
static uintptr_t site, wait_site, resume;
static volatile state fault;

#define ONCE(name, insn) \
extern void once_##name(state *); \
extern unsigned char site_##name[], wait_##name[], resume_##name[]; \
__asm__(".text\n.p2align 4\n.globl once_" #name ",site_" #name ",wait_" #name ",resume_" #name "\n" \
        "once_" #name ":\nsite_" #name ":\n\t" insn "\n\tfxsave64 (%rdi)\n" \
        "\tmovl $1,x87t_capture_after_valid(%rip)\nwait_" #name ":\n\tfwait\n" \
        "resume_" #name ":\n\tfnclex\n\tret\n");
ONCE(fsin, "fsin")
ONCE(fcos, "fcos")
ONCE(fsincos, "fsincos")
ONCE(fptan, "fptan")
ONCE(f2xm1, "f2xm1")
ONCE(fpatan, "fpatan")
ONCE(fyl2x, "fyl2x")
ONCE(fyl2xp1, "fyl2xp1")

static void catch_fpe(int signo, siginfo_t *info, void *pointer)
{
    (void)info;
    ucontext_t *uc = pointer;
    uintptr_t rip = uc->uc_mcontext.gregs[REG_RIP];
    if (signo != SIGFPE || !armed || fault_at || !uc->uc_mcontext.fpregs)
        _exit(90);
    fault_at = rip == site ? 1 : rip == wait_site ? 2 : 3;
    if (fault_at == 3) _exit(91);
    volatile const unsigned char *source = (const unsigned char *)uc->uc_mcontext.fpregs;
    for (unsigned j = 0; j < 512; ++j) fault.bytes[j] = source[j];
    uc->uc_mcontext.fpregs->swd &= 0x7f00;
    uc->uc_mcontext.fpregs->cwd |= 63;
    uc->uc_mcontext.gregs[REG_RIP] = resume;
}

static void store16(unsigned char *p, unsigned v)
{ p[0] = v; p[1] = v >> 8; }
static void raw80(unsigned char *p, unsigned se, uint64_t sig)
{
    for (unsigned j = 0; j < 8; ++j) p[j] = sig >> (8*j);
    store16(p+8, se);
}
static void print_state(const state *s)
{ for (unsigned j = 0; j < 512; ++j) printf("%02x", s->bytes[j]); }

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--identity")) {
        unsigned a=1,b,c=0,d;
        __asm__ volatile("cpuid" : "+a"(a), "=b"(b), "+c"(c), "=d"(d));
        printf("CPUID %08x\n", a);
        return 0;
    }
    if (argc != 1) return 2;
    struct sigaction action;
    memset(&action,0,sizeof action);
    action.sa_sigaction=catch_fpe;action.sa_flags=SA_SIGINFO;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGFPE,&action,NULL)) return 3;
    char line[512],id[64],op[16],mode[8],extra;
    unsigned count=0;
    while (fgets(line,sizeof line,stdin)) {
        unsigned pc,masks,xs,ys;uint64_t xm,ym;
        if (sscanf(line,"%63s %15s %7s %u %x %x %" SCNx64 " %x %" SCNx64 " %c",
                   id,op,mode,&pc,&masks,&xs,&xm,&ys,&ym,&extra)!=9 ||
            masks>63 || xs>65535 || ys>65535 || (pc!=24 && pc!=53 && pc!=64)) return 4;
        const char *modes[]={"rn","rd","ru","rz"};
        unsigned rc;for(rc=0;rc<4 && strcmp(mode,modes[rc]);++rc) {}
        if(rc==4)return 4;
        void (*call)(state *)=NULL;
#define SELECT(name) if(!strcmp(op,#name)) { call=once_##name;site=(uintptr_t)site_##name;wait_site=(uintptr_t)wait_##name;resume=(uintptr_t)resume_##name; }
        SELECT(fsin) SELECT(fcos) SELECT(fsincos) SELECT(fptan)
        SELECT(f2xm1) SELECT(fpatan) SELECT(fyl2x) SELECT(fyl2xp1)
        if(!call)return 4;
        int binary=!strcmp(op,"fpatan") || !strcmp(op,"fyl2x") || !strcmp(op,"fyl2xp1");
        if(!binary && (ys || ym))return 4;
        state input={{0}},before={{0}},after={{0}};
        unsigned cw=masks|0x40|(pc==64?0x300:pc==53?0x200:0)|(rc<<10);
        store16(input.bytes,cw);store16(input.bytes+2,0x3000);
        input.bytes[4]=0xc0;store16(input.bytes+24,0x1f80);
        for(unsigned j=0;j<8;++j)raw80(input.bytes+32+16*j,0x4001,UINT64_C(0x987654321abcdef0)+j);
        raw80(input.bytes+32,xs,xm);
        if(binary)raw80(input.bytes+48,ys,ym);
        __asm__ volatile("fninit\n\tfxrstor64 %0" :: "m"(input) : "memory",
            "st","st(1)","st(2)","st(3)","st(4)","st(5)","st(6)","st(7)",
            "xmm0","xmm1","xmm2","xmm3","xmm4","xmm5","xmm6","xmm7",
            "xmm8","xmm9","xmm10","xmm11","xmm12","xmm13","xmm14","xmm15");
        __asm__ volatile("fxsave64 %0" : "=m"(before) :: "memory");
        if (memcmp(before.bytes,input.bytes,5) || memcmp(before.bytes+32,input.bytes+32,10) ||
            (binary && memcmp(before.bytes+48,input.bytes+48,10))) return 5;
        fault_at=0;x87t_capture_after_valid=0;armed=1;
        call(&after);
        armed=0;
        printf("%s ",id);print_state(&before);putchar(' ');
        print_state(x87t_capture_after_valid?&after:(const state *)&fault);
        printf(" %d ",fault_at);
        if(fault_at)print_state((const state *)&fault);else putchar('-');
        putchar('\n');fflush(stdout);++count;
    }
    if(ferror(stdin))return 6;
    fprintf(stderr,"COMPLETE %u\n",count);
    return 0;
}

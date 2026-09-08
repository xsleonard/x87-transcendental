/* H1678: restoration-only observation, never FSIN/FCOS/FWAIT.
 * Input: case method order mode pc masks depth cc flags summary se sig
 * Methods: fxrstor, fldenv, frstor, fldcw, fnstenv. Orders: scalar, fx.
 * Load under all masks; establish one requested state and observe once.
 * All instructions after a possibly pending state are NO-WAIT observations
 * and FNCLEX. No arithmetic, retry, warmup or selftest is permitted.
 * FLDCW starts with all exceptions masked. Legacy loads also start there.
 * Observe scalar SW/CW before or after FXSAVE, on distinct fresh operands.
 * SAVED fields belong only to FNSTENV's pre-mask environment image.
 * A failed or partial campaign must never be retried.
 */
#define _GNU_SOURCE
#if !defined(__linux__) || !defined(__x86_64__)
#error "H1678 requires the authorized Linux x86-64 research host"
#endif
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

struct x80 { unsigned char b[10]; };
struct fxarea { unsigned char b[512]; } __attribute__((aligned(16)));
struct legacy { unsigned char b[108]; };

static uint16_t u16(const unsigned char *p) { uint16_t v; memcpy(&v,p,2); return v; }
static uint64_t u64(const unsigned char *p) { uint64_t v; memcpy(&v,p,8); return v; }
static void put16(unsigned char *p,uint16_t v) { memcpy(p,&v,2); }
static void pack(struct x80 *p,uint16_t se,uint64_t sig)
{ memcpy(p->b,&sig,8); memcpy(p->b+8,&se,2); }

static void unexpected_fpe(int signo)
{
    /* Fail closed, with no context restoration or reexecution. The supported
     * target's documented no-wait operations do not deliver pending #MF. */
    (void)signo;
    _exit(90);
}

static void load_stack(const struct x80 *operand,unsigned depth)
{
    struct x80 sentinels[7];
    /* 1 + (index+1)*2^-60: normal, exact, and readily distinguishable. */
    for(unsigned i=0;i<7;i++) pack(&sentinels[i],0x3fff,(UINT64_C(1)<<63)+8*(i+1));
    for(int i=(int)depth-2;i>=0;i--)
        __asm__ volatile("fldt %0" :: "m"(sentinels[i]) : "st","memory");
    __asm__ volatile("fldt %0" :: "m"(*operand) : "st","memory");
}

#define RESTORE_CLOBBERS "memory","st","st(1)","st(2)","st(3)","st(4)","st(5)","st(6)","st(7)", \
    "xmm0","xmm1","xmm2","xmm3","xmm4","xmm5","xmm6","xmm7", \
    "xmm8","xmm9","xmm10","xmm11","xmm12","xmm13","xmm14","xmm15"

static void restore_fx(const struct fxarea *p)
{ __asm__ volatile("fxrstor64 %0" :: "m"(*p) : RESTORE_CLOBBERS); }

/* Dedicated external assembler routines make both observation cuts auditable.
 * No library call or waiting instruction can occur between these observations
 * and the non-wait cleanup. CW and SW pointers are ordinary initialized memory.
 */
extern void h1678_scalar_first(struct fxarea *,uint16_t *,uint16_t *);
extern void h1678_fx_first(struct fxarea *,uint16_t *,uint16_t *);
__asm__(
    ".text\n.p2align 4\n.globl h1678_scalar_first\n.type h1678_scalar_first,@function\n"
    "h1678_scalar_first:\n\tfnstsw (%rsi)\n\tfnstcw (%rdx)\n\tfxsave64 (%rdi)\n\tfnclex\n\tret\n"
    ".size h1678_scalar_first,.-h1678_scalar_first\n"
    ".p2align 4\n.globl h1678_fx_first\n.type h1678_fx_first,@function\n"
    "h1678_fx_first:\n\tfxsave64 (%rdi)\n\tfnstsw (%rsi)\n\tfnstcw (%rdx)\n\tfnclex\n\tret\n"
    ".size h1678_fx_first,.-h1678_fx_first\n");

static int parse_mode(const char *s)
{
    if(!strcmp(s,"rn")) return 0;
    if(!strcmp(s,"rd")) return 0x400;
    if(!strcmp(s,"ru")) return 0x800;
    if(!strcmp(s,"rz")) return 0xc00;
    return -1;
}
static int parse_pc(const char *s)
{
    if(!strcmp(s,"pc24")) return 0;
    if(!strcmp(s,"pc53")) return 0x200;
    if(!strcmp(s,"pc64")) return 0x300;
    return -1;
}

int main(void)
{
    if(signal(SIGFPE,unexpected_fpe)==SIG_ERR) return 2;
    char line[512]; unsigned number=0;
    while(fgets(line,sizeof line,stdin)) {
        char id[32]={0},method[16]={0},order[16]={0},mode[8]={0},pc[8]={0},extra;
        unsigned masks,depth,cc,flags,summary,se; unsigned long long sig;
        ++number;
        int n=sscanf(line,"%31s %15s %15s %7s %7s %x %u %x %x %x %x %llx %c",
            id,method,order,mode,pc,&masks,&depth,&cc,&flags,&summary,&se,&sig,&extra);
        int rc=parse_mode(mode),precision=parse_pc(pc),kind=-1;
        if(!strcmp(method,"fxrstor")) kind=0;
        if(!strcmp(method,"fldenv")) kind=1;
        if(!strcmp(method,"frstor")) kind=2;
        if(!strcmp(method,"fldcw")) kind=3;
        if(!strcmp(method,"fnstenv")) kind=4;
        if(n!=12 || kind<0 || (strcmp(order,"scalar") && strcmp(order,"fx")) || rc<0 || precision<0
            || masks>63 || depth<1 || depth>8 || (cc&~0x4700u) || flags>0x7f
            || ((flags&64) && !(flags&1)) || (summary&~0x8080u)
            || (kind>=3 && summary) || se>0xffff || (se&0x7fff)!=0x3ffc || !(sig>>63)) {
            fprintf(stderr,"line %u: invalid restoration input\n",number); return 2;
        }
        struct x80 operand; struct fxarea seed,observed; struct legacy env,saved;
        memset(&seed,0,sizeof seed); memset(&observed,0,sizeof observed);
        memset(&env,0,sizeof env); memset(&saved,0,sizeof saved);
        pack(&operand,(uint16_t)se,(uint64_t)sig);
        uint16_t cw=(uint16_t)(0x40|masks|rc|precision),load_cw=(uint16_t)(cw|63);
        __asm__ volatile("fninit\n\tfldcw %0" :: "m"(load_cw) : "memory");
        load_stack(&operand,depth);
        /* FNSTENV is harmless here: the seed already has all masks set. Its
         * 28-byte protected/long-mode environment supplies the legacy layout.
         * Raw data registers remain loaded; FRSTOR receives their logical order.
         */
        __asm__ volatile("fxsave64 %0\n\tfnstenv %1" : "=m"(seed),"=m"(env) :: "memory");
        uint16_t requested=(uint16_t)((((-depth)&7)<<11)|cc|flags|summary);
        put16(seed.b,cw); put16(seed.b+2,requested);
        put16(env.b,cw); put16(env.b+4,requested);
        for(unsigned i=0;i<8;i++) memcpy(env.b+28+10*i,seed.b+32+16*i,10);
        uint16_t scalar_sw=0,scalar_cw=0;
        int scalar_first=!strcmp(order,"scalar");
        /* Every potentially waiting state-establishment opcode below begins
         * with a masked/no-pending seed. After it, use only no-wait operations.
         * In particular FLDCW is not issued against a prior pending state.
         */
        if(kind==0) restore_fx(&seed);
        else if(kind==1) __asm__ volatile("fldenv %0" :: "m"(env) : "memory");
        else if(kind==2) __asm__ volatile("frstor %0" :: "m"(env) : RESTORE_CLOBBERS);
        else if(kind==3) {
            put16(seed.b,load_cw); put16(seed.b+2,(uint16_t)(requested&~0x8080u));
            restore_fx(&seed);
            __asm__ volatile("fldcw %0" :: "m"(cw) : "memory");
        } else {
            put16(seed.b+2,(uint16_t)((requested&~0x8080u)|((flags&~masks&63)?0x8080:0)));
            restore_fx(&seed);
            __asm__ volatile("fnstenv %0" : "=m"(saved) :: "memory");
        }
        if(scalar_first) h1678_scalar_first(&observed,&scalar_sw,&scalar_cw);
        else h1678_fx_first(&observed,&scalar_sw,&scalar_cw);
        printf("CASE=%s METHOD=%s ORDER=%s MODE=%s PC=%s MASKS=%02x DEPTH=%u CC=%04x FLAGS=%02x SUMMARY=%04x REQ_CW=%04x REQ_SW=%04x SCALAR_CW=%04x SCALAR_SW=%04x SAVED_CW=%04x SAVED_SW=%04x SAVED_TW=%04x",
            id,method,order,mode,pc,masks,depth,cc,flags,summary,cw,requested,scalar_cw,scalar_sw,
            u16(saved.b),u16(saved.b+4),u16(saved.b+8));
        unsigned sw=u16(observed.b+2);
        printf(" FX_CW=%04x FX_SW=%04x FX_TOP=%u FX_FTW=%02x",u16(observed.b),sw,(sw>>11)&7,observed.b[4]);
        for(unsigned i=0;i<8;i++)
            printf(" FX_R%u=%04x:%016llx",i,u16(observed.b+32+16*i+8),(unsigned long long)u64(observed.b+32+16*i));
        printf(" FX_FOP=%04x FX_FIP=%016llx FX_FDP=%016llx\n",u16(observed.b+6),
            (unsigned long long)u64(observed.b+8),(unsigned long long)u64(observed.b+16));
    }
    __asm__ volatile("fninit" ::: "memory");
    return ferror(stdin)?4:0;
}

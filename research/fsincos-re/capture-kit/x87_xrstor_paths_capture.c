/* H1685: one standard XRSTOR/XRSTOR64, then no-wait observation/cleanup.
 * Input: case form order request present seed_pending mode pc masks depth cc flags summary se sig
 * form=w32|w64, order=scalar|fx, request/present/seed_pending are each 0|1.
 * Only x87 component 0 is requested. All XSAVE header reserved bytes are zero.
 * Neither unsupported compacted/supervisor restore nor FSIN/FCOS/FWAIT runs.
 * A distinct memory-image operand contrasts with the existing register value.
 * The seed, source image and observed result are all recorded separately.
 * One fresh audited row per operand. Never retry a partial or failed capture.
 */
#define main h1685_archived_restore_paths_main_not_used
#include "x87_restore_paths_capture.c"
#undef main
#include <cpuid.h>

struct xsavearea { unsigned char b[576]; } __attribute__((aligned(64)));
_Static_assert(sizeof(struct xsavearea)==576,"Unexpected XSAVE area size");

extern void h1685_xrstor32(const struct xsavearea *,unsigned);
extern void h1685_xrstor64(const struct xsavearea *,unsigned);
__asm__(
    ".text\n.p2align 4\n.globl h1685_xrstor32\n.type h1685_xrstor32,@function\n"
    "h1685_xrstor32:\n\tmovl %esi,%eax\n\txorl %edx,%edx\n\txrstor (%rdi)\n\tret\n"
    ".size h1685_xrstor32,.-h1685_xrstor32\n"
    ".p2align 4\n.globl h1685_xrstor64\n.type h1685_xrstor64,@function\n"
    "h1685_xrstor64:\n\tmovl %esi,%eax\n\txorl %edx,%edx\n\txrstor64 (%rdi)\n\tret\n"
    ".size h1685_xrstor64,.-h1685_xrstor64\n");

static void print_fx(const char *prefix,const struct fxarea *p)
{
    unsigned sw=u16(p->b+2);
    printf(" %s_CW=%04x %s_SW=%04x %s_TOP=%u %s_FTW=%02x",prefix,u16(p->b),prefix,sw,prefix,(sw>>11)&7,prefix,p->b[4]);
    for(unsigned i=0;i<8;i++)
        printf(" %s_R%u=%04x:%016llx",prefix,i,u16(p->b+32+16*i+8),(unsigned long long)u64(p->b+32+16*i));
    printf(" %s_FOP=%04x %s_FIP=%016llx %s_FDP=%016llx",prefix,u16(p->b+6),
        prefix,(unsigned long long)u64(p->b+8),prefix,(unsigned long long)u64(p->b+16));
}

int main(void)
{
    unsigned a,b,c,d;
    if(__get_cpuid_max(0,0)<0x0d) return 2;
    __cpuid_count(1,0,a,b,c,d);
    if((c&(3u<<26))!=(3u<<26)) return 2;
    __asm__ volatile("xgetbv" : "=a"(a),"=d"(d) : "c"(0));
    if(!(a&1)) return 2;
    if(signal(SIGFPE,unexpected_fpe)==SIG_ERR) return 2;
    char line[512]; unsigned number=0;
    while(fgets(line,sizeof line,stdin)) {
        char id[32]={0},form[8]={0},order[16]={0},mode[8]={0},pc[8]={0},extra;
        unsigned request,present,seed_pending,masks,depth,cc,flags,summary,se; unsigned long long sig;
        ++number;
        int n=sscanf(line,"%31s %7s %15s %u %u %u %7s %7s %x %u %x %x %x %x %llx %c",
            id,form,order,&request,&present,&seed_pending,mode,pc,&masks,&depth,&cc,&flags,&summary,&se,&sig,&extra);
        int rc=parse_mode(mode),precision=parse_pc(pc);
        if(n!=15 || (strcmp(form,"w32") && strcmp(form,"w64")) || (strcmp(order,"scalar") && strcmp(order,"fx"))
            || request>1 || present>1 || seed_pending>1 || rc<0 || precision<0 || masks>63 || depth<1 || depth>8
            || (cc&~0x4700u) || flags>0x7f || ((flags&64) && !(flags&1)) || (summary&~0x8080u)
            || se>0xffff || (se&0x7fff)!=0x3ffc || !(sig>>63)) {
            fprintf(stderr,"line %u: invalid standard XRSTOR input\n",number); return 2;
        }
        int scalar_first=!strcmp(order,"scalar"),wide=!strcmp(form,"w64");
        struct x80 operand,image_operand; struct fxarea seed,before,image,after; struct xsavearea area;
        memset(&seed,0,sizeof seed); memset(&before,0,sizeof before); memset(&image,0,sizeof image);
        memset(&after,0,sizeof after); memset(&area,0,sizeof area);
        pack(&operand,(uint16_t)se,(uint64_t)sig);
        pack(&image_operand,(uint16_t)(se^0x8001u),(uint64_t)sig);
        uint16_t load_cw=(uint16_t)(0x7f|rc|precision);
        __asm__ volatile("fninit\n\tfldcw %0" :: "m"(load_cw) : "memory");
        load_stack(&operand,depth);
        __asm__ volatile("fxsave64 %0" : "=m"(seed) :: "memory");
        uint16_t top=(uint16_t)(((-depth)&7)<<11);
        uint16_t seed_cw=(uint16_t)(load_cw^(seed_pending?1:0));
        uint16_t seed_sw=(uint16_t)(top|(cc^0x4700u)|(seed_pending?0x8081:0));
        put16(seed.b,seed_cw); put16(seed.b+2,seed_sw);
        memcpy(&image,&seed,sizeof image);
        put16(image.b,(uint16_t)(0x40|masks|rc|precision));
        put16(image.b+2,(uint16_t)(top|cc|flags|summary));
        /* Deliberate register/metadata contrast: load, init and skip cannot
         * all masquerade as the same result. The image is never dereferenced
         * through these informational FIP/FDP fields. Both are canonical.
         */
        put16(image.b+6,0x05a5);
        uint64_t ip=UINT64_C(0x0000000123456000),dp=UINT64_C(0x0000000234567000);
        memcpy(image.b+8,&ip,8); memcpy(image.b+16,&dp,8);
        memcpy(image.b+32,image_operand.b,10);
        memcpy(area.b,image.b,sizeof image.b);
        uint64_t state=present; memcpy(area.b+512,&state,8);
        /* XCOMP_BV and all reserved header bytes remain zero. EDX:EAX is
         * exactly 0 or 1, so no SSE, AVX, PKRU or supervisor state is requested.
         * Both pointers, the complete header and destination storage are valid
         * before establishing the possibly pending seed.
         */
        uint16_t scalar_sw=0,scalar_cw=0;
        restore_fx(&seed);
        __asm__ volatile("fxsave64 %0" : "=m"(before) :: "memory");
        if(wide) h1685_xrstor64(&area,request);
        else h1685_xrstor32(&area,request);
        if(scalar_first) h1678_scalar_first(&after,&scalar_sw,&scalar_cw);
        else h1678_fx_first(&after,&scalar_sw,&scalar_cw);
        printf("CASE=%s FORM=%s ORDER=%s REQUEST=%u PRESENT=%u SEED_PENDING=%u MODE=%s PC=%s MASKS=%02x DEPTH=%u CC=%04x FLAGS=%02x SUMMARY=%04x SCALAR_CW=%04x SCALAR_SW=%04x XSTATE=%016llx XCOMP=%016llx",
            id,form,order,request,present,seed_pending,mode,pc,masks,depth,cc,flags,summary,scalar_cw,scalar_sw,
            (unsigned long long)u64(area.b+512),(unsigned long long)u64(area.b+520));
        print_fx("B",&before); print_fx("I",&image); print_fx("A",&after); putchar('\n');
    }
    __asm__ volatile("fninit" ::: "memory");
    return ferror(stdin)?4:0;
}

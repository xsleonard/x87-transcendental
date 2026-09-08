/* Analysis-only counterpart of H1578 for both equality thresholds.
 * Validate its complete output against independent constant-tap binaries
 * before admitting its endpoints to a hardware-blind candidate bank.
 */
static unsigned h1585_tap;
#define G_ROUND84 0
#define G_R99TAPS (1 + h1585_tap)
#define main h1585_original_model_main
#include "../src/fsincos_skylake.c"
#undef main

int main(void)
{
    char line[1024];unsigned long long count=0,visible=0;
    const sf_rc_t modes[3]={SF_RN,SF_RD,SF_RU};
    const char *names[3]={"rn","rd","ru"};
    g_fcos_standalone_path=1;
    while(fgets(line,sizeof line,stdin)) {
        if(!strncmp(line,"operand\t",8))continue;
        unsigned se,anchor,tap;int offset;unsigned long long sig;
        if(sscanf(line,"%x %llx\t%u\t%d\t%u",&se,&sig,&anchor,&offset,&tap)!=5
           ||se!=0x3ffc||(tap!=1&&tap!=2))return 2;
        x80_t input={.se=(uint16_t)se,.sig=(uint64_t)sig};++count;
        for(unsigned i=0;i<3;++i) {
            x80_t strict,inclusive;
            h1585_tap=tap==1?0:1;
            if(fcos_ref(input,&strict,modes[i])!=FSINCOS_OK)return 3;
            h1585_tap=tap==1?1:3;
            if(fcos_ref(input,&inclusive,modes[i])!=FSINCOS_OK)return 3;
            if(strict.se!=inclusive.se||strict.sig!=inclusive.sig) {
                printf("%04x %016llx\t%u\t%s\t%04x:%016llx\t%04x:%016llx\n",se,sig,tap,names[i],
                       strict.se,(unsigned long long)strict.sig,inclusive.se,(unsigned long long)inclusive.sig);
                ++visible;
            }
        }
    }
    if(ferror(stdin))return 4;
    fprintf(stderr,"input_rows=%llu visible_mode_rows=%llu\n",count,visible);
    return 0;
}

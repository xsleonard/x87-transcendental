/* Analysis-only streaming current-source endpoint discriminator.
 * G_R99TAPS's preprocessor condition is true (1 + undefined-identifier->0),
 * while its runtime expression selects exactly the two existing forced-tap
 * configurations 1 and 2.  This avoids retaining millions of Python model
 * outputs.  It must match separately compiled constant-tap binaries before
 * any generated operand is eligible for a hardware manifest.
 */
static unsigned h1578_equality_tap;
#define G_ROUND84 0
#define G_R99TAPS (1 + h1578_equality_tap)
#define main h1578_original_model_main
#include "../src/fsincos_skylake.c"
#undef main

int main(void)
{
    char line[1024];
    unsigned long long rows=0,visible=0;
    const sf_rc_t modes[3]={SF_RN,SF_RD,SF_RU};
    const char *names[3]={"rn","rd","ru"};
    g_fcos_standalone_path=1;
    while(fgets(line,sizeof line,stdin)) {
        if(!strncmp(line,"operand\t",8))continue;
        unsigned se;unsigned long long sig;
        if(sscanf(line,"%x %llx",&se,&sig)!=2||se!=0x3ffc)return 2;
        x80_t in={.se=(uint16_t)se,.sig=(uint64_t)sig};
        ++rows;
        for(unsigned i=0;i<3;++i) {
            x80_t strict,inclusive;
            h1578_equality_tap=0;
            if(fcos_ref(in,&strict,modes[i])!=FSINCOS_OK)return 3;
            h1578_equality_tap=1;
            if(fcos_ref(in,&inclusive,modes[i])!=FSINCOS_OK)return 3;
            if(strict.se!=inclusive.se||strict.sig!=inclusive.sig) {
                printf("%04x %016llx\t%s\t%04x:%016llx\t%04x:%016llx\n",
                       se,sig,names[i],strict.se,(unsigned long long)strict.sig,
                       inclusive.se,(unsigned long long)inclusive.sig);
                ++visible;
            }
        }
    }
    if(ferror(stdin))return 4;
    fprintf(stderr,"input_rows=%llu visible_mode_rows=%llu\n",rows,visible);
    return 0;
}

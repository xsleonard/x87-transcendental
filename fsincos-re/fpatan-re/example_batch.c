/* Batch client using the public library API, independently of the model CLI.
 * Build this file with fpatan_library.c and link GMP. No algorithm flags.
 */
#include "fpatan_library.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    x87_fpatan *ctx=x87_fpatan_create();if(!ctx)return 3;
    char line[256],id[64],mode[4],extra;unsigned pc,ys,xs;uint64_t ym,xm;int result=0;
    while(fgets(line,sizeof(line),stdin)){
        if(sscanf(line,"%63s %3s %u %x %" SCNx64 " %x %" SCNx64 " %c",id,mode,&pc,&ys,&ym,&xs,&xm,&extra)!=7 || ys>65535 || xs>65535){result=2;break;}
        x87_fpatan_round rc;
        if(!strcmp(mode,"rn"))rc=X87_FPATAN_RN;else if(!strcmp(mode,"rd"))rc=X87_FPATAN_RD;
        else if(!strcmp(mode,"ru"))rc=X87_FPATAN_RU;else if(!strcmp(mode,"rz"))rc=X87_FPATAN_RZ;
        else {result=2;break;}
        x87_fpatan_result out;
        if(x87_fpatan_evaluate(ctx,(x87_fpatan_value){(uint16_t)ys,ym},(x87_fpatan_value){(uint16_t)xs,xm},rc,pc,&out)!=X87_FPATAN_OK){result=2;break;}
        printf("%s %04x %016" PRIx64 " %u %02x 00\n",id,out.value.se,out.value.sig,out.c1,out.exceptions);
    }
    x87_fpatan_destroy(ctx);
    return result?result:(ferror(stdin)||fflush(stdout)?3:0);
}

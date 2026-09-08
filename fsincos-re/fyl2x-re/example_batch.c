/* Batch client using the public library API, independently of the model CLI.
 * Build this file with log_library.c and link GMP. No algorithm flags.
 */
#include "log_library.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    x87_log *ctx=x87_log_create();if(!ctx)return 3;
    char line[256],id[64],op[16],mode[4],extra;unsigned pc,ys,xs;uint64_t ym,xm;int result=0;
    while(fgets(line,sizeof(line),stdin)){
        if(sscanf(line,"%63s %15s %3s %u %x %" SCNx64 " %x %" SCNx64 " %c",id,op,mode,&pc,&ys,&ym,&xs,&xm,&extra)!=8 || ys>65535 || xs>65535){result=2;break;}
        x87_log_round rc;
        if(!strcmp(mode,"rn"))rc=X87_LOG_RN;else if(!strcmp(mode,"rd"))rc=X87_LOG_RD;
        else if(!strcmp(mode,"ru"))rc=X87_LOG_RU;else if(!strcmp(mode,"rz"))rc=X87_LOG_RZ;
        else {result=2;break;}
        x87_log_instruction instruction;
        if(!strcmp(op,"fyl2x"))instruction=X87_FYL2X;
        else if(!strcmp(op,"fyl2xp1"))instruction=X87_FYL2XP1;
        else {result=2;break;}
        x87_log_result out;
        if(x87_log_evaluate(ctx,instruction,(x87_log_value){(uint16_t)ys,ym},(x87_log_value){(uint16_t)xs,xm},rc,pc,&out)!=X87_LOG_OK){result=2;break;}
        printf("%s %04x %016" PRIx64 " %u %02x 00\n",id,out.value.se,out.value.sig,out.c1,out.exceptions);
    }
    x87_log_destroy(ctx);
    return result?result:(ferror(stdin)||fflush(stdout)?3:0);
}

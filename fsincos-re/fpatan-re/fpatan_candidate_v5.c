/* Unpromoted fixed V5 candidate for fresh prospective validation.
 * No algorithm-selection flags. Includes analysis helpers locally; the final
 * deliverable must fold a validated graph into the single standalone source.
 */
#define main schedule_audit_main
#include "d0008_schedule_audit.c"
#undef main

int main(int argc,char **argv)
{
    (void)argv;
    if(argc!=1)return 2;
    char name[]="fpatan_candidate_v5",policy[]="3";
    char *arguments[]={name,policy,NULL};
    return schedule_audit_main(2,arguments);
}

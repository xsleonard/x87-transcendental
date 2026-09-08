/* H1684: read-only CPUID/XGETBV enumeration, no x87 instruction or capture.
 * Never write XCR0, MSRs, control registers, or any processor state setting.
 * XGETBV is issued only after CPUID confirms OSXSAVE and XSAVE support.
 */
#if !defined(__x86_64__) || !defined(__linux__)
#error "H1684 expects the authorized Linux x86-64 research host"
#endif
#include <cpuid.h>
#include <stdint.h>
#include <stdio.h>

static void leaf(unsigned function,unsigned subleaf)
{
    unsigned a,b,c,d;
    __cpuid_count(function,subleaf,a,b,c,d);
    printf("LEAF=%08x SUBLEAF=%08x EAX=%08x EBX=%08x ECX=%08x EDX=%08x\n",
        function,subleaf,a,b,c,d);
}

int main(void)
{
    unsigned a,b,c,d,max=__get_cpuid_max(0,0);
    leaf(0,0);
    if(max<1) return 2;
    __cpuid_count(1,0,a,b,c,d); leaf(1,0);
    if(max>=7) leaf(7,0);
    if((c&((1u<<26)|(1u<<27)))!=((1u<<26)|(1u<<27)) || max<0x0d) {
        puts("XGETBV=NOT_EXECUTED REASON=XSAVE_OR_OSXSAVE_UNAVAILABLE"); return 0;
    }
    unsigned low,high;
    __asm__ volatile("xgetbv" : "=a"(low),"=d"(high) : "c"(0));
    printf("XCR0=%08x%08x\n",high,low);
    leaf(0x0d,0); leaf(0x0d,1);
    __cpuid_count(0x0d,0,a,b,c,d); uint64_t users=((uint64_t)d<<32)|a;
    __cpuid_count(0x0d,1,a,b,c,d); uint64_t supervisors=((uint64_t)d<<32)|c;
    for(unsigned bit=2;bit<63;bit++) if((users|supervisors)&(UINT64_C(1)<<bit)) leaf(0x0d,bit);
    return 0;
}

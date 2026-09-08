/* H1667: one-attempt FSIN/FCOS capture with independently injected ES/B.
 *
 * Input: case insn mode pc masks_hex depth cc_hex flags_hex summary_hex empty se sig
 * Load under all masks, restore the specified prestate, record ES/B restoration,
 * attempt ONE transcendental, FXSAVE before FWAIT, then observe SIGFPE context.
 * A fault at the transcendental (old pending exception) skips that instruction;
 * a fault at FWAIT skips the wait. Neither instruction is ever retried.
 * No warmup, timing, selftest or automatic restart. Inputs require a fresh,
 * immutable audited manifest and the ordinary once-only campaign guard.
 * Requested ES/B need not be coherent with flags/masks. Record their actual
 * restored values before attempting FSIN/FCOS; do not call normalization a
 * successful inconsistent-state execution. Other prestate fields must match.
 * This harness is NOT permission to recapture old tuples with new state fields.
 */
#define _GNU_SOURCE
#if !defined(__linux__) || !defined(__x86_64__)
#error "H1667 requires the authorized Linux x86-64 research host"
#endif
#include <signal.h>
#include <stddef.h>
#include <ucontext.h>
#include <unistd.h>

#define main h1400_archived_main_not_used
#include "x87_state_capture.c"
#undef main

_Static_assert(sizeof(struct _libc_fpstate) == 512, "Unexpected signal FP state size");
_Static_assert(offsetof(struct _libc_fpstate, swd) == 2, "Unexpected SW offset");
_Static_assert(offsetof(struct _libc_fpstate, _st) == 32, "Unexpected ST offset");

volatile sig_atomic_t h1667_after_valid;
static volatile sig_atomic_t armed, fault_seen, fault_kind, fault_code, fault_trap;
static volatile uintptr_t expected_site, expected_wait, expected_resume;
static volatile struct fxsave_area fault_state;

extern void h1667_once_sin(struct fxsave_area *);
extern void h1667_once_cos(struct fxsave_area *);
extern unsigned char h1667_sin_site[], h1667_sin_wait[], h1667_sin_resume[];
extern unsigned char h1667_cos_site[], h1667_cos_wait[], h1667_cos_resume[];

/* Fixed assembler labels make fault attribution/recovery auditable. There is
 * no back-edge, no retry and no other x87 arithmetic between observation cuts.
 * The first no-wait snapshot precedes the deliberate exception-delivery point.
 */
__asm__(
    ".text\n"
    ".p2align 4\n"
    ".globl h1667_once_sin,h1667_sin_site,h1667_sin_wait,h1667_sin_resume\n"
    ".type h1667_once_sin,@function\n"
    "h1667_once_sin:\n"
    "h1667_sin_site:\n\tfsin\n\tfxsave64 (%rdi)\n"
    "\tmovl $1,h1667_after_valid(%rip)\n"
    "h1667_sin_wait:\n\tfwait\n"
    "h1667_sin_resume:\n\tfnclex\n\tret\n"
    ".size h1667_once_sin,.-h1667_once_sin\n"
    ".p2align 4\n"
    ".globl h1667_once_cos,h1667_cos_site,h1667_cos_wait,h1667_cos_resume\n"
    ".type h1667_once_cos,@function\n"
    "h1667_once_cos:\n"
    "h1667_cos_site:\n\tfcos\n\tfxsave64 (%rdi)\n"
    "\tmovl $1,h1667_after_valid(%rip)\n"
    "h1667_cos_wait:\n\tfwait\n"
    "h1667_cos_resume:\n\tfnclex\n\tret\n"
    ".size h1667_once_cos,.-h1667_once_cos\n"
);

static void catch_fpe(int signo, siginfo_t *info, void *context)
{
    ucontext_t *uc = context;
    uintptr_t rip = (uintptr_t)uc->uc_mcontext.gregs[REG_RIP];
    if (signo != SIGFPE || !armed || fault_seen || !uc->uc_mcontext.fpregs)
        _exit(90);
    if (rip == expected_site) fault_kind = 1;
    else if (rip == expected_wait) fault_kind = 2;
    else _exit(91);
    /* Volatile byte copy prevents vectorization/library calls in the handler.
     * Preserve the kernel-provided fault context BEFORE clearing its exceptions
     * solely for safe return. That repaired context is not scored as hardware.
     */
    volatile const unsigned char *source = (const unsigned char *)uc->uc_mcontext.fpregs;
    for (size_t i = 0; i < sizeof fault_state.bytes; ++i)
        fault_state.bytes[i] = source[i];
    fault_code = info->si_code;
    fault_trap = (sig_atomic_t)uc->uc_mcontext.gregs[REG_TRAPNO];
    fault_seen = 1;
    uc->uc_mcontext.fpregs->swd &= 0x7f00u;
    uc->uc_mcontext.fpregs->cwd |= 0x003fu;
    uc->uc_mcontext.gregs[REG_RIP] = (greg_t)expected_resume;
}

static void snapshot64(struct fxsave_area *area)
{
    memset(area, 0, sizeof *area);
    __asm__ volatile("fxsave64 %0" : "=m" (*area) :: "memory");
}

static void restore64(const struct fxsave_area *area)
{
    /* The seed includes SSE state: declare all restored registers clobbered. */
    __asm__ volatile("fxrstor64 %0" :: "m" (*area) :
        "memory", "st", "st(1)", "st(2)", "st(3)", "st(4)", "st(5)", "st(6)", "st(7)",
        "xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7",
        "xmm8", "xmm9", "xmm10", "xmm11", "xmm12", "xmm13", "xmm14", "xmm15");
}

static void print_extended(const char *label, const struct fxsave_area *area)
{
    print_area(label, area);
    printf(" %s_FOP=%04x %s_FIP=%016llx %s_FDP=%016llx", label,
           load_u16(area->bytes + 6), label, (unsigned long long)load_u64(area->bytes + 8),
           label, (unsigned long long)load_u64(area->bytes + 16));
}

int main(void)
{
    struct sigaction action;
    memset(&action, 0, sizeof action);
    action.sa_sigaction = catch_fpe;
    action.sa_flags = SA_SIGINFO;
    if (sigemptyset(&action.sa_mask) || sigaction(SIGFPE, &action, NULL)) return 2;
    char line[512];
    unsigned line_number = 0;
    while (fgets(line, sizeof line, stdin)) {
        char case_id[32], instruction[16], mode[8], precision[8], extra;
        unsigned masks, depth, cc, flags, summary, empty, se;
        unsigned long long sig;
        ++line_number;
        if (line[0] == '#' || line[0] == '\n') continue;
        int fields = sscanf(line, "%31s %15s %7s %7s %x %u %x %x %x %u %x %llx %c",
            case_id, instruction, mode, precision, &masks, &depth, &cc, &flags,
            &summary, &empty, &se, &sig, &extra);
        uint16_t rc_bits, pc_bits;
        if (fields != 12 || (strcmp(instruction, "fsin") && strcmp(instruction, "fcos"))
            || !parse_mode(mode, &rc_bits) || !parse_precision(precision, &pc_bits)
            || masks > 0x3f || depth < 1 || depth > 8 || empty > 1 || (summary & ~0x8080u) || se > 0xffff
            || (cc & ~0x4700u) || (flags & ~0x007fu) || ((flags & 0x40) && !(flags & 1))) {
            fprintf(stderr, "line %u: invalid exception-transition input\n", line_number);
            return 2;
        }
        uint16_t load_cw = (uint16_t)(0x007f | rc_bits | pc_bits);
        uint16_t cw = (uint16_t)(0x0040 | masks | rc_bits | pc_bits);
        struct x80mem operand;
        struct fxsave_area seed, before, after, delivered;
        memset(&after, 0, sizeof after);
        memset(&delivered, 0, sizeof delivered);
        pack_x80((uint16_t)se, (uint64_t)sig, &operand);
        __asm__ volatile("fninit\n\tfldcw %0" :: "m" (load_cw) : "memory");
        load_stack(&operand, (int)depth);
        snapshot64(&seed);
        unsigned top = (load_u16(seed.bytes + 2) >> 11) & 7;
        uint16_t sw = (uint16_t)((top << 11) | cc | flags | summary);
        memcpy(seed.bytes, &cw, sizeof cw);
        memcpy(seed.bytes + 2, &sw, sizeof sw);
        if (empty) seed.bytes[4] &= (unsigned char)~(1u << top);
        restore64(&seed);
        snapshot64(&before);
        /* Abort before the instruction if FXRSTOR did not establish the exact
         * specified input apart from the two summary bits under investigation.
         * No failed row is silently repaired or retried. Requested SW is
         * printed separately; actual restored ES/B are observations, not edits. */
        if (load_u16(before.bytes) != cw || ((load_u16(before.bytes + 2) ^ sw) & ~0x8080u)
            || before.bytes[4] != seed.bytes[4]
            || memcmp(before.bytes + 32, seed.bytes + 32, 10)) {
            __asm__ volatile("fnclex" ::: "memory");
            fprintf(stderr, "line %u: requested prestate was not restored\n", line_number);
            return 3;
        }
        fault_seen = fault_kind = fault_code = fault_trap = h1667_after_valid = 0;
        if (!strcmp(instruction, "fsin")) {
            expected_site = (uintptr_t)h1667_sin_site;
            expected_wait = (uintptr_t)h1667_sin_wait;
            expected_resume = (uintptr_t)h1667_sin_resume;
            armed = 1;
            h1667_once_sin(&after);
        } else {
            expected_site = (uintptr_t)h1667_cos_site;
            expected_wait = (uintptr_t)h1667_cos_wait;
            expected_resume = (uintptr_t)h1667_cos_resume;
            armed = 1;
            h1667_once_cos(&after);
        }
        armed = 0;
        if (fault_seen) {
            for (size_t i = 0; i < sizeof delivered.bytes; ++i)
                delivered.bytes[i] = fault_state.bytes[i];
        }
        printf("CASE=%s INSN=%s MODE=%s PC=%s MASKS=%02x DEPTH=%u CC=%04x FLAGS=%02x SUMMARY=%04x EMPTY=%u REQ_SW=%04x"
               " A_VALID=%d FAULT=%d FAULT_AT=%d SI_CODE=%d TRAP=%d",
            case_id, instruction, mode, precision, masks, depth, cc, flags, summary, empty, sw,
            h1667_after_valid, fault_seen, fault_kind, fault_code, fault_trap);
        print_extended("B", &before);
        print_extended("A", &after);
        print_extended("F", &delivered);
        putchar('\n');
    }
    __asm__ volatile("fninit" ::: "memory");
    return ferror(stdin) ? 4 : 0;
}

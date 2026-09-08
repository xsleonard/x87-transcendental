/* Pentium FPU ROM constants (Shirriff decode, righto.com 2025-01),
 * with two silicon-verified single-bit corrections: row 186 cos(44/64)
 * sig bit 43, row 189 cos(18/64) sig bit 12 (article-appendix
 * transcription errors; hardware matches the corrected values).
 * p5c_t: value = (-1)^sign * sig68 * 2^exp2  (sig68 up to 68 bits). */
typedef struct { uint8_t sign; int32_t exp2; unsigned __int128 sig; } p5c_t;
#define P5C(s, e, hi17) { (s), (e), (unsigned __int128)(hi17) }
static const p5c_t P5S6_1 = { 1, -69, ((unsigned __int128)0x5ull<<64)|0x5555555555555555ull };
static const p5c_t P5S6_2 = { 0, -73, ((unsigned __int128)0x4ull<<64)|0x4444444444443e35ull };
static const p5c_t P5S6_3 = { 1, -79, ((unsigned __int128)0x6ull<<64)|0x806806806773c774ull };
static const p5c_t P5S6_4 = { 0, -85, ((unsigned __int128)0x5ull<<64)|0xc778e94f50956d70ull };
static const p5c_t P5S6_5 = { 1, -92, ((unsigned __int128)0x6ull<<64)|0xb991122efa0532f0ull };
static const p5c_t P5S6_6 = { 0, -99, ((unsigned __int128)0x5ull<<64)|0x8303f02614d5e4d8ull };
static const p5c_t P5C6_1 = { 1, -68, ((unsigned __int128)0x7ull<<64)|0xfffffffffffffffeull };
static const p5c_t P5C6_2 = { 0, -71, ((unsigned __int128)0x5ull<<64)|0x5555555555554277ull };
static const p5c_t P5C6_3 = { 1, -76, ((unsigned __int128)0x5ull<<64)|0xb05b05b05a18a1baull };
static const p5c_t P5C6_4 = { 0, -82, ((unsigned __int128)0x6ull<<64)|0x80680675b559f2cfull };
static const p5c_t P5C6_5 = { 1, -88, ((unsigned __int128)0x4ull<<64)|0x9f93af61f5349300ull };
static const p5c_t P5C6_6 = { 0, -95, ((unsigned __int128)0x4ull<<64)|0x7a4f2483514c1af8ull };
static const p5c_t P5S4_1 = { 1, -69, ((unsigned __int128)0x5ull<<64)|0x5555555555555445ull };
static const p5c_t P5S4_2 = { 0, -73, ((unsigned __int128)0x4ull<<64)|0x4444444443a3fdb6ull };
static const p5c_t P5S4_3 = { 1, -79, ((unsigned __int128)0x6ull<<64)|0x8068060b2044e9aeull };
static const p5c_t P5S4_4 = { 0, -85, ((unsigned __int128)0x5ull<<64)|0xd75716e60f321240ull };
static const p5c_t P5C4_1 = { 1, -68, ((unsigned __int128)0x7ull<<64)|0xfffffffffffffa28ull };
static const p5c_t P5C4_2 = { 0, -71, ((unsigned __int128)0x5ull<<64)|0x55555555539cfae6ull };
static const p5c_t P5C4_3 = { 1, -76, ((unsigned __int128)0x5ull<<64)|0xb05b050f31b2e713ull };
static const p5c_t P5C4_4 = { 0, -82, ((unsigned __int128)0x6ull<<64)|0x803988d56e3bff10ull };
static const struct { int b; p5c_t sinT, cosT; } P5TAB[8] = {
    { 18, { 0, -68, ((unsigned __int128)0x4ull<<64)|0x70df5931ae1d9460ull }, { 0, -67, ((unsigned __int128)0x7ull<<64)|0xaf8853ddbbe9efd0ull } },
    { 22, { 0, -68, ((unsigned __int128)0x5ull<<64)|0x646f27e8bd65cbe4ull }, { 0, -67, ((unsigned __int128)0x7ull<<64)|0x882fd26b35b03d34ull } },
    { 26, { 0, -68, ((unsigned __int128)0x6ull<<64)|0x529afa7d51b12963ull }, { 0, -67, ((unsigned __int128)0x7ull<<64)|0x594fc1cf900fe89eull } },
    { 30, { 0, -68, ((unsigned __int128)0x7ull<<64)|0x3a74b8f52947b682ull }, { 0, -67, ((unsigned __int128)0x7ull<<64)|0x2316fe3386a10d5aull } },
    { 36, { 0, -67, ((unsigned __int128)0x4ull<<64)|0x4434312da70edd92ull }, { 0, -67, ((unsigned __int128)0x6ull<<64)|0xc4741058a93188efull } },
    { 44, { 0, -67, ((unsigned __int128)0x5ull<<64)|0x13ace073ce1aac13ull }, { 0, -67, ((unsigned __int128)0x6ull<<64)|0x2ec4169772401864ull } },
    { 52, { 0, -67, ((unsigned __int128)0x5ull<<64)|0xcedda037a95df6eeull }, { 0, -67, ((unsigned __int128)0x5ull<<64)|0x806149bd58f7d46dull } },
    { 60, { 0, -67, ((unsigned __int128)0x6ull<<64)|0x72daa6ef3992b586ull }, { 0, -67, ((unsigned __int128)0x4ull<<64)|0xbc044c9908390c72ull } },
};

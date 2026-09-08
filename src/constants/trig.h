#ifndef X87TRANS_TRIG_CONSTANTS_H
#define X87TRANS_TRIG_CONSTANTS_H
#include <stdint.h>
/* Pentium FPU ROM constants (Shirriff decode, righto.com 2025-01),
 * with two silicon-verified single-bit corrections: row 186 cos(44/64)
 * sig bit 43, row 189 cos(18/64) sig bit 12 (article-appendix
 * transcription errors; hardware matches the corrected values).
 * p5c_t: value = (-1)^sign * sig68 * 2^exp2  (sig68 up to 68 bits). */
typedef struct {
    uint8_t sign;
    int32_t exp2;
    unsigned __int128 sig;
} p5c_t;
typedef struct {
    int b;
    p5c_t sinT, cosT;
} trig_table_entry;
extern const p5c_t P5S6_1;
extern const p5c_t P5S6_2;
extern const p5c_t P5S6_3;
extern const p5c_t P5S6_4;
extern const p5c_t P5S6_5;
extern const p5c_t P5S6_6;
extern const p5c_t P5C6_1;
extern const p5c_t P5C6_2;
extern const p5c_t P5C6_3;
extern const p5c_t P5C6_4;
extern const p5c_t P5C6_5;
extern const p5c_t P5C6_6;
extern const p5c_t P5S4_1;
extern const p5c_t P5S4_2;
extern const p5c_t P5S4_3;
extern const p5c_t P5S4_4;
extern const p5c_t P5C4_1;
extern const p5c_t P5C4_2;
extern const p5c_t P5C4_3;
extern const p5c_t P5C4_4;
extern const trig_table_entry P5TAB[8];
#endif

/* Literal P5 ROM data, not coefficients fitted to our FPATAN captures.
 * Source: Ken Shirriff, "Pi in the Pentium", January 2025, ROM appendix:
 * https://www.righto.com/2025/01/pentium-floating-point-ROM.html
 * Local transcription: ../data/pentium-rom/rom-constants.tsv.
 *
 * Each entry preserves the published row index, sign and significand bits.
 * Its exact value is (-1)^sign * integer(sig, 16) * 2^scale, where
 * scale = published_exponent - 0x0ffff - 66. All selected flag bits are zero.
 * The 67-bit significand is stored as a hex string to avoid a 64-bit cut.
 *
 * This is a physical decode of a P5 ROM, not a dump of the Skylake ROM.
 * Use in this Skylake reconstruction is supported by the retained captures.
 */
static const struct {
    int index, sign, scale;
    const char *sig;
} constants[] = {
    /* Quadrant-restoration constants: pi and pi/2. */
    {19, 0, -65, "6487ed5110b4611a6"},
    {20, 0, -66, "6487ed5110b4611a6"},
    /* Short polynomial: z^3, z^5, z^7 and z^9 coefficients. */
    {114, 1, -68, "555555555555535f0"},
    {115, 0, -69, "6666666664208b016"},
    {116, 1, -69, "492491e0653ac37b8"},
    {117, 0, -70, "71b83f4133889b2f0"},
    /* Long polynomial: z^3 through z^13, in ascending odd powers. */
    {118, 1, -68, "55555555555555543"},
    {119, 0, -69, "66666666666616b73"},
    {120, 1, -69, "4924924920fca4493"},
    {121, 0, -70, "71c71c4be6f662c91"},
    {122, 1, -70, "5d16e0bde0b12eee8"},
    {123, 0, -70, "4e403be3e3c725aa0"},
    /* Table anchors: atan(n/32), n = 1..32, at ROM index 124 + n.
     * The fixed V7 table path selects n >= 2; row 125 is retained as data.
     */
    {125, 0, -72, "7ff556eea5d892a14"},
    {126, 0, -71, "7fd56edcb3f7a71b6"},
    {127, 0, -70, "5fb860980bc43a305"},
    {128, 0, -70, "7f56ea6ab0bdb7196"},
    {129, 0, -69, "4f5bbba31989b161a"},
    {130, 0, -69, "5ee5ed2f396c089a4"},
    {131, 0, -69, "6e435d4a498288118"},
    {132, 0, -69, "7d6dd7e4b203758ab"},
    {133, 0, -68, "462fd68c2fc5e0986"},
    {134, 0, -68, "4d89dcdc1faf2f34e"},
    {135, 0, -68, "54c2b6654735276d5"},
    {136, 0, -68, "5bd86507937bc239c"},
    {137, 0, -68, "62c934e5286c95b6d"},
    {138, 0, -68, "6993bb0f308ff2db2"},
    {139, 0, -68, "7036d3253b27be33e"},
    {140, 0, -68, "76b19c1586ed3da2b"},
    {141, 0, -68, "7d03742d50505f2e3"},
    {142, 0, -67, "4195fa536cc33f152"},
    {143, 0, -67, "4495766fef4aa3da8"},
    {144, 0, -67, "47802eaf7bfacfcdb"},
    {145, 0, -67, "4a563964c238c37b1"},
    {146, 0, -67, "4d17c07338deed102"},
    {147, 0, -67, "4fc4fee27a5bd0f68"},
    {148, 0, -67, "525e3e8c9a7b84921"},
    {149, 0, -67, "54e3d5ee24187ae45"},
    {150, 0, -67, "5756261c5a6c60401"},
    {151, 0, -67, "59b598e48f821b48b"},
    {152, 0, -67, "5c029f15e118cf39e"},
    {153, 0, -67, "5e3daef574c579407"},
    {154, 0, -67, "606742dc562933204"},
    {155, 0, -67, "627fd7fd5fc7deaa4"},
    {156, 0, -67, "6487ed5110b4611a6"},
};

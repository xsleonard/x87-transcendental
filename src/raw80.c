/* Raw operands are classified before any numerical normalization. */
#include "internal/api.h"

raw_class x87t_internal_raw80_classify(x87t_raw80 v)
{
    unsigned exponent = v.se & 0x7fff;
    if (!exponent) {
        if (!v.sig)
            return RAW_ZERO;
        return v.sig >> 63 ? RAW_PSEUDO : RAW_DENORMAL;
    }
    if (!(v.sig >> 63))
        return RAW_UNSUPPORTED;
    if (exponent != 0x7fff)
        return RAW_NORMAL;
    if (v.sig == (UINT64_C(1) << 63))
        return RAW_INFINITY;
    return v.sig & (UINT64_C(1) << 62) ? RAW_QNAN : RAW_SNAN;
}

uint8_t x87t_internal_trig_flags(x87t_raw80 x, int range_return, int sine_component)
{
    /* Use the original encoding, before normalization. Set PE for a finite
     * nonzero input when the instruction completes, regardless of whether
     * its internal products were exact. Denormals and pseudo-denormals set
     * DE. Only true denormals set UE for sine or tangent; FCOS passes
     * sine_component=0. Handle special encodings before checking C2. */
    raw_class kind = x87t_internal_raw80_classify(x);
    if (kind == RAW_UNSUPPORTED || kind == RAW_SNAN || kind == RAW_INFINITY)
        return X87T_IE;
    if (kind == RAW_QNAN || kind == RAW_ZERO || range_return)
        return 0;
    return X87T_PE | ((kind == RAW_DENORMAL || kind == RAW_PSEUDO) ? X87T_DE : 0) |
           ((sine_component && kind == RAW_DENORMAL) ? X87T_UE : 0);
}

/* The extreme-tiny trig bypass retains the input exactly. Its unmasked
 * underflow endpoint is input * 2^24576, not a scaled rounded approximation.
 * H1656/H1659 establish this endpoint for standalone FSIN. */
void x87t_internal_wrap_trig_underflow(x87t_raw80 x, x87t_result *result,
                                     const x87t_control *control)
{
    if (!(result->exceptions & X87T_UE) || (control->exception_masks & X87T_UE))
        return;
    unsigned shift = 0;
    while (!(x.sig >> 63)) {
        x.sig <<= 1;
        ++shift;
    }
    x.se = (uint16_t)((x.se & 0x8000) | (24577 - shift));
    result->primary = x;
}

x87t_raw80 x87t_load_le(const uint8_t bytes[10])
{
    x87t_raw80 value = {(uint16_t)(bytes[8] | (uint16_t)bytes[9] << 8), 0};
    for (unsigned i = 0; i < 8; ++i)
        value.sig |= (uint64_t)bytes[i] << (8 * i);
    return value;
}

void x87t_store_le(uint8_t bytes[10], x87t_raw80 value)
{
    for (unsigned i = 0; i < 8; ++i)
        bytes[i] = (uint8_t)(value.sig >> (8 * i));
    bytes[8] = (uint8_t)value.se;
    bytes[9] = (uint8_t)(value.se >> 8);
}

/* Raw operands are classified before any numerical normalization. */
#include "internal/api.h"

raw_class raw80_classify(x87t_raw80 v)
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

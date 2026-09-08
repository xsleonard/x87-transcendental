"""Read numerical x87 capture rows for offline experiments."""

from __future__ import annotations

from p6_arithmetic import ExactFP, p6_from_exact
from p6_value import P6Value

PI_OVER_FOUR_SIGNIFICAND = 0xC90FDAA22168C234
PI_OVER_TWO_M66 = (3 << 64) | 0x243F6A8885A308D3

ROUNDING_MODES = ("rn", "rd", "ru")
CONDITION_C1 = 0x0200


def parse_capture(
    line: str, function: str
) -> tuple[tuple[int, int], int] | None:
    fields = line.split()
    if len(fields) == 3 and fields[0] == "C2" and fields[1] == "SW":
        return None
    if len(fields) == 5 and fields[0] == "OK" and fields[3] == "SW":
        return (int(fields[1], 16), int(fields[2], 16)), int(fields[4], 16)
    if len(fields) == 7 and fields[0] == "OK" and fields[5] == "SW":
        offset = 1 if function == "sin" else 3
        return (
            (int(fields[offset], 16), int(fields[offset + 1], 16)),
            int(fields[6], 16),
        )
    raise ValueError(line)



def direct_region(sign_exponent: int, significand: int) -> str | None:
    exponent = (sign_exponent & 0x7FFF) - 0x3FFF
    if not significand or (sign_exponent & 0x7FFF) in (0, 0x7FFF):
        return None
    if -68 <= exponent < -2:
        return "small"
    if exponent < -68:
        return None
    if exponent == -2 or (
        exponent == -1 and significand < PI_OVER_FOUR_SIGNIFICAND
    ):
        return "table"
    if exponent < 63:
        return "reduced"
    return None


def reduced_kernel_state(
    sign_exponent: int, significand: int
) -> tuple[int, P6Value]:
    exponent = (sign_exponent & 0x7FFF) - 0x3FFF
    sign = sign_exponent >> 15
    input_integer = significand << (exponent + 2)
    quotient_magnitude, remainder = divmod(
        input_integer, PI_OVER_TWO_M66
    )
    # The numerical model centers a strict upper-half remainder. Equality stays
    # in the positive half; for external 64-bit inputs and this odd 66-bit
    # modulus an exact half is not representable, but retain the literal rule.
    if (remainder << 1) > PI_OVER_TWO_M66:
        quotient_magnitude += 1
    multiple_integer = quotient_magnitude * PI_OVER_TWO_M66
    residual_sign = int(input_integer < multiple_integer) ^ sign
    magnitude = abs(input_integer - multiple_integer)
    signed_quotient = -quotient_magnitude if sign else quotient_magnitude
    residual = p6_from_exact(ExactFP(residual_sign, magnitude, -65))
    return signed_quotient, residual


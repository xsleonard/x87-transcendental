#!/usr/bin/env python3
"""corpus2_filter: keep only product-boundary-sensitive rows.

Reads /root/corpus2/candidates.txt and traces_all.txt (one trace line per
candidate, from the model's --debug-cosine-carrier flag).  A row is kept
when incrementing the LEFT or RIGHT terminal product by one retained unit
changes the model's final cosine in at least one rounding mode — those
are exactly the rows whose hardware capture can label the conditional
product-increment gates G_L / G_R.  Writes selected_inputs.txt and
selected_traces.txt.
"""

MODES = ("rn", "rd", "ru")


def parse_trace_line(line):
    fields = {}
    for token in line.split()[1:]:
        name, value = token.split("=")
        fields[name] = value
    return fields


def chop_to_67_bits(signed_value, scale):
    negative = signed_value < 0
    magnitude = -signed_value if negative else signed_value
    shift = max(magnitude.bit_length() - 67, 0)
    magnitude >>= shift
    return (-magnitude if negative else magnitude), scale + shift


def final_cosine_result(correction, corr_exponent, mode):
    numerator = (1 << -corr_exponent) + correction
    shift = numerator.bit_length() - 64
    if shift <= 0:
        return numerator << -shift
    kept = numerator >> shift
    remainder = numerator & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    if (mode == "rn" and (remainder > half
                          or (remainder == half and kept & 1))) \
            or (mode == "ru" and remainder):
        kept += 1
    if kept >> 64:
        kept >>= 1
    return kept


def results_for(fields, left_delta, right_delta):
    payload = int(fields["payload"])
    left_e2, right_e2 = int(fields["le2"]), int(fields["re2"])
    left_sig = int(fields["ls"], 16) + left_delta
    right_sig = int(fields["rs"], 16) + right_delta
    left_sign, right_sign = int(fields["lsign"]), int(fields["rsign"])
    scale = min(left_e2, right_e2)
    if payload:
        scale = min(scale, left_e2 - 8)
    accumulator = (-1 if left_sign else 1) * (left_sig << (left_e2 - scale)) \
        + (-1 if right_sign else 1) * (right_sig << (right_e2 - scale))
    if payload:
        accumulator += (-1 if left_sign else 1) \
            * (payload << (left_e2 - 8 - scale))
    corr, corr_e = chop_to_67_bits(accumulator, scale)
    return tuple(final_cosine_result(corr, corr_e, m) for m in MODES)


def main():
    kept_inputs, kept_traces = [], []
    with open("candidates.txt") as cands, open("traces_all.txt") as traces:
        for candidate, trace in zip(cands, traces):
            fields = parse_trace_line(trace)
            if fields.get("active") != "1":
                continue
            plain = results_for(fields, 0, 0)
            if results_for(fields, 0, 1) != plain \
                    or results_for(fields, 1, 0) != plain:
                kept_inputs.append(candidate)
                kept_traces.append(trace)
    with open("selected_inputs.txt", "w") as f:
        f.writelines(kept_inputs)
    with open("selected_traces.txt", "w") as f:
        f.writelines(kept_traces)


if __name__ == "__main__":
    main()

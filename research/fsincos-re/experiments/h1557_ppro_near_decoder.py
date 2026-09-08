#!/usr/bin/env python3
"""Resolve and inspect the strongest corrected Pentium Pro near-decoder.

H1556 found that the exact public CPUID-0x619 CRBUS representation has a
strong, non-random alignment with the published later-P6 decoder, although no
candidate reaches the later-P6 calibration thresholds.  This audit selects
the best *joint* configuration rather than independent field maxima, emits a
complete decoded listing, and checks the three live 0x619 patch hook targets.

Opcode recognition remains a diagnostic against the public later-P6 catalogue;
an unrecognized opcode is not proof of a bad Pentium Pro decode.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path

import numpy as np

import h1490_ppro_core_permutation_transfer as later
import h1493_ppro_serialization_isomorphisms as simple
import h1556_ppro_correct_layout_mapping_audit as corrected


EXPECTED_H1556_SHA256 = (
    "65fbbf326f7a11f4b748b97b05b137091ab64a12beb2fe5514b2cdb35d912cdc"
)
PPRO_BASE = 0x3FAC


ARITHMETIC_NAMES = {
    0x400: "MOVE",
    0x401: "AOP1",
    0x402: "AOP2",
    0x403: "AOP3",
    0x404: "BTEST",
    0x405: "BTS",
    0x406: "BTR",
    0x407: "BTC",
    0x408: "ADD",
    0x409: "OR",
    0x40A: "ADC",
    0x40B: "SBC",
    0x40C: "AND",
    0x40D: "SUB",
    0x40E: "XOR",
    0x40F: "SUBR",
    0x420: "ROL",
    0x421: "ROR",
    0x422: "RCL",
    0x423: "RCR",
    0x424: "SHL",
    0x425: "SHR",
    0x426: "SAL",
    0x427: "SAR",
    0x46F: "WUCONCAT",
}
EXACT_NAMES = {
    0x021: "BSWAP",
    0x022: "FNSTSW?",
    0x024: "FXORS",
    0x02A: "SIGEVENT",
    0x030: "FREADROM",
    0x031: "MOVETOCREG",
    0x032: "MOVEFROMCREG",
    0x033: "WRSEGFLD",
    0x03A: "RDSEGFLD",
    0x090: "TRANSPORTUIP",
    0x0E0: "MERGE",
    0x160: "INTEXTRACT.HI32",
    0x161: "INTEXTRACT.HI16",
    0x1C0: "FLAG_EXTRACT",
    0x1C6: "FLAG_SET",
    0x210: "U_JMP",
    0x212: "M_CALL",
    0x214: "M_JMP_REL",
    0x225: "FSQRT",
    0x226: "FEXAMINE",
    0x22F: "FCOMPARE",
    0x250: "U_JMP_NT",
    0x26B: "FSELECT",
    0x290: "U_JMP_INDIR",
    0x291: "M_RET",
    0x294: "M_JMP",
    0x2D0: "U_JMP_INDIR_N",
    0x414: "BSF",
    0x415: "BSR",
    0x461: "MUL",
    0x463: "IMUL",
    0x464: "DIV",
    0x466: "IDIV",
    0x611: "AAS",
    0x612: "DAA",
    0x613: "DAS",
    0x630: "STRD",
    0x7EB: "FPNORM",
}
CONDITIONAL_NAMES = {
    0x180: "SETcc",
    0x240: "CMOV",
    0x310: "U_JCC_T",
    0x350: "U_JCC_N",
    0x390: "U_JCC_I_T",
    0x3D0: "U_JCC_I_N",
}
MEMORY_NAMES = {
    0x800: "STA",
    0x804: "LOAD",
    0x840: "STA40",
    0x844: "LOAD40",
    0xC00: "LEA",
    0xC03: "PORTOUT",
    0xC05: "PORTIN",
    0xC40: "LEA40",
    0xC43: "PORTOUT40",
    0xC45: "PORTIN40",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def opcode_name(opcode: int) -> str | None:
    arithmetic = opcode & 0xC7F
    if arithmetic in ARITHMETIC_NAMES and (opcode & 0x380) in later.DATA_SIZES:
        return ARITHMETIC_NAMES[arithmetic]
    if opcode in EXACT_NAMES:
        return EXACT_NAMES[opcode]
    conditional = opcode & 0xFF0
    if conditional in CONDITIONAL_NAMES:
        return CONDITIONAL_NAMES[conditional]
    memory = opcode & 0xC4F
    if memory in MEMORY_NAMES and (opcode & 0x380) in later.DATA_SIZES:
        return MEMORY_NAMES[memory]
    return None


def transform_word(value: int, transform) -> int:
    result = 0
    for destination_bit in range(32):
        source_bit = transform(destination_bit)
        result |= ((value >> source_bit) & 1) << destination_bit
    return result


def apply_configuration(words: list[int], configuration: dict[str, object]) -> list[int]:
    transform = simple.TRANSFORMS[configuration["within_dword_transform"]]
    permutation = configuration["candidate_position_to_original_dword"]
    return [transform_word(words[source], transform) for source in permutation]


def decode_rows(
    rows: np.ndarray, configuration: dict[str, object], base: int = PPRO_BASE
) -> list[dict[str, object]]:
    reverse_core = configuration["logical_orientation"] == "published_core"
    result = []
    for group, original in enumerate(rows):
        words = [int(value) for value in original]
        physical = apply_configuration(words, configuration)
        for lane, value in enumerate(later.decode_group(physical, reverse_core)):
            fields = later.decode_fields(value)
            opcode = int(fields["opcode"], 16)
            name = opcode_name(opcode)
            branch_target = (fields["source2"] << 9) | fields["immediate"]
            result.append(
                {
                    "group": group,
                    "lane": lane,
                    "address": f"{base + 4 * group + lane:04X}",
                    **fields,
                    "opcode_name": name,
                    "recognized": name is not None,
                    "branch_target": f"{branch_target:04X}",
                }
            )
    return result


def rank_candidates(rows8: np.ndarray) -> dict[str, object]:
    datasets = np.expand_dims(rows8, 0)
    recognized = np.asarray(
        [later.recognized_opcode(opcode) is not None for opcode in range(4096)],
        dtype=np.uint8,
    )
    best_key = None
    best_count = 0
    best_examples: list[dict[str, object]] = []
    recognition_histogram: Counter[int] = Counter()
    high_recognition_field_ranges: dict[int, dict[str, int]] = {}
    candidate_count = 0

    for reverse_core in (True, False):
        inverse = simple.inverse_core_mapping(reverse_core)
        for transform_name, transform in simple.TRANSFORMS.items():
            contributions = simple.contributions(datasets, inverse, transform)
            for permutation in itertools.permutations(range(8)):
                candidate_count += 1
                selected = simple.selected_fields(contributions, permutation)
                arrays, _ = simple.counts(selected, recognized)
                metrics = {name: int(values[0]) for name, values in arrays.items()}
                recognition_histogram[metrics["recognized_opcodes"]] += 1
                recognized_count = metrics["recognized_opcodes"]
                if recognized_count >= 45:
                    summary = high_recognition_field_ranges.setdefault(
                        recognized_count,
                        {
                            "candidate_count": 0,
                            "flow_zero_min": metrics["flow_zero"],
                            "flow_zero_max": metrics["flow_zero"],
                            "u1_zero_min": metrics["u1_zero"],
                            "u1_zero_max": metrics["u1_zero"],
                            "u2_zero_min": metrics["u2_zero"],
                            "u2_zero_max": metrics["u2_zero"],
                        },
                    )
                    summary["candidate_count"] += 1
                    for field in ("flow_zero", "u1_zero", "u2_zero"):
                        summary[f"{field}_min"] = min(summary[f"{field}_min"], metrics[field])
                        summary[f"{field}_max"] = max(summary[f"{field}_max"], metrics[field])

                # Recognition is the only field with a public old-opcode catalogue
                # interpretation. Break its ties by flow, reserved bit 1, then the
                # later-generation unknown2-zero diagnostic.
                key = (
                    metrics["recognized_opcodes"],
                    metrics["flow_zero"],
                    metrics["u1_zero"],
                    metrics["u2_zero"],
                )
                configuration = simple.configuration(
                    reverse_core, transform_name, permutation
                )
                example = {"configuration": configuration, "metrics": metrics}
                if best_key is None or key > best_key:
                    best_key = key
                    best_count = 1
                    best_examples = [example]
                elif key == best_key:
                    best_count += 1
                    if len(best_examples) < 20:
                        best_examples.append(example)

    expected = 2 * len(simple.TRANSFORMS) * math_factorial_8()
    if candidate_count != expected or not best_examples:
        raise RuntimeError("candidate ranking was incomplete")
    return {
        "candidate_count": candidate_count,
        "ranking": ["recognized_opcodes", "flow_zero", "u1_zero", "u2_zero"],
        "best_key": list(best_key),
        "candidate_count_at_best_key": best_count,
        "best_examples": best_examples,
        "recognition_histogram": {
            str(key): value for key, value in sorted(recognition_histogram.items())
        },
        "high_recognition_field_ranges": {
            str(key): value for key, value in sorted(high_recognition_field_ranges.items())
        },
    }


def math_factorial_8() -> int:
    return 40320


def hook_targets(report1555: dict[str, object]) -> list[dict[str, object]]:
    result = []
    for control in report1555["patches"]["619"]["controls"]:
        if control["address"] not in ("1B8", "1B9", "1BA", "1BB"):
            continue
        value = int(control["value"], 16)
        result.append(
            {
                "register": control["address"],
                "high_half": f"{value >> 16:04X}",
                "low_half": f"{value & 0xFFFF:04X}",
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h1555", required=True, type=Path)
    parser.add_argument("--h1556", required=True, type=Path)
    parser.add_argument("--msrom2scramble-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if digest(arguments.h1556) != EXPECTED_H1556_SHA256:
        raise RuntimeError("unexpected H1556 report hash")
    if digest(arguments.msrom2scramble_source) != corrected.EXPECTED_SOURCE_SHA256:
        raise RuntimeError("unexpected public converter source hash")

    report1555 = json.loads(arguments.h1555.read_text())
    source = arguments.msrom2scramble_source.read_text()
    masks = corrected.parse_c_array(source, "dw_masks_619", 8)
    routes = corrected.parse_c_array(source, "dw_to_crbusrom_619", 32)
    mapping = corrected.recover_public_mapping(masks, routes)
    patch619 = corrected.load_patch_rows(report1555, ("619",))
    rom619_7 = np.asarray(
        [
            corrected.transform_words([int(word) for word in row], mapping, True)
            for row in patch619
        ],
        dtype=np.uint32,
    )
    rom619 = np.column_stack(
        (rom619_7, np.zeros(rom619_7.shape[0], dtype=np.uint32))
    )

    ranking = rank_candidates(rom619)
    canonical = ranking["best_examples"][0]
    listing = decode_rows(rom619, canonical["configuration"])
    hooks = hook_targets(report1555)
    hook_addresses = {
        half
        for hook in hooks
        for half in (hook["high_half"], hook["low_half"])
        if PPRO_BASE <= int(half, 16) <= PPRO_BASE + 4 * GROUPS_SPAN()
    }
    decoded_by_address = {row["address"]: row for row in listing}
    hook_rows = [decoded_by_address[address] for address in sorted(hook_addresses)]
    opcode_histogram = Counter(row["opcode"] for row in listing)
    unknown_histogram = Counter(row["opcode"] for row in listing if not row["recognized"])

    result = {
        "status": "strong_nonrandom_ppro_near_decoder_not_exact",
        "question": (
            "What exact orientation gives H1556's strongest 0x619 alignment, "
            "and do the live patch hook targets decode coherently?"
        ),
        "dependencies": {
            "h1555": {"path": str(arguments.h1555), "sha256": digest(arguments.h1555)},
            "h1556": {"path": str(arguments.h1556), "sha256": digest(arguments.h1556)},
            "utools_msrom2scramble_c": {
                "url": corrected.SOURCE_URL,
                "sha256": digest(arguments.msrom2scramble_source),
            },
        },
        "method": {
            "hardware_executed": False,
            "x87_executed": False,
            "microcode_loaded": False,
            "private_ledger_accessed": False,
            "ranking_is_diagnostic_not_a_decoder_oracle": True,
        },
        "ranking": ranking,
        "canonical_best": canonical,
        "canonical_listing": listing,
        "canonical_summary": {
            "opcode_histogram": dict(sorted(opcode_histogram.items())),
            "unknown_opcode_histogram": dict(sorted(unknown_histogram.items())),
            "recognized": sum(row["recognized"] for row in listing),
            "uops": len(listing),
            "flow_zero": sum(row["flow"] == 0 for row in listing),
            "unknown1_zero": sum(row["unknown1"] == 0 for row in listing),
            "unknown2_zero": sum(row["unknown2"] == 0 for row in listing),
        },
        "hooks": hooks,
        "hook_rows_in_patch_window": hook_rows,
        "conclusion": {
            "nonrandom_structure": True,
            "exact_logical_decoder": False,
            "reason_not_exact": (
                "eleven of 63 opcodes remain outside the current public later-P6 "
                "catalogue, and neither a paired known Pentium Pro logical listing "
                "nor the old-format opcode catalogue/p6scrambler is public"
            ),
            "next_step": (
                "Use known PPro assembly/patch cribs or a public p6scrambler release "
                "to decide whether the eleven opcodes are legitimate old encodings "
                "and to resolve the remaining field permutation"
            ),
            "selector_found": False,
            "emulator_change": False,
            "frontier_closed": False,
        },
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def GROUPS_SPAN() -> int:
    return corrected.GROUPS_PER_PATCH


if __name__ == "__main__":
    main()

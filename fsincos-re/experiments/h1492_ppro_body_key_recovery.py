#!/usr/bin/env python3
"""Audit a separate Pentium Pro body key using exact GF(2) constraints.

H1467 decrypts four old P6 updates as one continuous encrypted stream.  The
first eighteen recovered 0x611 and 0x612 MSRAM groups have physical dword bit
31 clear, while the later 0x617 and 0x619 recoveries do not.  This program
tests the concrete alternative that the MSRAM body uses another key selected
from the public 256-entry FPROM.

For every distinct FPROM value, it solves rather than samples all IVs that
clear bit 31 in physical words 14..157.  It then conjoins the encrypted MSRAM
integrity check by splitting on the exact eight-bit FPROM index.  All cipher
relations are linear over GF(2); no hardware, capture label, or private ledger
is involved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import h1460_unknown_p6_padding_key as old
import h1467_pentium_pro_sibling_patch_recovery as sibling


PREFIX_DWORDS = 18 * 8
BODY_STREAM_STOP = old.MSRAM_INTEGRITY + 1
EXPECTED_PATCH_HASHES = {
    0x611: "3d963b50eef0867008a1c767c514214a21426922c0b02cad0f4848e81d7732df",
    0x612: "b411ab12fca67bef7103ea75c07adc8dbb53b4a966bb619ca32012b26eac7db1",
    0x616: "3b8ad8d55fc1f7fffb46efa77de1dbdc498d5f21d132bedbdeb285bfcb28faaf",
    0x617: "8fa7bcc2d450c2ac810648201a14ce6bcc0883840eb46975fa04ed1dfeabd678",
    0x619: "a513f9c3b37b98550323f7afb257cc08469b1597a0318bb65339b9fedca5921d",
}
EXPECTED_FPROM_HASH = (
    "758ce01ac9a4cbd37c3d847186f1f287a50d1818eb7b213221cc464a43681bb5"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_equation(basis: list[int | None], coefficient: int, rhs: int) -> bool:
    """Add one 32-variable equation, returning False iff it contradicts."""

    row = coefficient | ((rhs & 1) << 32)
    coefficient &= 0xFFFFFFFF
    while coefficient:
        pivot = coefficient.bit_length() - 1
        if basis[pivot] is None:
            basis[pivot] = row
            return True
        row ^= int(basis[pivot])
        coefficient = row & 0xFFFFFFFF
    return not ((row >> 32) & 1)


def solve_basis(basis: list[int | None]) -> tuple[int, tuple[int, ...]]:
    """Return a particular solution and nullspace for a consistent basis."""

    def solve(free_value: int) -> int:
        value = free_value
        for pivot, row in enumerate(basis):
            if row is None:
                continue
            rhs = (row >> 32) & 1
            lower = row & ((1 << pivot) - 1)
            if rhs ^ ((lower & value).bit_count() & 1):
                value |= 1 << pivot
        return value

    particular = solve(0)
    nullspace = tuple(
        solve(1 << bit) ^ particular
        for bit, row in enumerate(basis)
        if row is None
    )
    return particular, nullspace


def coefficient(columns: tuple[int, ...], output_bit: int) -> int:
    return sum(
        ((column >> output_bit) & 1) << input_bit
        for input_bit, column in enumerate(columns)
    )


def linear_state_trace(key: int) -> tuple[tuple[int, ...], ...]:
    """Return the IV-to-state linear map after each body-stream dword."""

    columns = tuple(1 << bit for bit in range(32))
    trace = []
    for _ in range(old.STREAM_START, BODY_STREAM_STOP):
        columns = tuple(old.block_function(column, key) for column in columns)
        trace.append(columns)
    return tuple(trace)


def baseline_body_trace(
    words: tuple[int, ...], key: int
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    state = 0
    last_ciphertext = key
    plaintext = []
    states = []
    for ciphertext in words[old.STREAM_START:BODY_STREAM_STOP]:
        state = old.u32(old.block_function(state, key) ^ ciphertext)
        plaintext.append(old.u32(state ^ last_ciphertext))
        states.append(state)
        last_ciphertext = ciphertext
    return tuple(plaintext), tuple(states)


def add_value_equations(
    basis: list[int | None],
    baseline: int,
    columns: tuple[int, ...],
    target: int,
    width: int,
) -> bool:
    for bit in range(width):
        if not add_equation(
            basis,
            coefficient(columns, bit),
            ((baseline ^ target) >> bit) & 1,
        ):
            return False
    return True


def enumerate_space(
    particular: int, nullspace: tuple[int, ...]
) -> tuple[int, ...]:
    if len(nullspace) > 16:
        raise RuntimeError("unexpectedly large final integrity solution space")
    values = []
    for mask in range(1 << len(nullspace)):
        value = particular
        for bit, vector in enumerate(nullspace):
            if mask & (1 << bit):
                value ^= vector
        values.append(value)
    return tuple(sorted(values))


def decrypt_candidate(
    words: tuple[int, ...], key: int, iv: int
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    state = iv
    last_ciphertext = key
    plaintext = []
    states = []
    for ciphertext in words[old.STREAM_START:BODY_STREAM_STOP]:
        state = old.u32(old.block_function(state, key) ^ ciphertext)
        plaintext.append(old.u32(state ^ last_ciphertext))
        states.append(state)
        last_ciphertext = ciphertext
    return tuple(plaintext), tuple(states)


def solve_patch(
    words: tuple[int, ...],
    keys: tuple[int, ...],
    key_indices: dict[int, tuple[int, ...]],
    fprom: dict[int, int],
    linear_traces: dict[int, tuple[tuple[int, ...], ...]],
) -> dict[str, object]:
    prefix_keys = []
    spaces = []
    rank_histogram: Counter[int] = Counter()
    for key in keys:
        plaintext, states = baseline_body_trace(words, key)
        trace = linear_traces[key]
        prefix_basis: list[int | None] = [None] * 32
        prefix_ok = True
        for relative in range(PREFIX_DWORDS):
            if not add_equation(
                prefix_basis,
                coefficient(trace[relative], 31),
                (plaintext[relative] >> 31) & 1,
            ):
                prefix_ok = False
                break
        if not prefix_ok:
            continue

        prefix_rank = sum(row is not None for row in prefix_basis)
        rank_histogram[prefix_rank] += 1
        prefix_keys.append(key)
        unknown_relative = old.MSRAM_UNKNOWN - old.STREAM_START
        integrity_relative = old.MSRAM_INTEGRITY - old.STREAM_START
        for index in range(256):
            basis = list(prefix_basis)
            if not add_value_equations(
                basis,
                states[unknown_relative] & 0xFF,
                trace[unknown_relative],
                index,
                8,
            ):
                continue
            if not add_value_equations(
                basis,
                plaintext[integrity_relative],
                trace[integrity_relative],
                fprom[index],
                32,
            ):
                continue
            particular, nullspace = solve_basis(basis)
            representatives = enumerate_space(particular, nullspace)
            for iv in representatives:
                candidate_plaintext, candidate_states = decrypt_candidate(
                    words, key, iv
                )
                if any(
                    (word >> 31) & 1
                    for word in candidate_plaintext[:PREFIX_DWORDS]
                ):
                    raise RuntimeError("GF(2) prefix solution failed replay")
                actual_index = candidate_states[unknown_relative] & 0xFF
                if actual_index != index:
                    raise RuntimeError("GF(2) integrity index failed replay")
                if candidate_plaintext[integrity_relative] != fprom[index]:
                    raise RuntimeError("GF(2) integrity value failed replay")
            spaces.append(
                {
                    "key": f"{key:08X}",
                    "fprom_indices_for_key": [
                        f"{item:02X}" for item in key_indices[key]
                    ],
                    "integrity_index": f"{index:02X}",
                    "particular_iv": f"{particular:08X}",
                    "nullspace_basis": [f"{item:08X}" for item in nullspace],
                    "representative_ivs": [
                        f"{item:08X}" for item in representatives
                    ],
                    "representative_count": len(representatives),
                }
            )

    return {
        "fprom_key_count": len(keys),
        "prefix_constraint": {
            "physical_words": [old.STREAM_START, old.STREAM_START + PREFIX_DWORDS - 1],
            "physical_group_count": PREFIX_DWORDS // 8,
            "required_bit": 31,
            "required_value": 0,
        },
        "prefix_sat_key_count": len(prefix_keys),
        "prefix_sat_keys": [f"{key:08X}" for key in prefix_keys],
        "prefix_rank_histogram": {
            str(rank): count for rank, count in sorted(rank_histogram.items())
        },
        "combined_integrity_solution_space_count": len(spaces),
        "combined_integrity_iv_count": sum(
            int(space["representative_count"]) for space in spaces
        ),
        "combined_integrity_solution_spaces": spaces,
        "combined_status": "SAT" if spaces else "UNSAT",
    }


def recovered_bit31_surface(h1467: dict[str, object]) -> dict[str, object]:
    result = {}
    for signature in ("611", "612", "616", "617", "619"):
        recovery = h1467["patches"][signature]["recovery"]
        body = recovery.get("decrypted_body")
        groups = body.get("physical_groups") if body else None
        if not groups:
            result[signature] = {"status": "NO_RECOVERED_BODY"}
            continue
        words = tuple(
            int(word, 16)
            for group in groups
            for word in group["physical_dwords"]
        )
        result[signature] = {
            "status": "RECOVERED_BY_H1467",
            "first_18_groups_bit31_ones": sum(
                (word >> 31) & 1 for word in words[:PREFIX_DWORDS]
            ),
            "all_19_groups_bit31_ones": sum((word >> 31) & 1 for word in words),
            "final_group_bit31_by_dword": [
                (word >> 31) & 1 for word in words[PREFIX_DWORDS:]
            ],
        }
    return result


def build_report(
    patch_paths: tuple[Path, ...], fprom_path: Path, h1467_path: Path
) -> dict[str, object]:
    if len(patch_paths) != len(EXPECTED_PATCH_HASHES):
        raise RuntimeError("provide exactly the five 0x611/612/616/617/619 updates")
    if digest(fprom_path) != EXPECTED_FPROM_HASH:
        raise RuntimeError("public FPROM source hash changed")
    fprom = old.load_fprom(fprom_path)
    key_indices_mutable: dict[int, list[int]] = {}
    for index, key in fprom.items():
        key_indices_mutable.setdefault(key, []).append(index)
    key_indices = {
        key: tuple(indices) for key, indices in key_indices_mutable.items()
    }
    keys = tuple(sorted(key_indices))
    if len(keys) != 208:
        raise RuntimeError(f"expected 208 distinct FPROM values, found {len(keys)}")

    patches: dict[int, tuple[int, ...]] = {}
    sources = {}
    for path in patch_paths:
        data, words = sibling.load_public_patch(path)
        signature = words[3] & 0xFFFF
        actual_hash = hashlib.sha256(data).hexdigest()
        if EXPECTED_PATCH_HASHES.get(signature) != actual_hash:
            raise RuntimeError(f"public patch hash changed for 0x{signature:X}")
        if signature in patches:
            raise RuntimeError(f"duplicate public patch 0x{signature:X}")
        patches[signature] = words
        sources[f"{signature:03X}"] = {
            "input_name": path.name,
            "packed_patch_sha256": actual_hash,
            "public_source_url": sibling.PUBLIC_SOURCES[signature],
        }
    if set(patches) != set(EXPECTED_PATCH_HASHES):
        raise RuntimeError("the five required public patches were not supplied")

    h1467 = json.loads(h1467_path.read_text())
    linear_traces = {key: linear_state_trace(key) for key in keys}
    results = {
        f"{signature:03X}": solve_patch(
            patches[signature], keys, key_indices, fprom, linear_traces
        )
        for signature in sorted(patches)
    }

    positive_controls = {}
    for signature in (0x611, 0x612):
        expected_key = str(h1467["patches"][f"{signature:03X}"]["control_key"])
        expected_ivs = set(
            h1467["patches"][f"{signature:03X}"]["recovery"]
            ["iv_equivalence_class"]["validated_representatives"]
        )
        matching = [
            space
            for space in results[f"{signature:03X}"]
            ["combined_integrity_solution_spaces"]
            if space["key"] == expected_key
        ]
        recovered_ivs = {
            iv for space in matching for iv in space["representative_ivs"]
        }
        positive_controls[f"{signature:03X}"] = {
            "h1467_control_key": expected_key,
            "h1467_validated_ivs": sorted(expected_ivs),
            "h1492_ivs_at_that_key": sorted(recovered_ivs),
            "exact_match": recovered_ivs == expected_ivs,
        }
    if not all(row["exact_match"] for row in positive_controls.values()):
        raise RuntimeError("positive-control recovery failed")

    control_key_crosscheck = {}
    for signature in (0x611, 0x612, 0x616, 0x617, 0x619):
        name = f"{signature:03X}"
        expected_key = str(h1467["patches"][name]["control_key"])
        combined_keys = {
            str(space["key"])
            for space in results[name]["combined_integrity_solution_spaces"]
        }
        control_key_crosscheck[name] = {
            "h1467_control_key": expected_key,
            "prefix_sat": expected_key in results[name]["prefix_sat_keys"],
            "combined_integrity_sat": expected_key in combined_keys,
            "only_prefix_sat_key": (
                results[name]["prefix_sat_keys"] == [expected_key]
            ),
        }

    later_unsat = all(
        results[signature]["combined_status"] == "UNSAT"
        for signature in ("616", "617", "619")
    )
    if not later_unsat:
        raise RuntimeError("expected exact later-stepping UNSAT wall did not reproduce")

    return {
        "query": "pentium_pro_separate_body_key_recovery",
        "status": "positive_controls_exact_later_fp_rom_key_family_unsat",
        "method": {
            "key_domain": "all 208 distinct values in the public 256-entry FPROM",
            "iv_domain": "all 2^32 IVs, represented and solved exactly over GF(2)",
            "structural_constraint": (
                "physical dword bit 31 is zero in old-format words 14..157"
            ),
            "integrity_constraint": (
                "state after word 166 selects the FPROM value decrypted at word 167"
            ),
            "search_character": "exhaustive inside the stated FPROM-key cipher family",
        },
        "sources": sources,
        "dependencies": {
            "fprom_name": fprom_path.name,
            "fprom_sha256": digest(fprom_path),
            "h1467_name": h1467_path.name,
            "h1467_sha256": digest(h1467_path),
            "h1460_source_sha256": digest(Path(old.__file__)),
            "h1467_source_sha256": digest(Path(sibling.__file__)),
        },
        "h1467_recovered_bit31_surface": recovered_bit31_surface(h1467),
        "positive_controls": positive_controls,
        "h1467_control_key_crosscheck": control_key_crosscheck,
        "patch_results": results,
        "conclusion": {
            "confirmed": [
                (
                    "the solver reproduces the exact H1467 0x611 and 0x612 key/IV "
                    "classes as positive controls"
                ),
                (
                    "0x616, 0x617, and 0x619 are UNSAT when the 18-group bit-31 "
                    "wall and encrypted MSRAM integrity are conjoined over every "
                    "public FPROM key value and every IV"
                ),
                (
                    "a separate key from the public FPROM family does not explain "
                    "the later-stepping bit-31 surface"
                ),
            ],
            "not_claimed": [
                "bit 31 is universally reserved across Pentium Pro steppings",
                "the 0x617 or 0x619 H1467 physical plaintext is incorrect",
                "a Pentium Pro physical-to-logical uop mapping",
                "an absolute base-ROM address or R59 selector",
            ],
            "remaining_explanations": [
                "stepping-specific physical metadata or body format",
                "a body key outside the public FPROM value family",
                "another unmodeled pre-body transform",
            ],
        },
        "execution": {
            "hardware": "none",
            "x87_instructions": "none",
            "capture_labels_opened": "none",
            "private_capture_ledger": "not accessed",
            "emulator_change": "none",
            "paper_change": "none",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", action="append", type=Path, required=True)
    parser.add_argument("--fprom-data", type=Path, required=True)
    parser.add_argument("--h1467", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = build_report(
        tuple(arguments.patch), arguments.fprom_data, arguments.h1467
    )
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(text, end="")
        return
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "hardware": "none",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

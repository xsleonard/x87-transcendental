#!/usr/bin/env python3
"""Recover and audit the three previously unsupported public P6 patches.

The public P6 patch cipher has a 32-bit linear state.  Long runs of the two
public inert micro-op encodings provide a physical-layout crib: two adjacent
known plaintext dwords identify the FPROM cipher polynomial without knowing
the IV.  The public IV derivation and all MSRAM/control integrity words then
verify a recovered base key.  No update is loaded and no x87 instruction is
executed.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


SEGMENT_SIZE = 2048
MSRAM_START = 14
MSRAM_DWORDS = 168
MSRAM_INTEGRITY = MSRAM_START + MSRAM_DWORDS
CONTROL_START = MSRAM_INTEGRITY + 2
CONTROL_COUNT = 16
FPROM_ASSIGNMENT = re.compile(
    r"FPROM\[0x([0-9A-Fa-f]+)\]\s*=\s*0x([0-9A-Fa-f]+)"
)
LOGICAL_LINE = re.compile(
    r"^([0-9A-Fa-f]+):\s+([0-9A-Fa-f]{20})\s+"
    r"([0-9A-Fa-f]{20})\s+([0-9A-Fa-f]{20})$"
)
PADDING_WORDS = frozenset(
    {
        int("00060000000000400000", 16),
        int("00060000000000800000", 16),
    }
)

# Public p6tools scramble.py output for every triad made from the two inert
# logical encodings above.  The final five dwords are common to all variants.
PHYSICAL_PADDING_TRIADS = (
    (0x00080000, 0x01000000, 0x20000000, 0, 0x04900000, 0x20020020, 0, 0),
    (0x00080000, 0x01000000, 0x40000000, 0, 0x04900000, 0x20020020, 0, 0),
    (0x00080000, 0x02000000, 0x20000000, 0, 0x04900000, 0x20020020, 0, 0),
    (0x00080000, 0x02000000, 0x40000000, 0, 0x04900000, 0x20020020, 0, 0),
    (0x00100000, 0x01000000, 0x20000000, 0, 0x04900000, 0x20020020, 0, 0),
    (0x00100000, 0x01000000, 0x40000000, 0, 0x04900000, 0x20020020, 0, 0),
    (0x00100000, 0x02000000, 0x20000000, 0, 0x04900000, 0x20020020, 0, 0),
    (0x00100000, 0x02000000, 0x40000000, 0, 0x04900000, 0x20020020, 0, 0),
)

FAMILY_MASK = 0xC7F
FLOATING_FAMILIES = {
    0x468: "fadd",
    0x469: "fmul",
    0x46B: "fnormalize",
    0x46E: "fdivide",
}
ARITH_FLAGS_REGISTER = 0x25
MATCH_CONTROL_REGISTERS = frozenset(range(0x0A8, 0x0B0)) | frozenset(
    range(0x0F0, 0x0F8)
) | frozenset(range(0x1B4, 0x1BC))
PATCH_ADDRESS_MIN = 0x3FAC
PATCH_ADDRESS_MAX = 0x3FFE


@dataclass(frozen=True)
class PaddingSurface:
    key: int
    variant: int
    first_group: int

    @property
    def run_length(self) -> int:
        return 21 - self.first_group


@dataclass(frozen=True)
class ControlWrite:
    address: int
    mask: int
    value: int
    integrity_index: int
    integrity_got: int
    integrity_expected: int

    @property
    def integrity_ok(self) -> bool:
        return self.integrity_got == self.integrity_expected

    def match_hook(self) -> tuple[int, int] | None:
        if self.address not in MATCH_CONTROL_REGISTERS or self.mask != 0:
            return None
        source = (self.value >> 16) & 0x7FFF
        destination = self.value & 0x7FFF
        if not PATCH_ADDRESS_MIN <= destination <= PATCH_ADDRESS_MAX:
            return None
        if destination & 3 == 3:
            return None
        return source, destination


@dataclass(frozen=True)
class LogicalWord:
    address: int
    value: int

    @property
    def opcode(self) -> int:
        return (self.value >> 56) & 0xFFF

    @property
    def source_one(self) -> int:
        return (self.value >> 31) & 0xFF

    @property
    def source_two(self) -> int:
        return (self.value >> 39) & 0xFF

    @property
    def destination(self) -> int:
        return (self.value >> 23) & 0xFF

    @property
    def modifier_u2(self) -> int:
        return (self.value >> 47) & 0x1FF

    @property
    def modifier_u3(self) -> int:
        return (self.value >> 72) & 0xFF

    @property
    def family(self) -> str | None:
        return FLOATING_FAMILIES.get(self.opcode & FAMILY_MASK)


@dataclass(frozen=True)
class Decryption:
    source_name: str
    source_sha256: str
    segment_index: int
    segment_sha256: str
    revision: int
    date: int
    signature: int
    platform_flags: int
    base: int
    key: int
    iv: int
    surface: PaddingSurface
    msram: tuple[int, ...]
    msram_integrity_index: int
    msram_integrity_got: int
    msram_integrity_expected: int
    controls: tuple[ControlWrite, ...]
    logical: tuple[LogicalWord, ...]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def u32(value: int) -> int:
    return value & 0xFFFFFFFF


def rotate_left(value: int, count: int) -> int:
    if not count:
        return value
    return u32((value << count) | (value >> (32 - count)))


def rotate_right(value: int, count: int) -> int:
    if not count:
        return value
    return u32((value >> count) | (value << (32 - count)))


def block_function(plain: int, key: int) -> int:
    state = plain
    for _ in range(37):
        state = (state >> 1) | ((state & 1) << 31)
        if state & 0x80000000:
            state ^= key
    return u32(state ^ plain)


def checked(command: list[str], cwd: Path) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result.stdout


def load_fprom(path: Path) -> dict[int, int]:
    values = {
        int(index, 16): int(value, 16)
        for index, value in FPROM_ASSIGNMENT.findall(path.read_text())
    }
    if set(values) != set(range(256)):
        raise RuntimeError(f"expected public FPROM indices 0x00..0xFF in {path}")
    return values


def parse_header(segment: bytes) -> tuple[int, int, int, int]:
    words = struct.unpack("<512I", segment)
    if words[0] != 1:
        raise RuntimeError(f"unexpected header version {words[0]}")
    if sum(words) & 0xFFFFFFFF:
        raise RuntimeError(f"standard Intel checksum failure: {digest(segment)}")
    return words[1], words[2], words[3], words[6]


def padding_transition_matches(
    ciphertext: tuple[int, ...], group: int, padding: tuple[int, ...], key: int
) -> bool:
    offset = group * 8
    if not offset:
        states = (padding[0] ^ key,) + tuple(
            padding[index] ^ ciphertext[index - 1] for index in range(1, 8)
        )
    else:
        states = tuple(
            padding[index] ^ ciphertext[offset + index - 1]
            for index in range(8)
        )
    return all(
        states[index]
        == u32(block_function(states[index - 1], key) ^ ciphertext[offset + index])
        for index in range(1, 8)
    )


def find_padding_surface(
    words: tuple[int, ...], fprom: dict[int, int]
) -> PaddingSurface:
    ciphertext = words[MSRAM_START : MSRAM_START + MSRAM_DWORDS]
    keys = sorted({fprom[index] for index in range(0x100) if index & ~0x9C == 0})
    candidates = []
    for variant, padding in enumerate(PHYSICAL_PADDING_TRIADS):
        for key in keys:
            matches = {
                group
                for group in range(21)
                if padding_transition_matches(ciphertext, group, padding, key)
            }
            first_group = 21
            while first_group - 1 in matches:
                first_group -= 1
            if first_group < 21:
                candidates.append(PaddingSurface(key, variant, first_group))
    if not candidates:
        raise RuntimeError("no public-padding cipher surface found")
    candidates.sort(key=lambda item: (-item.run_length, item.key, item.variant))
    best = candidates[0]
    if len(candidates) > 1 and candidates[1].run_length == best.run_length:
        raise RuntimeError(f"ambiguous best padding surfaces: {candidates[:2]}")
    if best.run_length < 2:
        raise RuntimeError(f"padding run too short to accept: {best}")
    return best


def state_at(
    ciphertext: tuple[int, ...], key: int, iv: int, final_index: int
) -> int:
    state = iv
    for word in ciphertext[: final_index + 1]:
        state = u32(block_function(state, key) ^ word)
    return state


def affine_solution_space(
    ciphertext: tuple[int, ...], key: int, final_index: int, target: int
) -> tuple[int, tuple[int, ...]]:
    baseline = state_at(ciphertext, key, 0, final_index)
    columns = tuple(
        state_at(ciphertext, key, 1 << bit, final_index) ^ baseline
        for bit in range(32)
    )
    wanted = target ^ baseline
    basis: list[int | None] = [None] * 32
    for output_bit in range(32):
        coefficient = sum(
            ((columns[input_bit] >> output_bit) & 1) << input_bit
            for input_bit in range(32)
        )
        row = coefficient | (((wanted >> output_bit) & 1) << 32)
        while coefficient:
            pivot = coefficient.bit_length() - 1
            if basis[pivot] is None:
                basis[pivot] = row
                break
            row ^= basis[pivot]
            coefficient = row & 0xFFFFFFFF
        if not coefficient and ((row >> 32) & 1):
            raise RuntimeError("known padding state has no IV preimage")

    free_bits = tuple(bit for bit, row in enumerate(basis) if row is None)

    def solve(free_value: int) -> int:
        result = free_value
        for pivot, row in enumerate(basis):
            if row is None:
                continue
            rhs = (row >> 32) & 1
            parity = ((row & ((1 << pivot) - 1)) & result).bit_count() & 1
            if rhs ^ parity:
                result |= 1 << pivot
        return result

    particular = solve(0)
    nullspace = tuple(solve(1 << bit) ^ particular for bit in free_bits)
    return particular, nullspace


def candidate_ivs(
    words: tuple[int, ...], surface: PaddingSurface
) -> tuple[int, ...]:
    ciphertext = words[MSRAM_START : MSRAM_START + MSRAM_DWORDS]
    index = surface.first_group * 8
    if not index:
        raise RuntimeError("group-zero padding is not a supported IV crib")
    padding = PHYSICAL_PADDING_TRIADS[surface.variant]
    target = padding[0] ^ ciphertext[index - 1]
    particular, nullspace = affine_solution_space(
        ciphertext, surface.key, index, target
    )
    if len(nullspace) > 20:
        raise RuntimeError(
            f"anchor leaves {len(nullspace)} free IV bits; choose another segment"
        )
    return tuple(
        particular
        ^ sum(
            nullspace[bit] if mask & (1 << bit) else 0
            for bit in range(len(nullspace))
        )
        for mask in range(1 << len(nullspace))
    )


def decrypt_raw(
    words: tuple[int, ...], key: int, iv: int, fprom: dict[int, int]
) -> tuple[
    tuple[int, ...], int, int, int, tuple[ControlWrite, ...]
]:
    state = iv
    last_ciphertext = key

    def decrypt(ciphertext: int) -> int:
        nonlocal state, last_ciphertext
        state = u32(block_function(state, key) ^ ciphertext)
        plaintext = u32(state ^ last_ciphertext)
        last_ciphertext = ciphertext
        return plaintext

    msram = tuple(
        decrypt(word)
        for word in words[MSRAM_START : MSRAM_START + MSRAM_DWORDS]
    )
    msram_index = state & 0xFF
    msram_got = decrypt(words[MSRAM_INTEGRITY])
    msram_expected = fprom[msram_index]
    controls = []
    for control in range(CONTROL_COUNT):
        start = CONTROL_START + control * 4
        address, mask, value = (decrypt(word) for word in words[start : start + 3])
        integrity_index = state & 0xFF
        integrity_got = decrypt(words[start + 3])
        controls.append(
            ControlWrite(
                address,
                mask,
                value,
                integrity_index,
                integrity_got,
                fprom[integrity_index],
            )
        )
    return msram, msram_index, msram_got, msram_expected, tuple(controls)


def valid_decryption(
    words: tuple[int, ...], surface: PaddingSurface, base: int, fprom: dict[int, int]
) -> tuple[int, tuple[int, ...], int, int, int, tuple[ControlWrite, ...]] | None:
    signature = words[3]
    iv = u32(rotate_left(base, signature & 0xF) + 6 + words[12])
    if fprom[iv & 0x9C] != surface.key:
        return None
    msram, integrity_index, got, expected, controls = decrypt_raw(
        words, surface.key, iv, fprom
    )
    padding = PHYSICAL_PADDING_TRIADS[surface.variant]
    if not all(
        tuple(msram[group * 8 : group * 8 + 8]) == padding
        for group in range(surface.first_group, 21)
    ):
        return None
    if got != expected or not all(control.integrity_ok for control in controls):
        return None
    return iv, msram, integrity_index, got, expected, controls


def recover_file(
    data: bytes, fprom: dict[int, int]
) -> tuple[tuple[int, ...], tuple[PaddingSurface, ...], int]:
    segments = tuple(
        data[offset : offset + SEGMENT_SIZE]
        for offset in range(0, len(data), SEGMENT_SIZE)
    )
    unpacked = tuple(struct.unpack("<512I", segment) for segment in segments)
    surfaces = tuple(find_padding_surface(words, fprom) for words in unpacked)
    spaces = []
    for segment_index, (words, surface) in enumerate(zip(unpacked, surfaces)):
        try:
            ivs = candidate_ivs(words, surface)
        except RuntimeError:
            continue
        spaces.append((len(ivs), segment_index, ivs))
    if not spaces:
        raise RuntimeError("no segment has a tractable IV solution space")
    _, anchor_index, anchor_ivs = min(spaces)
    anchor_words = unpacked[anchor_index]
    bases = {
        rotate_right(
            u32(iv - 6 - anchor_words[12]), anchor_words[3] & 0xF
        )
        for iv in anchor_ivs
    }
    survivors = []
    for base in sorted(bases):
        results = tuple(
            valid_decryption(words, surface, base, fprom)
            for words, surface in zip(unpacked, surfaces)
        )
        if all(result is not None for result in results):
            survivors.append((base, results))
    if len(survivors) != 1:
        raise RuntimeError(f"expected one verified base, got {len(survivors)}")
    base, results = survivors[0]
    return unpacked, surfaces, base


def parse_logical(text: str) -> tuple[LogicalWord, ...]:
    logical = []
    for raw_line in text.splitlines():
        match = LOGICAL_LINE.fullmatch(raw_line.strip())
        if not match:
            if raw_line.strip():
                raise RuntimeError(f"unexpected descrambler output: {raw_line!r}")
            continue
        base = int(match.group(1), 16)
        logical.extend(
            LogicalWord(base + slot, int(match.group(slot + 2), 16))
            for slot in range(3)
        )
    if len(logical) != 63:
        raise RuntimeError(f"expected 63 logical words, got {len(logical)}")
    return tuple(logical)


def descramble(
    msram: tuple[int, ...], descrambler: Path, work: Path, stem: str
) -> tuple[LogicalWord, ...]:
    physical = work / f"{stem}.hex"
    physical.write_text(
        "".join(
            f"{0x7F58 + group * 8:04X}: "
            + " ".join(f"{word:08X}" for word in msram[group * 8 : group * 8 + 8])
            + "\n"
            for group in range(21)
        )
    )
    return parse_logical(
        checked([sys.executable, "-B", str(descrambler), str(physical)], work)
    )


def relevant(word: LogicalWord) -> bool:
    return bool(
        word.family
        or word.opcode in {0x120, 0x1C1}
        or word.source_one == ARITH_FLAGS_REGISTER
        or word.source_two == ARITH_FLAGS_REGISTER
        or word.modifier_u2 in {0x49, 0x50}
    )


def candidate_tail_form(word: LogicalWord) -> bool:
    return bool(
        word.family == "fadd"
        or (word.opcode == 0x120 and word.modifier_u2 == 0x50)
        or word.opcode == 0x1C1
        or word.source_one == ARITH_FLAGS_REGISTER
        or word.source_two == ARITH_FLAGS_REGISTER
        or (word.family and word.modifier_u2 == 0x49)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("fprom_data", type=Path)
    parser.add_argument("descrambler", type=Path)
    parser.add_argument("mcus", nargs="+", type=Path)
    arguments = parser.parse_args()
    if arguments.report.exists():
        raise SystemExit(f"refusing to overwrite {arguments.report}")
    if len(arguments.mcus) != 3 or {path.name for path in arguments.mcus} != {
        "06-03-02",
        "06-08-03",
        "06-0d-06",
    }:
        raise SystemExit("expected exactly the three unsupported official MCU files")
    fprom = load_fprom(arguments.fprom_data)
    decryptions = []
    with tempfile.TemporaryDirectory(prefix="h1459-p6-recovery-") as temporary:
        work = Path(temporary)
        for path in sorted(arguments.mcus, key=lambda item: item.name):
            data = path.read_bytes()
            if not data or len(data) % SEGMENT_SIZE:
                raise RuntimeError(f"unexpected file size for {path}: {len(data)}")
            unpacked, surfaces, base = recover_file(data, fprom)
            for segment_index, (words, surface) in enumerate(zip(unpacked, surfaces)):
                start = segment_index * SEGMENT_SIZE
                segment = data[start : start + SEGMENT_SIZE]
                revision, date, signature, platform_flags = parse_header(segment)
                result = valid_decryption(words, surface, base, fprom)
                if result is None:
                    raise RuntimeError("verified recovery failed on second pass")
                iv, msram, integrity_index, got, expected, controls = result
                logical = descramble(
                    msram,
                    arguments.descrambler.resolve(),
                    work,
                    f"{path.name}-{segment_index}",
                )
                decryptions.append(
                    Decryption(
                        path.name,
                        digest(data),
                        segment_index,
                        digest(segment),
                        revision,
                        date,
                        signature,
                        platform_flags,
                        base,
                        surface.key,
                        iv,
                        surface,
                        msram,
                        integrity_index,
                        got,
                        expected,
                        controls,
                        logical,
                    )
                )

    counts: Counter[str] = Counter()
    relevant_words = []
    hooks = []
    for item in decryptions:
        counts["logical_words"] += len(item.logical)
        counts["padding_words"] += sum(
            word.value in PADDING_WORDS for word in item.logical
        )
        counts["control_writes"] += len(item.controls)
        for control in item.controls:
            hook = control.match_hook()
            if hook is not None:
                hooks.append((item, control, *hook))
                counts["match_hooks"] += 1
        for word in item.logical:
            if word.value in PADDING_WORDS:
                continue
            counts["active_words"] += 1
            if word.family:
                counts[f"family.{word.family}"] += 1
            if word.opcode == 0x120:
                counts["opcode.120"] += 1
            if word.opcode == 0x120 and word.modifier_u2 == 0x50:
                counts["opcode.120_u2.50"] += 1
            if word.opcode == 0x1C1:
                counts["opcode.1c1"] += 1
            if word.source_one == ARITH_FLAGS_REGISTER:
                counts["arithflags.source_one"] += 1
            if word.source_two == ARITH_FLAGS_REGISTER:
                counts["arithflags.source_two"] += 1
            if word.family and word.modifier_u2 == 0x49:
                counts["floating_u2.49"] += 1
            if candidate_tail_form(word):
                counts["candidate_tail_forms"] += 1
            if relevant(word):
                relevant_words.append((item, word))

    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    with arguments.report.open("x") as output:
        output.write("hardware_policy\tstatic_official_files_only_no_load_no_x87\n")
        output.write("claim_boundary\tpublic_update_payloads_not_base_mask_rom\n")
        output.write(f"fprom_data_sha256\t{digest(arguments.fprom_data.read_bytes())}\n")
        output.write(f"mcu_files\t{len(arguments.mcus)}\n")
        output.write(f"update_segments\t{len(decryptions)}\n")
        for key in (
            "logical_words",
            "active_words",
            "padding_words",
            "control_writes",
            "match_hooks",
            "family.fadd",
            "family.fmul",
            "family.fdivide",
            "family.fnormalize",
            "opcode.120",
            "opcode.120_u2.50",
            "opcode.1c1",
            "arithflags.source_one",
            "arithflags.source_two",
            "floating_u2.49",
            "candidate_tail_forms",
        ):
            output.write(f"{key}\t{counts[key]}\n")

        output.write("\n[recovered segments]\n")
        output.write(
            "file\tsegment\tfile_sha256\tsegment_sha256\tsignature\trevision\t"
            "date\tplatform\tbase\tkey\tiv\tkey_index\tpadding_variant\t"
            "padding_first_group\tpadding_run\tmsram_integrity\t"
            "control_integrities\tactive_words\n"
        )
        for item in decryptions:
            active = sum(word.value not in PADDING_WORDS for word in item.logical)
            output.write(
                f"{item.source_name}\t{item.segment_index}\t{item.source_sha256}\t"
                f"{item.segment_sha256}\t{item.signature:08X}\t"
                f"{item.revision:08X}\t{item.date:08X}\t{item.platform_flags:08X}\t"
                f"{item.base:08X}\t{item.key:08X}\t{item.iv:08X}\t"
                f"{item.iv & 0x9C:02X}\t{item.surface.variant}\t"
                f"{item.surface.first_group}\t{item.surface.run_length}\t"
                f"{item.msram_integrity_got:08X}="
                f"{item.msram_integrity_expected:08X}\t"
                f"{sum(control.integrity_ok for control in item.controls)}/16\t"
                f"{active}\n"
            )

        output.write("\n[decoded match hooks]\n")
        output.write(
            "file\tsegment\tsignature\tcontrol_register\traw_value\t"
            "source_urom\tdestination_msram\n"
        )
        for item, control, source, destination in hooks:
            output.write(
                f"{item.source_name}\t{item.segment_index}\t{item.signature:08X}\t"
                f"{control.address:03X}\t{control.value:08X}\t"
                f"{source:04X}\t{destination:04X}\n"
            )

        output.write("\n[adjacent or candidate raw words]\n")
        output.write(
            "file\tsegment\taddress\traw80\topcode\tu2\tu3\t"
            "destination\tsource_one\tsource_two\tfamily\n"
        )
        for item, word in relevant_words:
            output.write(
                f"{item.source_name}\t{item.segment_index}\t{word.address:04X}\t"
                f"{word.value:020X}\t{word.opcode:03X}\t"
                f"{word.modifier_u2:03X}\t{word.modifier_u3:02X}\t"
                f"{word.destination:02X}\t{word.source_one:02X}\t"
                f"{word.source_two:02X}\t{word.family or '-'}\n"
            )

        output.write("\n[result]\n")
        output.write("unsupported_public_patches\trecovered_and_integrity_verified\n")
        output.write(
            "patch_surface_candidate_tail_forms\t"
            + ("present_review_rows_above" if counts["candidate_tail_forms"] else "absent")
            + "\n"
        )
        output.write("base_mask_rom_recovery\tnot_provided_by_update_patches\n")

    print(
        f"wrote {arguments.report}: segments={len(decryptions)} "
        f"active={counts['active_words']} relevant={len(relevant_words)} "
        f"candidate_tail={counts['candidate_tail_forms']}"
    )


if __name__ == "__main__":
    main()

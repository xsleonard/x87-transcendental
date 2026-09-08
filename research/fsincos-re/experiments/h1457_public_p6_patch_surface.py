#!/usr/bin/env python3
"""Audit raw floating/control forms in public Intel P6 update patches.

The public P6 patch decryptor and physical-to-logical descrambler make official
MSRAM updates a small source of raw 80-bit micro-ops.  They do not recover the
base mask ROM.  This script decrypts every supplied 2 KiB update segment,
validates its standard Intel header checksum, descrambles its 63 logical
micro-ops, and reports forms relevant to the unresolved cosine tail:

* masked floating add, multiply, divide, and normalize families;
* opcode 0x120, especially modifier U2.50;
* explicit ArithFLAGS register sources;
* final floating-family forms carrying U2.49.

It accepts already downloaded official MCU files and external public tools so
that neither third-party code nor binary updates need to be copied into the
repository.  It never loads a microcode update or executes an x87 instruction.
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
FAMILY_MASK = 0xC7F
FLOATING_FAMILIES = {
    0x468: "fadd",
    0x469: "fmul",
    0x46B: "fnormalize",
    0x46E: "fdivide",
}
ARITH_FLAGS_REGISTER = 0x25
CONTROL_WRITE = re.compile(
    r"^write_creg\s+0x([0-9A-Fa-f]+)\s+0x([0-9A-Fa-f]+)\s+"
    r"0x([0-9A-Fa-f]+)$"
)
ADDRESSED_LINE = re.compile(r"^UROM_([0-9A-Fa-f]+)\b")
MATCH_CONTROL_REGISTERS = frozenset(
    range(0x0A8, 0x0B0)
) | frozenset(range(0x0F0, 0x0F8)) | frozenset(range(0x1B4, 0x1BC))
PATCH_ADDRESS_MIN = 0x3FAC
PATCH_ADDRESS_MAX = 0x3FFE


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
class ControlWrite:
    address: int
    mask: int
    value: int

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
class SegmentResult:
    source_name: str
    source_sha256: str
    index: int
    segment_sha256: str
    revision: int
    date: int
    signature: int
    platform_flags: int
    decryption_warnings: tuple[str, ...]
    control_writes: tuple[ControlWrite, ...]
    words: tuple[LogicalWord, ...]


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def checked_run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
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
    return result


def parse_logical(text: str) -> tuple[LogicalWord, ...]:
    words = []
    for raw_line in text.splitlines():
        match = LOGICAL_LINE.fullmatch(raw_line.strip())
        if not match:
            if raw_line.strip():
                raise RuntimeError(f"unexpected descrambler output: {raw_line!r}")
            continue
        base = int(match.group(1), 16)
        words.extend(
            LogicalWord(base + slot, int(match.group(slot + 2), 16))
            for slot in range(3)
        )
    if len(words) != 63:
        raise RuntimeError(f"expected 63 logical micro-ops, got {len(words)}")
    return tuple(words)


def parse_control_writes(path: Path) -> tuple[ControlWrite, ...]:
    writes = []
    for raw_line in path.read_text().splitlines():
        match = CONTROL_WRITE.fullmatch(raw_line.strip())
        if match:
            writes.append(ControlWrite(*(int(value, 16) for value in match.groups())))
    if len(writes) != 16:
        raise RuntimeError(f"expected 16 decrypted control writes in {path}, got {len(writes)}")
    return tuple(writes)


def parse_listing_spec(spec: str) -> tuple[int, Path, frozenset[int]]:
    signature_text, separator, path_text = spec.partition("=")
    if not separator:
        raise argparse.ArgumentTypeError("listing must be SIGNATURE=PATH")
    try:
        signature = int(signature_text, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"bad listing signature: {signature_text}") from error
    path = Path(path_text)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"listing does not exist: {path}")
    addresses = frozenset(
        int(match.group(1), 16)
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if (match := ADDRESSED_LINE.match(line))
    )
    if not addresses:
        raise argparse.ArgumentTypeError(f"listing has no UROM addresses: {path}")
    return signature, path, addresses


def header(segment: bytes) -> tuple[int, int, int, int]:
    values = struct.unpack_from("<12I", segment)
    header_version, revision, date, signature = values[:4]
    platform_flags = values[6]
    if header_version != 1:
        raise RuntimeError(f"unexpected header version {header_version}")
    if sum(struct.unpack("<512I", segment)) & 0xFFFFFFFF:
        raise RuntimeError(
            f"standard Intel update checksum failed for signature {signature:08X}"
        )
    return revision, date, signature, platform_flags


def decode_segment(
    source_name: str,
    source_sha256: str,
    index: int,
    segment: bytes,
    patchtools: Path,
    descrambler: Path,
    work: Path,
) -> SegmentResult:
    revision, date, signature, platform_flags = header(segment)
    stem = f"{source_name}-segment-{index}"
    patch_path = work / f"{stem}.dat"
    config_path = work / f"{stem}.txt"
    patch_path.write_bytes(segment)

    decrypted = checked_run(
        [str(patchtools), "-e", "-p", str(patch_path), "-i", str(config_path)],
        work,
    )
    warnings = tuple(
        line.strip() for line in decrypted.stderr.splitlines() if line.strip()
    )
    if any("failed" in warning.lower() for warning in warnings):
        raise RuntimeError(f"decryption integrity failure: {warnings}")

    physical_path = work / f"{stem}.hex"
    if not physical_path.is_file():
        raise RuntimeError(f"patch decryptor did not create {physical_path}")
    logical = checked_run(
        [sys.executable, "-B", str(descrambler), str(physical_path)],
        descrambler.parent,
    )
    return SegmentResult(
        source_name,
        source_sha256,
        index,
        digest_bytes(segment),
        revision,
        date,
        signature,
        platform_flags,
        warnings,
        parse_control_writes(config_path),
        parse_logical(logical.stdout),
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


def is_padding(word: LogicalWord) -> bool:
    return word.value in PADDING_WORDS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("patchtools", type=Path)
    parser.add_argument("descrambler", type=Path)
    parser.add_argument(
        "--listing",
        action="append",
        default=[],
        type=parse_listing_spec,
        help="known routine listing as SIGNATURE=PATH",
    )
    parser.add_argument("mcus", nargs="+", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")
    if not args.patchtools.is_file() or not args.descrambler.is_file():
        raise SystemExit("patch decryptor or descrambler does not exist")

    listing_addresses = {}
    for signature, path, addresses in args.listing:
        if signature in listing_addresses:
            raise SystemExit(f"duplicate listing signature {signature:08X}")
        listing_addresses[signature] = (path, addresses)

    segments: list[SegmentResult] = []
    source_hashes = {path.name: digest(path) for path in args.mcus}
    if len(source_hashes) != len(args.mcus):
        raise SystemExit("MCU basenames must be unique")

    with tempfile.TemporaryDirectory(prefix="h1457-p6-patches-") as temporary:
        work = Path(temporary)
        for path in args.mcus:
            data = path.read_bytes()
            if not data or len(data) % SEGMENT_SIZE:
                raise RuntimeError(
                    f"{path} size {len(data)} is not a nonzero multiple of 2 KiB"
                )
            for index in range(len(data) // SEGMENT_SIZE):
                start = index * SEGMENT_SIZE
                segment = data[start:start + SEGMENT_SIZE]
                segments.append(decode_segment(
                    path.name,
                    source_hashes[path.name],
                    index,
                    segment,
                    args.patchtools.resolve(),
                    args.descrambler.resolve(),
                    work,
                ))

    counts: Counter[str] = Counter()
    matches = []
    hooks = []
    hook_overlaps = []
    signatures = set()
    for segment in segments:
        signatures.add(segment.signature)
        counts["logical_words"] += len(segment.words)
        counts["padding_words"] += sum(
            is_padding(word) for word in segment.words
        )
        counts["decryption_warnings"] += len(segment.decryption_warnings)
        counts["control_writes"] += len(segment.control_writes)
        for write in segment.control_writes:
            hook = write.match_hook()
            if hook is None:
                continue
            source, destination = hook
            hooks.append((segment, write, source, destination))
            counts["match_hooks"] += 1
            known_listing = listing_addresses.get(segment.signature)
            if known_listing is not None and source in known_listing[1]:
                hook_overlaps.append((segment, write, source, destination))
                counts["known_listing_hook_overlaps"] += 1
        for word in segment.words:
            if is_padding(word):
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
                matches.append((segment, word))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write("hardware_policy\tofficial_patch_files_static_only_no_load_no_x87_execution\n")
        output.write(
            "claim_boundary\tpublic_decryptable_msram_updates_only_not_base_mask_rom\n"
        )
        output.write(f"mcu_files\t{len(args.mcus)}\n")
        output.write(f"update_segments\t{len(segments)}\n")
        output.write(f"processor_signatures\t{len(signatures)}\n")
        output.write(f"known_routine_listings\t{len(listing_addresses)}\n")
        for key in (
            "logical_words",
            "active_words",
            "padding_words",
            "decryption_warnings",
            "control_writes",
            "match_hooks",
            "known_listing_hook_overlaps",
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
        ):
            output.write(f"{key}\t{counts[key]}\n")
        output.write(f"adjacent_or_candidate_raw_words\t{len(matches)}\n")
        candidate_tail_forms = counts["candidate_tail_forms"]
        output.write(f"candidate_tail_forms\t{candidate_tail_forms}\n")

        output.write("\n[known routine listings]\n")
        output.write("signature\tlisting\tsha256\taddressed_locations\tminimum\tmaximum\n")
        for signature, (path, addresses) in sorted(listing_addresses.items()):
            output.write(
                f"{signature:08X}\t{path}\t{digest(path)}\t{len(addresses)}\t"
                f"{min(addresses):04X}\t{max(addresses):04X}\n"
            )

        output.write("\n[official MCU sources]\n")
        output.write("file\tsha256\tbytes\tsegments\n")
        for path in args.mcus:
            size = path.stat().st_size
            output.write(
                f"{path.name}\t{source_hashes[path.name]}\t{size}\t"
                f"{size // SEGMENT_SIZE}\n"
            )

        output.write("\n[decoded update segments]\n")
        output.write(
            "file\tsegment\tsegment_sha256\tsignature\trevision\tdate\t"
            "platform_flags\tactive_words\twarnings\n"
        )
        for segment in segments:
            active = sum(not is_padding(word) for word in segment.words)
            output.write(
                f"{segment.source_name}\t{segment.index}\t"
                f"{segment.segment_sha256}\t{segment.signature:08X}\t"
                f"{segment.revision:08X}\t{segment.date:08X}\t"
                f"{segment.platform_flags:08X}\t{active}\t"
                f"{' | '.join(segment.decryption_warnings) or '-'}\n"
            )

        output.write("\n[decoded match hooks]\n")
        output.write(
            "file\tsegment\tsignature\tcontrol_register\traw_value\t"
            "source_urom\tdestination_msram\tknown_listing_overlap\n"
        )
        overlap_keys = {
            (segment.source_name, segment.index, write.address)
            for segment, write, _, _ in hook_overlaps
        }
        for segment, write, source, destination in hooks:
            key = (segment.source_name, segment.index, write.address)
            known = listing_addresses.get(segment.signature)
            overlap = "-" if known is None else str(int(key in overlap_keys))
            output.write(
                f"{segment.source_name}\t{segment.index}\t"
                f"{segment.signature:08X}\t{write.address:03X}\t"
                f"{write.value:08X}\t{source:04X}\t{destination:04X}\t"
                f"{overlap}\n"
            )

        output.write("\n[adjacent or candidate raw words]\n")
        output.write(
            "file\tsegment\taddress\traw80\topcode\tu2\tu3\t"
            "destination\tsource_one\tsource_two\tfamily\n"
        )
        for segment, word in matches:
            output.write(
                f"{segment.source_name}\t{segment.index}\t{word.address:04X}\t"
                f"{word.value:020X}\t{word.opcode:03X}\t"
                f"{word.modifier_u2:03X}\t{word.modifier_u3:02X}\t"
                f"{word.destination:02X}\t{word.source_one:02X}\t"
                f"{word.source_two:02X}\t"
                f"{word.family or '-'}\n"
            )

        output.write("\n[result]\n")
        if candidate_tail_forms:
            output.write("patch_surface_candidate_tail_forms\tpresent_review_rows_above\n")
        else:
            output.write("patch_surface_candidate_tail_forms\tabsent\n")
        if matches:
            output.write(
                "patch_surface_adjacent_samples\tpresent_but_no_precision_seed_"
                "or_terminal_status_route\n"
            )
        output.write("base_mask_rom_recovery\tnot_provided_by_update_patches\n")
        if listing_addresses:
            output.write(
                "known_routine_match_hooks\t"
                f"{'present' if hook_overlaps else 'absent'}\n"
            )

    print(
        f"wrote {args.report}: files={len(args.mcus)} segments={len(segments)} "
        f"active={counts['active_words']} relevant={len(matches)}"
    )


if __name__ == "__main__":
    main()

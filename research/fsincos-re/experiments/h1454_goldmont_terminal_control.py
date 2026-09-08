#!/usr/bin/env python3
"""Audit the raw terminal-control forms in the public Goldmont ROM dump.

The public Goldmont dump is a different FPU lineage and cannot establish a
Skylake selector.  It does, however, expose complete 48-bit micro-operations
and absolute ROM addresses.  This audit uses that independent raw control
surface to answer one narrow structural question: do the terminal opcode
``0x689`` sites carry path-specific control bits, or do their mode fields
reduce to stable scalar and paired-result forms?

Only source-defined fields from the published 48-bit layout are decoded.  No
hardware is executed, no target labels are consulted, and no raw Goldmont
field is scored as an R59 feature.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


SOURCE_URL = (
    "https://github.com/chip-red-pill/uCodeDisasm/"
    "blob/master/ucode/ucode_glm.txt"
)
SOURCE_SHA256 = "46fb61bfaf174765c117de65b036b73ae4433b9c2b9871d5289fd02d4867067e"
OPCODE = 0x689
DUAL_PATH_ENDPOINTS = ((0x4AD1, 0x4AD6), (0x64B1, 0x64B6))
SCALAR_PATH_ENDPOINTS = (0x67B6, 0x6D12)
PATH_SPLITS = (
    ("dual", 0x64AC, 0x4ACD, DUAL_PATH_ENDPOINTS[0], 0x64AD,
     DUAL_PATH_ENDPOINTS[1]),
    ("scalar", 0x6CF6, 0x679A, (SCALAR_PATH_ENDPOINTS[0],), 0x6CF8,
     (SCALAR_PATH_ENDPOINTS[1],)),
)
SITE_RE = re.compile(
    r"^U([0-9A-Fa-f]+):\s+([0-9A-Fa-f]{12})\s+.*\bunk_689\(([^)]*)\)"
)
SEQUENCE_RE = re.compile(r"SEQW\s+(?:GOTO\s+)?(\S+)")
BLOCK_RE = re.compile(r"^-{20,}\s*$")


@dataclass(frozen=True)
class RawUop:
    address: int
    raw: int
    patch_bits: int
    m2: int
    m1: int
    opcode: int
    imm0: int
    m0: int
    imm1: int
    destination: int
    source1: int
    source0: int
    operands: str
    block: int
    exit_target: str

    @property
    def control_tuple(self) -> tuple[int, ...]:
        return (
            self.patch_bits,
            self.m2,
            self.m1,
            self.m0,
            self.imm0,
            self.imm1,
            self.destination,
        )

    @property
    def mode_tuple(self) -> tuple[int, ...]:
        return (
            self.patch_bits,
            self.m2,
            self.m1,
            self.m0,
            self.imm0,
            self.imm1,
        )


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def decode(address: int, raw: int, operands: str, block: int,
           exit_target: str) -> RawUop:
    return RawUop(
        address=address,
        raw=raw,
        patch_bits=(raw >> 46) & 0x3,
        m2=(raw >> 45) & 0x1,
        m1=(raw >> 44) & 0x1,
        opcode=(raw >> 32) & 0xFFF,
        imm0=(raw >> 24) & 0xFF,
        m0=(raw >> 23) & 0x1,
        imm1=(raw >> 18) & 0x1F,
        destination=(raw >> 12) & 0x3F,
        source1=(raw >> 6) & 0x3F,
        source0=raw & 0x3F,
        operands=operands,
        block=block,
        exit_target=exit_target,
    )


def parse_source(path: Path) -> list[RawUop]:
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[list[tuple[int, str]]] = [[]]
    for line_number, line in enumerate(lines):
        if BLOCK_RE.match(line):
            blocks.append([])
        else:
            blocks[-1].append((line_number, line))

    sites: list[RawUop] = []
    for block_number, block_lines in enumerate(blocks):
        matches = []
        for line_number, line in block_lines:
            match = SITE_RE.match(line)
            if match:
                matches.append((line_number, match))
        if not matches:
            continue

        sequence_targets = []
        last_site_line = matches[-1][0]
        for line_number, line in block_lines:
            if line_number <= last_site_line:
                continue
            match = SEQUENCE_RE.search(line)
            if match:
                sequence_targets.append(match.group(1))
        if not sequence_targets:
            raise RuntimeError(
                f"terminal block {block_number} has no following sequence target"
            )
        exit_target = sequence_targets[0]
        if exit_target not in {"uend", "U0404"}:
            raise RuntimeError(
                f"opcode 0x689 block exits to unexpected target {exit_target}"
            )

        for _, match in matches:
            address_text, raw_text, operands = match.groups()
            site = decode(
                int(address_text, 16),
                int(raw_text, 16),
                operands,
                block_number,
                exit_target,
            )
            if site.opcode != OPCODE:
                raise AssertionError("parser matched the wrong opcode")
            sites.append(site)
    return sites


def validate_path_splits(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    address_lines: dict[int, int] = {}
    for line_number, line in enumerate(lines):
        match = re.match(r"^U([0-9A-Fa-f]+):", line)
        if match:
            address_lines[int(match.group(1), 16)] = line_number

    def linear_segment(start: int, end: int) -> None:
        start_line = address_lines[start]
        end_line = address_lines[end]
        if start_line > end_line:
            raise RuntimeError(f"reversed path segment {start:04x}..{end:04x}")
        body = "\n".join(lines[start_line:end_line + 1])
        if "UJMP" in body or "SEQW GOTO" in body or "SEQW URET" in body:
            raise RuntimeError(
                f"path segment {start:04x}..{end:04x} is no longer linear"
            )

    for kind, branch, target, target_endpoints, fallthrough, fall_endpoints in PATH_SPLITS:
        branch_line = lines[address_lines[branch]]
        if "UJMPCC_DIRECT_NOTTAKEN" not in branch_line or f"U{target:04x}" not in branch_line:
            raise RuntimeError(
                f"{kind} path split at {branch:04x} no longer targets {target:04x}"
            )
        linear_segment(target, target_endpoints[-1])
        linear_segment(fallthrough, fall_endpoints[-1])


def validate_structure(sites: list[RawUop]) -> tuple[list[list[RawUop]], list[RawUop]]:
    by_block: dict[int, list[RawUop]] = {}
    for site in sites:
        by_block.setdefault(site.block, []).append(site)
    for block_sites in by_block.values():
        block_sites.sort(key=lambda item: item.address)

    paired = [items for items in by_block.values() if len(items) == 2]
    scalar = [items[0] for items in by_block.values() if len(items) == 1]
    if any(len(items) not in {1, 2} for items in by_block.values()):
        raise RuntimeError("unexpected 0x689 multiplicity in a terminal block")
    if len(sites) != 13 or len(paired) != 2 or len(scalar) != 9:
        raise RuntimeError(
            "public terminal census changed: "
            f"sites={len(sites)} paired={len(paired)} scalar={len(scalar)}"
        )

    scalar_modes = {item.mode_tuple for item in scalar}
    expected_scalar = {
        (0, 0, 0, 0, 0, 0),
        (0, 1, 0, 0, 0, 0),
    }
    if scalar_modes != expected_scalar:
        raise RuntimeError(f"scalar terminal mode changed: {scalar_modes}")

    expected_pair_modes = (
        (0, 0, 0, 1, 0x01, 0),
        (0, 1, 0, 1, 0x71, 0),
    )
    for items in paired:
        if tuple(item.mode_tuple for item in items) != expected_pair_modes:
            raise RuntimeError(
                "paired terminal mode changed: "
                f"{tuple(item.mode_tuple for item in items)}"
            )
        if tuple(item.destination for item in items) != (0x08, 0x09):
            raise RuntimeError("paired terminal destinations changed")

    if any(item.patch_bits or item.m1 or item.imm1 for item in sites):
        raise RuntimeError("previously zero terminal control field became active")

    by_address = {item.address: item for item in sites}
    observed_dual_paths = tuple(
        tuple(by_address[address].mode_tuple for address in endpoints)
        for endpoints in DUAL_PATH_ENDPOINTS
    )
    if observed_dual_paths[0] != observed_dual_paths[1]:
        raise RuntimeError(
            f"dual alternative path controls diverged: {observed_dual_paths}"
        )
    observed_scalar_paths = tuple(
        by_address[address].mode_tuple for address in SCALAR_PATH_ENDPOINTS
    )
    if observed_scalar_paths[0] != observed_scalar_paths[1]:
        raise RuntimeError(
            f"scalar alternative path controls diverged: {observed_scalar_paths}"
        )
    return paired, scalar


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    source_hash = digest(args.source)
    if source_hash != SOURCE_SHA256:
        raise SystemExit(
            "public Goldmont source digest changed; inspect before updating: "
            f"{source_hash}"
        )
    validate_path_splits(args.source)
    sites = parse_source(args.source)
    paired, scalar = validate_structure(sites)
    raw_forms = Counter(item.raw for item in sites)
    mode_forms = Counter(item.mode_tuple for item in sites)
    exit_targets = Counter(item.exit_target for item in sites)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write("hardware_policy\tpublic_rom_static_only_no_x87_execution\n")
        output.write(f"primary_source\t{SOURCE_URL}\n")
        output.write(f"source_sha256\t{source_hash}\n")
        output.write(
            "source_scope\tGoldmont_raw_control_structural_prior_not_"
            "P6_or_Skylake_provenance\n"
        )
        output.write(
            "candidate_policy\tdecode_published_48bit_fields_only_no_"
            "target_labels_or_feature_scoring\n"
        )
        output.write(f"opcode\t0x{OPCODE:03x}\n")
        output.write(f"terminal_sites\t{len(sites)}\n")
        output.write(f"terminal_blocks\t{len(paired) + len(scalar)}\n")
        output.write(f"scalar_terminal_sites\t{len(scalar)}\n")
        output.write(f"paired_terminal_sites\t{sum(map(len, paired))}\n")
        output.write(f"paired_terminal_blocks\t{len(paired)}\n")
        output.write(f"raw_word_forms\t{len(raw_forms)}\n")
        output.write(f"control_mode_forms\t{len(mode_forms)}\n")
        output.write("active_patch_bits\t0\n")
        output.write("active_m1_sites\t0\n")
        output.write("active_imm1_sites\t0\n")
        output.write(
            "paired_blocks_have_identical_ordered_control_modes\t1\n"
        )
        output.write(
            f"scalar_control_modes\t{len(set(item.mode_tuple for item in scalar))}\n"
        )
        output.write(
            "dual_alternative_paths_share_ordered_control_modes\t1\n"
        )
        output.write(
            "scalar_alternative_paths_share_terminal_control_mode\t1\n"
        )
        output.write("all_sites_exit_terminally\t1\n")

        output.write("\n[mode forms]\n")
        output.write(
            "patch_bits\tm2\tm1\tm0\timm0\timm1\tsites\n"
        )
        for mode, count in sorted(mode_forms.items()):
            patch_bits, m2, m1, m0, imm0, imm1 = mode
            output.write(
                f"{patch_bits}\t{m2}\t{m1}\t{m0}\t0x{imm0:02x}\t"
                f"0x{imm1:02x}\t{count}\n"
            )

        output.write("\n[terminal sites]\n")
        output.write(
            "address\traw\tblock_kind\tpair_position\tpatch_bits\tm2\t"
            "m1\tm0\timm0\timm1\tdestination\tsource1\tsource0\t"
            "exit_target\n"
        )
        paired_blocks = {items[0].block: items for items in paired}
        for item in sorted(sites, key=lambda value: value.address):
            block_sites = paired_blocks.get(item.block)
            block_kind = "paired" if block_sites else "scalar"
            pair_position = (
                block_sites.index(item) if block_sites is not None else -1
            )
            output.write(
                f"0x{item.address:04x}\t{item.raw:012x}\t{block_kind}\t"
                f"{pair_position}\t{item.patch_bits}\t{item.m2}\t"
                f"{item.m1}\t{item.m0}\t0x{item.imm0:02x}\t"
                f"0x{item.imm1:02x}\t0x{item.destination:02x}\t"
                f"0x{item.source1:02x}\t0x{item.source0:02x}\t"
                f"{item.exit_target}\n"
            )

        output.write("\n[paired block controls]\n")
        output.write(
            "block\tfirst_address\tsecond_address\tfirst_mode\t"
            "second_mode\n"
        )
        for block_number, items in sorted(
            (items[0].block, items) for items in paired
        ):
            first_mode = ",".join(map(str, items[0].mode_tuple))
            second_mode = ",".join(map(str, items[1].mode_tuple))
            output.write(
                f"{block_number}\t0x{items[0].address:04x}\t"
                f"0x{items[1].address:04x}\t{first_mode}\t"
                f"{second_mode}\n"
            )

        output.write("\n[visible path alternatives]\n")
        output.write(
            "kind\tbranch\ttaken_start\ttaken_endpoint\tfallthrough_start\t"
            "fallthrough_endpoint\tlinear_paths\tcontrols_equal\n"
        )
        for kind, branch, target, target_endpoints, fallthrough, fall_endpoints in PATH_SPLITS:
            left = "/".join(f"0x{address:04x}" for address in target_endpoints)
            right = "/".join(f"0x{address:04x}" for address in fall_endpoints)
            output.write(
                f"{kind}\t0x{branch:04x}\t0x{target:04x}\t{left}\t"
                f"0x{fallthrough:04x}\t{right}\t1\t1\n"
            )

        output.write("\n[exit targets]\n")
        output.write("target\tsites\n")
        for target, count in sorted(exit_targets.items()):
            output.write(f"{target}\t{count}\n")

        output.write("\n[result]\n")
        output.write(
            "raw_terminal_control\tfour_fixed_site_forms_with_"
            "stable_alternative_path_controls\n"
        )
        output.write(
            "input_dependent_terminal_mode_selector\tnot_exposed_at_"
            "the_two_visible_sincos_shaped_path_splits\n"
        )
        output.write(
            "cross_generation_claim\tnone_different_FPU_lineage\n"
        )
        output.write(
            "remaining_possible_channel\tinternal_arithmetic_state_or_"
            "unpublished_Skylake_control\n"
        )
        output.write("r59_selector_candidate\tnone\n")

    print(
        f"wrote {args.report}: sites={len(sites)} scalar={len(scalar)} "
        f"paired_blocks={len(paired)} modes={len(mode_forms)}",
        flush=True,
    )


if __name__ == "__main__":
    main()

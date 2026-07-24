#!/usr/bin/env python3
"""Verify and score a returned full or constraint-only capture-kit archive.

Archives are read directly without extraction.  The report identifies the
CPU, validates the capture manifest, compares legacy channels with the local
Pentium-II witness when available, checks the h59 files against the known
Skylake hashes, checks h62's m-width result, checks h65/h71/h74 polynomial
results, checks h67's wide-producer result, checks h78's paired-table
result, verifies h83-h108 targets against known Skylake hashes, and scores
the baseline and carried schedules.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import tarfile
from collections.abc import Callable

import h58_constraint_search as h58
import h62_mwidth_discriminator as h62
import h64_poly_constraints as h64
import h65_poly_discriminator as h65
import h67_wide_producer_discriminator as h67
import h73_poly_product_crossvalidate as h73
import h79_table_state_bias as h79


ROOT = pathlib.Path(__file__).resolve().parents[1]
H59_INPUTS = ROOT / "capture-kit" / "inputs" / "constraint_narrow_h59.txt"
H62_INPUTS = ROOT / "capture-kit" / "inputs" / "constraint_mwidth_h62.txt"
H65_INPUTS = ROOT / "capture-kit" / "inputs" / "constraint_poly_h65.txt"
H71_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_poly_round75_h71.txt"
)
H74_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_poly_product_h74.txt"
)
H67_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_wide_producer_h67.txt"
)
H78_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_paired_table_h78.txt"
)
DENSE_INPUTS = ROOT / "capture-kit" / "inputs" / "dense_qn.txt"
DEFAULT_REFERENCE = ROOT / "capture-kit-captures" / "pentiumII"
H59_FILES = tuple(f"constraint_narrow_{rc}.txt" for rc in h58.RCS)
H62_FILES = tuple(f"constraint_mwidth_{rc}.txt" for rc in h58.RCS)
H65_FILES = tuple(f"constraint_poly_{rc}.txt" for rc in h58.RCS)
H71_FILES = tuple(
    f"constraint_poly_round75_{rc}.txt" for rc in h58.RCS
)
H74_FILES = tuple(
    f"constraint_poly_product_{rc}.txt" for rc in h58.RCS
)
H67_FILES = tuple(
    f"constraint_wide_producer_{rc}.txt" for rc in h58.RCS
)
H78_FILES = tuple(
    f"constraint_paired_table_{rc}.txt" for rc in h58.RCS
)
LEGACY_FILES = (
    "sweep_rn.txt",
    "dense_rn.txt",
    "dense_rd.txt",
    "dense_ru.txt",
    "dense_fsin.txt",
    "dense_fcos.txt",
)
SKYLAKE_H59_SHA256 = {
    "constraint_narrow_rn.txt":
        "97c03422b1d1481e21b5d8664570faabe3e1322edb34a3167f0db8c5e7880658",
    "constraint_narrow_rd.txt":
        "844b1499774ca07811a5374e1830cb200eee647ce963982f6f7365665a9d9457",
    "constraint_narrow_ru.txt":
        "15f401861df306549e43ee9fa36def6d905404f8f8fad07ebcf20dd1850b389e",
}
SKYLAKE_H62_SHA256 = {
    "constraint_mwidth_rn.txt":
        "fb9fa2c5932db7511a1d3d78860ed2ad2dce317b2aa44366bf3c330b2957c49a",
    "constraint_mwidth_rd.txt":
        "36dca8b5734d46811d224b8fb0ee1bd67c12d61153cdc618ea25fdc7de985b15",
    "constraint_mwidth_ru.txt":
        "e4b5cb105ef6ac45c3fc9d38116cb37ecb0caac5dc891fbe58849d5f6365f848",
}
SKYLAKE_H65_SHA256 = {
    "constraint_poly_rn.txt":
        "89acd845b16ed59ecdbc94384be9e4d74031eca01ad155b0ca688ceb1535fff3",
    "constraint_poly_rd.txt":
        "0c42af541894f90f0a922223f051b9c6aae8b0be646ff65548714d030bd165e1",
    "constraint_poly_ru.txt":
        "3addc764253d3156e7f06cf20f12950d3b26621cb1093f48af14d8f32c37929b",
}
SKYLAKE_H71_SHA256 = {
    "constraint_poly_round75_rn.txt":
        "d04a834330f0bada514187fe944df6c6b25c3aaa6ea703bc22505d448667703f",
    "constraint_poly_round75_rd.txt":
        "9abebe53056aeeff234e862a46cedf3b99915b8d6f400b1e90d1534bc8719057",
    "constraint_poly_round75_ru.txt":
        "20aeeb1d4a36430b8cc68fcc6ab27857000d4818142a4fb5cf6926d353584118",
}
SKYLAKE_H74_SHA256 = {
    "constraint_poly_product_rn.txt":
        "823e454b7231b2adbb897d155e6771453d36267eb14c3f54712fe649935bbf23",
    "constraint_poly_product_rd.txt":
        "c72a12ee0b6d65333a978430471f09d84b1b50b08d6589a09f78495a460fef1d",
    "constraint_poly_product_ru.txt":
        "62abec9382c7676d16c010c6731f10ca96d9811006bae1b8866f2621a036a3b1",
}
SKYLAKE_H67_SHA256 = {
    "constraint_wide_producer_rn.txt":
        "2a830077714a79e271eb718ee42c4df6384c728d8d7861a5570b6f268e1fbb25",
    "constraint_wide_producer_rd.txt":
        "9e96ed5fa42cc613e8cf17374d61a4c2c20ca4a594912bf7ed88bdd0000c5019",
    "constraint_wide_producer_ru.txt":
        "6f9a5ef1fa0be54caabb3e1290b3242d0657e7d114a3e2b3a719cbe3ad715231",
}
SKYLAKE_H78_SHA256 = {
    "constraint_paired_table_rn.txt":
        "f6179a11d474fdeae58c95cc93162ccc83a5973fe9a01db8d72d25053fdb1d53",
    "constraint_paired_table_rd.txt":
        "d92a24c536bc5f6836d9fd50ded98e9781610147bb70c90ea7caceb6ab4a0e43",
    "constraint_paired_table_ru.txt":
        "f216d781f6bff77c313581b380c750949b9ca34db75ac85cfb51d958dd17d9ae",
}
NEW_TARGETS = (
    (
        "h83 small boundary",
        ROOT / "capture-kit" / "inputs" / "constraint_small_h83.txt",
        "constraint_small",
        (
            "f69b428b94556e426afa94b63e0e96e1ee7d78076b34a649e7b0fd095c6a9469",
            "659d465f0e1603fe596c64d42702b2759a1a0399364f565ec409805d5f374347",
            "df01c36d58b8be3ee33e9d38074c45ae97aab50dcc23bc1e8b2e621f45de7ca6",
        ),
    ),
    (
        "h85 small width",
        ROOT / "capture-kit" / "inputs" / "constraint_small_width_h85.txt",
        "constraint_small_width",
        (
            "894c06db33975fdbf7a86cce7e0be34ec6d7c6e006ddda607052429699753355",
            "cfda5df583275cd89996851b35be6037ea923122121d2ff3f9d49078bc2465bd",
            "2b9ab694d79a48c164e55eefec0e1a002cc31d765e26308039ec057261f58d46",
        ),
    ),
    (
        "h87 small chop",
        ROOT / "capture-kit" / "inputs" / "constraint_small_chop_h87.txt",
        "constraint_small_chop",
        (
            "ff3dac88558b1597c127378911dd38faaeea37d8bd96265fff6802a068f6e54c",
            "5e90a7bf5e5c07bfa4901d5ecc8cb1a1fd319ffc1d14fdd36c088c9926cdf565",
            "d14b171a60ea66ac1ccadd3e0ce9b07c8878e69aeea1f118ea2f6e1bbe0c2e46",
        ),
    ),
    (
        "h89 deep small",
        ROOT / "capture-kit" / "inputs" / "constraint_small_deep_h89.txt",
        "constraint_small_deep",
        (
            "098bdabec676c614b658afa5e5612df81547089e2cdab2db5ee051c0209bcf87",
            "9915daba88762c04020ff34b214858a477f6c6e6c6f2f41a39256867167c9c06",
            "7b8d91b8d0236716589faf1e0b41a83e45a5fdbaa9bdc5abe9ff935066eb7a37",
        ),
    ),
    (
        "h93 master tomography",
        ROOT / "capture-kit" / "inputs" / "constraint_table_residual_h93.txt",
        "constraint_table_residual",
        (
            "d47e847a0019d4dde63c0549b1107a7b49afc3d840d24b09c3e8f13b1ed22142",
            "ee0421ef39685193ecfeeff59958b6d6699744c3b39cfffb96762cf1948242d8",
            "d2e46add44407eaf446df8943d492ce6a2c0855452ce6b460da2bbea195d478f",
        ),
    ),
    (
        "h95 local tomography",
        ROOT / "capture-kit" / "inputs" / "constraint_table_local_h95.txt",
        "constraint_table_local",
        (
            "ec924e723b72260eff943f2988efd37ced91455bbfcacadbfb3f673569b6766d",
            "0f2cb81fac899bd8ac133ed821c158460d411d07e80195ccc695a03ffdf970b1",
            "4ec44bfd8e8ae61792ca54174f6af0501a554e15c5ba22654dffd6e1de2a41c8",
        ),
    ),
    (
        "h97 narrow coefficient",
        ROOT / "capture-kit" / "inputs" / "constraint_narrow_coefficient_h97.txt",
        "constraint_narrow_coefficient",
        (
            "48edfc3d10762ba7c38f26e15e7740c4d0ad8ac2d3d7b24b6f4bc3f6c57a9a22",
            "91da4f2fee328b4f81d7405fbcf4fbfed42e233914758ddd4178442487649a0d",
            "11d5fce94d80cba30e01a5492ff55a374ae229d6cdadf239b7dfb6a6e43b08e3",
        ),
    ),
    (
        "h107 Round-24 parameters",
        ROOT / "capture-kit" / "inputs" / "constraint_round24_parameters_h107.txt",
        "constraint_round24_parameters",
        (
            "75be24e60d7ab2448c30e67d2b92f96f254515b01ba93d0ae244241ee34d8d96",
            "191bfc38bca154cd67ca5cf0013c1f6a61637834195831123a594b7ccb5b0f82",
            "b23dfdabea8b3e3e608847c3709475aa7eb790700a6fa98e8316be08cab00c41",
        ),
    ),
    (
        "h108 reduced-table parameters",
        ROOT
        / "capture-kit"
        / "inputs"
        / "constraint_reduced_table_parameters_h108.txt",
        "constraint_reduced_table_parameters",
        (
            "4b3a693b66eb835c32b7465c7df8430397cbbaf05a1040c8cd911ceca3c789ba",
            "1043da7d8a3b7363933352509b797bfe9c0681ad8291b4c4406178207afdc7b0",
            "f48a2f1c30c9f344e32a95ad30170140d27ad65f541a90da97e5ec0cee190222",
        ),
    ),
)
NEW_TARGET_FILES = tuple(
    f"{prefix}_{rc}.txt"
    for _, _, prefix, _ in NEW_TARGETS
    for rc in h58.RCS
)


def load_directory(path: pathlib.Path) -> dict[str, bytes]:
    candidates = (path, path / "out", path / "constraint-out")
    directory = next(
        (
            candidate
            for candidate in candidates
            if candidate.is_dir()
            and any((candidate / name).exists() for name in (
                "cpu_info.txt", "dense_rn.txt",
                *H59_FILES, *H62_FILES, *H65_FILES,
                *H71_FILES, *H74_FILES, *H67_FILES, *H78_FILES,
                *NEW_TARGET_FILES,
            ))
        ),
        None,
    )
    if directory is None:
        raise SystemExit(f"no capture output directory found under {path}")
    return {
        child.name: child.read_bytes()
        for child in directory.iterdir()
        if child.is_file()
    }


def load_archive(path: pathlib.Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    with tarfile.open(path, "r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            member_path = pathlib.PurePosixPath(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise SystemExit(f"unsafe archive member name: {member.name}")
            if member.size > 128 * 1024 * 1024:
                raise SystemExit(f"archive member is unexpectedly large: {member.name}")
            name = member_path.name
            source = archive.extractfile(member)
            if source is None:
                raise SystemExit(f"cannot read archive member: {member.name}")
            contents = source.read()
            if name in files and files[name] != contents:
                raise SystemExit(f"archive contains conflicting {name} files")
            files[name] = contents
    if not files:
        raise SystemExit(f"archive contains no regular files: {path}")
    return files


def load_capture(path: pathlib.Path) -> dict[str, bytes]:
    return load_directory(path) if path.is_dir() else load_archive(path)


def verify_manifest(files: dict[str, bytes]) -> tuple[str, int] | None:
    for manifest_name, algorithm in (
        ("SHA256SUMS", "sha256"),
        ("MD5SUMS", "md5"),
    ):
        manifest = files.get(manifest_name, b"").decode(
            "ascii", errors="strict"
        )
        rows = [line.split() for line in manifest.splitlines() if line.strip()]
        if not rows:
            continue
        checked = 0
        for row in rows:
            if len(row) != 2:
                raise SystemExit(f"malformed {manifest_name} row: {' '.join(row)}")
            expected, listed_name = row
            name = pathlib.PurePosixPath(listed_name.lstrip("*")).name
            if name not in files:
                raise SystemExit(f"{manifest_name} lists missing file: {name}")
            actual = hashlib.new(algorithm, files[name]).hexdigest()
            if actual.lower() != expected.lower():
                raise SystemExit(
                    f"{manifest_name} mismatch for {name}: "
                    f"expected {expected}, got {actual}"
                )
            checked += 1
        return algorithm, checked
    return None


def cpu_summary(files: dict[str, bytes]) -> str:
    text = files.get("cpu_info.txt", b"").decode("utf-8", errors="replace")

    def field(name: str) -> str:
        match = re.search(rf"(?m)^{re.escape(name)}\s*:\s*(.+)$", text)
        return match.group(1).strip() if match else "?"

    return (
        f"{field('vendor_id')} {field('model name')} "
        f"(family {field('cpu family')}, model {field('model')}, "
        f"stepping {field('stepping')})"
    )


def parse_points(
    input_lines: list[str],
    outputs: list[list[str]],
    predicate: Callable[[int, int], bool] | None = None,
) -> list[h58.RawPoint]:
    if any(len(lines) != len(input_lines) for lines in outputs):
        raise SystemExit(
            "capture line count differs from its versioned input set: "
            f"inputs={len(input_lines)}, outputs={[len(lines) for lines in outputs]}"
        )
    points = []
    for index, line in enumerate(input_lines):
        se_text, sig_text = line.split()
        se, sig = int(se_text, 16), int(sig_text, 16)
        if predicate is not None and not predicate(se, sig):
            continue
        points.append(
            h58.RawPoint(
                index=index,
                sign=se >> 15,
                exponent=(se & 0x7FFF) - 16383,
                sig=sig,
                hw=tuple(h58.parse_sincos(lines[index]) for lines in outputs),
            )
        )
    return points


def score_with_tail(
    raw_points: list[h58.RawPoint],
    choose_tail: Callable[[h58.PreparedPoint], h58.TailConfig],
) -> h58.Score:
    score = h58.Score()
    for raw in raw_points:
        point = h58.prepare(raw, h58.BASE_PRODUCER)
        score.total_outputs += 2
        values = h58.table_tail(point, choose_tail(point))
        region = "wide" if point.wide else "narrow"
        for side, value in enumerate(values):
            output_missed = False
            for rc_index, rc in enumerate(h58.RCS):
                mismatch = h58.x87_round(value, rc) != raw.hw[rc_index][side]
                score.mode_misses += mismatch
                score.by_region[(region, f"{'sc'[side]}-{rc}")] += mismatch
                output_missed |= mismatch
                if rc == "rn":
                    score.rn_misses += mismatch
            score.constrained_output_misses += output_missed
    return score


def print_score(name: str, score: h58.Score) -> None:
    print(f"  {name:9s} {score.describe()}")
    for key in sorted(score.by_region):
        if score.by_region[key]:
            print(f"             {key[0]:6s} {key[1]}: {score.by_region[key]:.0f}")


def score_target(files: dict[str, bytes]) -> None:
    present = [name for name in H59_FILES if name in files]
    if not present:
        print("h59 target: not present (legacy capture)")
        return
    if len(present) != len(H59_FILES):
        missing = sorted(set(H59_FILES) - set(present))
        raise SystemExit(f"incomplete h59 capture; missing: {', '.join(missing)}")

    hashes = {
        name: hashlib.sha256(files[name]).hexdigest() for name in H59_FILES
    }
    matching = [
        name for name in H59_FILES
        if hashes[name] == SKYLAKE_H59_SHA256[name]
    ]
    if len(matching) == len(H59_FILES):
        print("h59 target: byte-identical to Skylake in RN/RD/RU")
    else:
        print(f"h59 target: {len(matching)}/3 modes byte-identical to Skylake")
        for name in H59_FILES:
            state = "same" if name in matching else "DIFFERENT"
            print(f"  {name}: {hashes[name]} ({state})")

    input_lines = H59_INPUTS.read_text().splitlines()
    output_lines = [
        files[f"constraint_narrow_{rc}.txt"].decode("ascii").splitlines()
        for rc in h58.RCS
    ]
    raw = parse_points(input_lines, output_lines)
    print(f"h59 score ({len(raw)} inputs, {2 * len(raw)} outputs):")
    print_score("baseline", score_with_tail(raw, lambda _: h58.BASE))
    print_score("round16", score_with_tail(raw, lambda _: h58.NARROW_TAIL))


def score_mwidth(files: dict[str, bytes]) -> None:
    present = [name for name in H62_FILES if name in files]
    if not present:
        print("h62 m-width target: not present")
        return
    if len(present) != len(H62_FILES):
        missing = sorted(set(H62_FILES) - set(present))
        raise SystemExit(f"incomplete h62 capture; missing: {', '.join(missing)}")

    hashes = {
        name: hashlib.sha256(files[name]).hexdigest() for name in H62_FILES
    }
    matching = [
        name for name in H62_FILES
        if hashes[name] == SKYLAKE_H62_SHA256[name]
    ]
    if len(matching) == len(H62_FILES):
        print("h62 m-width target: byte-identical to Skylake in RN/RD/RU")
    else:
        print(
            f"h62 m-width target: {len(matching)}/3 modes "
            "byte-identical to Skylake"
        )
        for name in H62_FILES:
            state = "same" if name in matching else "DIFFERENT"
            print(f"  {name}: {hashes[name]} ({state})")

    input_lines = H62_INPUTS.read_text().splitlines()
    output_lines = [
        files[f"constraint_mwidth_{rc}.txt"].decode("ascii").splitlines()
        for rc in h58.RCS
    ]
    raw = parse_points(input_lines, output_lines)
    points = [h58.prepare(point, h58.BASE_PRODUCER) for point in raw]
    print(f"h62 score ({len(raw)} inputs, {2 * len(raw)} outputs):")
    for name, tail in h62.VARIANTS:
        print_score(name, h58.score_config(points, tail))


def score_poly(files: dict[str, bytes]) -> None:
    present = [name for name in H65_FILES if name in files]
    if not present:
        print("h65 polynomial target: not present")
        return
    if len(present) != len(H65_FILES):
        missing = sorted(set(H65_FILES) - set(present))
        raise SystemExit(
            f"incomplete h65 capture; missing: {', '.join(missing)}"
        )

    hashes = {
        name: hashlib.sha256(files[name]).hexdigest() for name in H65_FILES
    }
    matching = [
        name for name in H65_FILES
        if hashes[name] == SKYLAKE_H65_SHA256[name]
    ]
    if len(matching) == len(H65_FILES):
        print("h65 polynomial target: byte-identical to Skylake in RN/RD/RU")
    else:
        print(
            f"h65 polynomial target: {len(matching)}/3 modes "
            "byte-identical to Skylake"
        )
        for name in H65_FILES:
            state = "same" if name in matching else "DIFFERENT"
            print(f"  {name}: {hashes[name]} ({state})")

    input_lines = H65_INPUTS.read_text().splitlines()
    output_lines = [
        files[f"constraint_poly_{rc}.txt"].decode("ascii").splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_lines) for lines in output_lines):
        raise SystemExit("h65 capture line count differs from its input set")
    raw = []
    for index, line in enumerate(input_lines):
        se_text, sig_text = line.split()
        se, sig = int(se_text, 16), int(sig_text, 16)
        raw.append(
            h64.PolyRaw(
                index=index,
                sign=se >> 15,
                exponent=(se & 0x7FFF) - 16383,
                sig=sig,
                sincos=tuple(
                    h58.parse_sincos(lines[index])
                    for lines in output_lines
                ),
                standalone=h65.DUMMY_OUTPUT,
            )
        )
    print(f"h65 score ({len(raw)} inputs, {2 * len(raw)} outputs):")
    configs = (
        (
            "baseline",
            h58.BASE_PRODUCER,
            h64.SIN_BASE,
            h64.COS_BASE,
            None,
        ),
        (
            "round18",
            h65.CANDIDATE_PRODUCER,
            h65.CANDIDATE_SIN,
            h65.CANDIDATE_COS,
            h65.CANDIDATE_Q_FINAL_PRODUCT_BITS,
        ),
    )
    for (
        name,
        producer,
        sine_tail,
        cosine_tail,
        q_final_product_bits,
    ) in configs:
        mode, outputs, rn, by_side = h65.score_config(
            raw,
            producer,
            sine_tail,
            cosine_tail,
            q_final_product_bits,
        )
        print(
            f"  {name:9s} {mode}/{6 * len(raw)} mode, "
            f"{outputs}/{2 * len(raw)} output, "
            f"{rn}/{2 * len(raw)} RN"
        )
        for key in sorted(by_side):
            if by_side[key]:
                print(f"             {key[0]}-{key[1]}: {by_side[key]}")


def score_poly_product_target(
    files: dict[str, bytes],
    label: str,
    inputs: pathlib.Path,
    prefix: str,
    names: tuple[str, ...],
    expected_hashes: dict[str, str],
) -> None:
    present = [name for name in names if name in files]
    if not present:
        print(f"{label} polynomial-product target: not present")
        return
    if len(present) != len(names):
        missing = sorted(set(names) - set(present))
        raise SystemExit(
            f"incomplete {label} capture; missing: {', '.join(missing)}"
        )

    hashes = {
        name: hashlib.sha256(files[name]).hexdigest() for name in names
    }
    matching = [
        name for name in names
        if hashes[name] == expected_hashes[name]
    ]
    if len(matching) == len(names):
        print(
            f"{label} polynomial-product target: "
            "byte-identical to Skylake in RN/RD/RU"
        )
    else:
        print(
            f"{label} polynomial-product target: {len(matching)}/3 modes "
            "byte-identical to Skylake"
        )
        for name in names:
            state = "same" if name in matching else "DIFFERENT"
            print(f"  {name}: {hashes[name]} ({state})")

    input_lines = inputs.read_text().splitlines()
    output_lines = [
        files[f"{prefix}_{rc}.txt"].decode("ascii").splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_lines) for lines in output_lines):
        raise SystemExit(
            f"{label} capture line count differs from its input set"
        )
    raw = []
    for index, line in enumerate(input_lines):
        se_text, sig_text = line.split()
        se, sig = int(se_text, 16), int(sig_text, 16)
        raw.append(
            h64.PolyRaw(
                index=index,
                sign=se >> 15,
                exponent=(se & 0x7FFF) - 16383,
                sig=sig,
                sincos=tuple(
                    h58.parse_sincos(lines[index])
                    for lines in output_lines
                ),
                standalone=h65.DUMMY_OUTPUT,
            )
        )

    print(f"{label} score ({len(raw)} cosine outputs):")
    schedules = (
        ("direct", h73.DIRECT),
        ("final67", h73.ProductVariant(5, 67, "chop")),
        ("all67", h73.ProductVariant(0, 67, "chop")),
    )
    for name, variant in schedules:
        mode, outputs, rn = h73.score(raw, variant)
        print(
            f"  {name:8s} {mode}/{3 * len(raw)} mode, "
            f"{outputs}/{len(raw)} output, {rn}/{len(raw)} RN"
        )


def score_wide_producer(files: dict[str, bytes]) -> None:
    present = [name for name in H67_FILES if name in files]
    if not present:
        print("h67 wide-producer target: not present")
        return
    if len(present) != len(H67_FILES):
        missing = sorted(set(H67_FILES) - set(present))
        raise SystemExit(
            f"incomplete h67 capture; missing: {', '.join(missing)}"
        )

    hashes = {
        name: hashlib.sha256(files[name]).hexdigest() for name in H67_FILES
    }
    matching = [
        name for name in H67_FILES
        if hashes[name] == SKYLAKE_H67_SHA256[name]
    ]
    if len(matching) == len(H67_FILES):
        print(
            "h67 wide-producer target: "
            "byte-identical to Skylake in RN/RD/RU"
        )
    else:
        print(
            f"h67 wide-producer target: {len(matching)}/3 modes "
            "byte-identical to Skylake"
        )
        for name in H67_FILES:
            state = "same" if name in matching else "DIFFERENT"
            print(f"  {name}: {hashes[name]} ({state})")

    input_lines = H67_INPUTS.read_text().splitlines()
    output_lines = [
        files[f"constraint_wide_producer_{rc}.txt"]
        .decode("ascii").splitlines()
        for rc in h58.RCS
    ]
    raw = parse_points(input_lines, output_lines)
    print(f"h67 score ({len(raw)} inputs, {2 * len(raw)} outputs):")
    for profile in ("baseline", "p-only", "q-only", "both"):
        print_score(profile, h67.score_points(raw, profile))


def score_paired_table(files: dict[str, bytes]) -> None:
    present = [name for name in H78_FILES if name in files]
    if not present:
        print("h78 paired-table target: not present")
        return
    if len(present) != len(H78_FILES):
        missing = sorted(set(H78_FILES) - set(present))
        raise SystemExit(
            f"incomplete h78 capture; missing: {', '.join(missing)}"
        )

    hashes = {
        name: hashlib.sha256(files[name]).hexdigest()
        for name in H78_FILES
    }
    matching = [
        name for name in H78_FILES
        if hashes[name] == SKYLAKE_H78_SHA256[name]
    ]
    if len(matching) == len(H78_FILES):
        print(
            "h78 paired-table target: "
            "byte-identical to Skylake in RN/RD/RU"
        )
    else:
        print(
            f"h78 paired-table target: {len(matching)}/3 modes "
            "byte-identical to Skylake"
        )
        for name in H78_FILES:
            state = "same" if name in matching else "DIFFERENT"
            print(f"  {name}: {hashes[name]} ({state})")

    input_lines = H78_INPUTS.read_text().splitlines()
    output_lines = [
        files[f"constraint_paired_table_{rc}.txt"]
        .decode("ascii").splitlines()
        for rc in h58.RCS
    ]
    raw = parse_points(input_lines, output_lines)
    print(f"h78 score ({len(raw)} inputs, {2 * len(raw)} outputs):")
    for family, numerator in (("narrow", 4), ("wide", 5)):
        selected = [
            point
            for point in raw
            if (point.exponent == -1) == (family == "wide")
        ]
        baseline = h79.score(selected, h79.BASE, 0)
        round21 = h79.score(selected, h79.BASE, numerator)
        print_score(f"{family}-base", baseline)
        print_score(f"{family}-r21", round21)


def score_dense(files: dict[str, bytes]) -> None:
    names = tuple(f"dense_{rc}.txt" for rc in h58.RCS)
    present = [name for name in names if name in files]
    if not present:
        return
    if len(present) != len(names):
        missing = sorted(set(names) - set(present))
        raise SystemExit(f"incomplete dense rounding capture; missing: {', '.join(missing)}")
    input_lines = DENSE_INPUTS.read_text().splitlines()
    output_lines = [
        files[f"dense_{rc}.txt"].decode("ascii").splitlines()
        for rc in h58.RCS
    ]
    raw = parse_points(input_lines, output_lines, h58.is_direct_table)
    print(f"full direct-table score ({len(raw)} inputs, {2 * len(raw)} outputs):")
    print_score("baseline", score_with_tail(raw, lambda _: h58.BASE))
    print_score(
        "round16",
        score_with_tail(raw, lambda point: h58.BASE if point.wide else h58.NARROW_TAIL),
    )
    wide = [point for point in raw if point.exponent == -1]
    print(
        f"full direct-wide producer score "
        f"({len(wide)} inputs, {2 * len(wide)} outputs):"
    )
    print_score("baseline", h67.score_points(wide, "baseline"))
    print_score("round19", h67.score_points(wide, "q-only"))


def verify_new_targets(files: dict[str, bytes]) -> None:
    if not any(name in files for name in NEW_TARGET_FILES):
        print("h83-h108 targets: not present")
        return
    for label, inputs, prefix, expected_hashes in NEW_TARGETS:
        names = tuple(f"{prefix}_{rc}.txt" for rc in h58.RCS)
        present = [name for name in names if name in files]
        if not present:
            print(f"{label}: not present")
            continue
        if len(present) != len(names):
            missing = sorted(set(names) - set(present))
            raise SystemExit(
                f"incomplete {label} capture; missing: "
                f"{', '.join(missing)}"
            )
        input_count = len(inputs.read_text().splitlines())
        output_counts = [
            len(files[name].decode("ascii").splitlines())
            for name in names
        ]
        if any(count != input_count for count in output_counts):
            raise SystemExit(
                f"{label} line count differs from its input set: "
                f"inputs={input_count}, outputs={output_counts}"
            )
        hashes = tuple(
            hashlib.sha256(files[name]).hexdigest()
            for name in names
        )
        matching = sum(
            actual == expected
            for actual, expected in zip(hashes, expected_hashes)
        )
        print(
            f"{label}: {matching}/3 modes byte-identical to Skylake "
            f"({input_count} inputs)"
        )
        if matching != 3:
            for name, actual, expected in zip(
                names,
                hashes,
                expected_hashes,
            ):
                state = "same" if actual == expected else "DIFFERENT"
                print(f"  {name}: {actual} ({state})")


def compare_reference(
    files: dict[str, bytes], reference_path: pathlib.Path | None
) -> None:
    if reference_path is None or not reference_path.exists():
        return
    reference = load_capture(reference_path)
    compared = [name for name in LEGACY_FILES if name in files and name in reference]
    if not compared:
        return
    matching = [name for name in compared if files[name] == reference[name]]
    executions = sum(files[name].count(b"\n") for name in matching)
    print(
        f"legacy channels vs Pentium-II reference: "
        f"{len(matching)}/{len(compared)} byte-identical"
        + (f" ({executions:,} instruction executions)" if matching else "")
    )
    for name in compared:
        if name not in matching:
            print(f"  {name}: DIFFERENT")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=pathlib.Path)
    parser.add_argument(
        "--reference",
        type=pathlib.Path,
        default=DEFAULT_REFERENCE if DEFAULT_REFERENCE.exists() else None,
        help="legacy full-capture reference directory (default: local Pentium II)",
    )
    args = parser.parse_args()

    files = load_capture(args.capture)
    print(f"capture: {args.capture}")
    print(f"CPU: {cpu_summary(files)}")
    verified = verify_manifest(files)
    if verified is None:
        print("manifest: unavailable")
    else:
        print(f"manifest: {verified[0]} verified ({verified[1]} files)")
    compare_reference(files, args.reference)
    score_target(files)
    score_mwidth(files)
    score_poly(files)
    score_poly_product_target(
        files,
        "h71",
        H71_INPUTS,
        "constraint_poly_round75",
        H71_FILES,
        SKYLAKE_H71_SHA256,
    )
    score_poly_product_target(
        files,
        "h74",
        H74_INPUTS,
        "constraint_poly_product",
        H74_FILES,
        SKYLAKE_H74_SHA256,
    )
    score_wide_producer(files)
    score_paired_table(files)
    verify_new_targets(files)
    score_dense(files)


if __name__ == "__main__":
    main()

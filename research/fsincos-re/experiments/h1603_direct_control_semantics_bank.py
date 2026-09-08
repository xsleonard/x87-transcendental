#!/usr/bin/env python3
"""Read-only, authenticated all-mode control loader for direct FCOS semantics.

The public cached H1107 table supplies actual outputs; no model is executed,
no missing mode is synthesized, and absent status/C1/PC metadata stays absent.
The optional CLI writes only a provenance/membership manifest, not a new
capture kit or duplicate hardware-output bank.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


MODES = ("rn", "rd", "ru", "rz")
CONTROL_PATH = "tmp/ledger33/current/h1107_controls_allmodes.tsv"
SELECTION_PATH = "tmp/ledger33/current/h1094b_visible_controls.tsv"
CONTROL_SHA = "3004f7187da5e0972c4359c49151b4c51570c9beeb18048dbe6982821425c1e8"
SELECTION_SHA = "9a01217e0e893dd13cac77e148f94957b0ac55a82ae4b1f9c00cec0b8fe9c7be"
PRIOR_RC_REPORT = "tmp/ledger33/current/h1596_rounding_mode_feasibility.json"
PRIOR_RC_SHA = "8b87f3d340e0257d2ea7591ad5a02d87d9d1883f571644ddcb339209f4af64fa"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(lines) -> str:
    return hashlib.sha256("".join(lines).encode()).hexdigest()


def direct_positive(operand: str) -> bool:
    """Normalized external binary80 input in [1/8,1/4), with sign clear."""
    words = operand.split()
    if len(words) != 2:
        return False
    try:
        se, sig = (int(word, 16) for word in words)
    except ValueError:
        return False
    return se == 0x3FFC and 1 << 63 <= sig < 1 << 64


@dataclass(frozen=True)
class ObservedControl:
    operand: str
    # Exactly MODES order. Identical values in two modes do not collapse the
    # separate observations or manufacture an unobserved architectural lane.
    outputs: tuple[str, str, str, str]
    corpus: str
    capture_index_zero_based: int
    source_lines_one_based: tuple[int, int, int, int]

    def hardware(self, mode: str) -> str:
        return self.outputs[MODES.index(mode)]


@dataclass(frozen=True)
class ControlBank:
    controls: tuple[ObservedControl, ...]
    evidence: tuple[tuple[str, str], ...]
    selection_mode_counts: tuple[tuple[str, int], ...]
    original_h1094_field_counts: tuple[tuple[int, int], ...]


def strict_tsv(path: Path, expected_header: tuple[str, ...]) -> list[dict]:
    with path.open() as source:
        reader = csv.reader(source, delimiter="\t")
        assert tuple(next(reader)) == expected_header, path
        rows = []
        for line, fields in enumerate(reader, 2):
            assert len(fields) == len(expected_header), (path, line, len(fields))
            rows.append(dict(zip(expected_header, fields), source_line=line))
        return rows


def group_records(rows: list[dict]) -> tuple[ObservedControl, ...]:
    groups = defaultdict(dict)
    locations = {}
    for row in rows:
        assert row["insn"] == "cos" and row["mode"] in MODES
        operand = row["op"].lower()
        assert direct_positive(operand), ("outside direct positive domain", operand)
        mode = row["mode"]
        assert mode not in groups[operand], ("duplicate observed tuple", operand, mode)
        location = row["corpus"], int(row["index"])
        assert locations.setdefault(operand, location) == location
        groups[operand][mode] = row
    controls = []
    for operand, modes in sorted(groups.items()):
        assert set(modes) == set(MODES), ("missing actual mode", operand, sorted(modes))
        corpus, index = locations[operand]
        outputs = tuple(modes[mode]["hw"].lower() for mode in MODES)
        for output in outputs:
            se, sig = (int(word, 16) for word in output.split(":"))
            assert 0 < se < 0x7FFF and 1 << 63 <= sig < 1 << 64
        controls.append(ObservedControl(operand, outputs, corpus, index,
                                       tuple(modes[mode]["source_line"] for mode in MODES)))
    assert len(set(locations.values())) == len(locations), "one corpus index mapped to multiple operands"
    return tuple(controls)


def load_controls(root: Path) -> ControlBank:
    """Return an immutable observed bank; this function never writes files."""
    control_path, selection_path = root / CONTROL_PATH, root / SELECTION_PATH
    assert digest(control_path) == CONTROL_SHA
    assert digest(selection_path) == SELECTION_SHA
    prior_path = root / PRIOR_RC_REPORT
    assert digest(prior_path) == PRIOR_RC_SHA
    prior = json.loads(prior_path.read_text())
    assert prior["sha256"]["evidence"][CONTROL_PATH] == CONTROL_SHA
    h1590_path = root / "tmp/ledger33/current/h1590_signed_threshold_ub_audit/report.json"
    assert digest(h1590_path) == prior["sha256"]["evidence"][str(h1590_path.relative_to(root))]
    h1590 = json.loads(h1590_path.read_text())
    assert h1590["sha256"]["evidence"][CONTROL_PATH] == CONTROL_SHA
    cache_audit_path = root / "tmp/ledger33/current/h1291_faddword_valid_cache_audit.txt"
    assert digest(cache_audit_path) == prior["sha256"]["evidence"][str(cache_audit_path.relative_to(root))]
    cache_pins = dict(line.split("\t", 1) for line in cache_audit_path.read_text().splitlines() if "\t" in line)
    assert cache_pins["score_sha256." + control_path.name] == CONTROL_SHA
    assert cache_pins["score_sha256." + selection_path.name] == SELECTION_SHA
    rows = strict_tsv(control_path, ("insn", "mode", "op", "hw", "corpus", "index"))
    controls = group_records(rows)
    assert len(rows) == 149764 and len(controls) == 37441
    selection = strict_tsv(selection_path, ("insn", "mode", "op", "hw", "base", "fminus2", "fplus1", "corpus", "index"))
    assert len(selection) == len(controls)
    by_location = {(c.corpus, c.capture_index_zero_based): c for c in controls}
    seen = set()
    for row in selection:
        location = row["corpus"], int(row["index"])
        assert location not in seen
        seen.add(location)
        observed = by_location[location]
        assert observed.operand == row["op"]
        assert observed.hardware(row["mode"]) == row["hw"]
        # These assertions document the old selection bias, never generate
        # truth from a model: the hardware values came from the raw table.
        assert row["base"] == row["hw"]
        assert row["fminus2"] != row["fplus1"]
    assert seen == set(by_location)
    # The original H1094 artifact has a nine-field header but only four data
    # fields. Use the authenticated H1094b correction for index provenance.
    original = root / "tmp/ledger33/current/h1094_visible_controls.tsv"
    assert digest(original) == cache_pins["score_sha256." + original.name]
    with original.open() as source:
        original_rows = list(csv.reader(source, delimiter="\t"))
    field_counts = Counter(len(r) for r in original_rows)
    assert field_counts == {9: 1, 4: 37441}
    assert original_rows[1:] == [[r[k] for k in ("insn", "mode", "op", "hw")] for r in selection]
    named_op = set()
    for bank_name in ("named_direct_82_only", "historical_h1091_allmode"):
        named_op.update(r["operand"] for r in prior["banks"][bank_name]["groups"])
    assert not named_op.intersection(c.operand for c in controls)
    evidence = {}
    for path in (control_path, selection_path, prior_path, h1590_path, cache_audit_path, original,
                 root / "experiments/h1107_cached_controls_allmodes.py",
                 root / "experiments/h1094_cached_r59_visible.sh"):
        relative = str(path.relative_to(root))
        evidence[relative] = digest(path)
        if relative in prior["sha256"]["evidence"]:
            assert evidence[relative] == prior["sha256"]["evidence"][relative]
    return ControlBank(controls, tuple(sorted(evidence.items())),
                       tuple(sorted(Counter(r["mode"] for r in selection).items())),
                       tuple(sorted(field_counts.items())))


def manifest(bank: ControlBank) -> dict:
    indices = defaultdict(list)
    for c in bank.controls:
        indices[c.corpus].append(c.capture_index_zero_based)
    return {
        "experiment": "h1603_direct_control_semantics_bank",
        "artifact_kind": "existing_observation_membership_and_provenance_not_capture_manifest",
        "hardware_execution": "none", "missing_modes_inferred": 0, "model_outputs_used_as_truth": False,
        "scope": "positive_normal_direct_FCOS_1over8_inclusive_to_1over4_exclusive",
        "operands": len(bank.controls), "observed_rows": len(bank.controls) * len(MODES),
        "mode_order": MODES, "actual_modes_per_operand": 4,
        "minimum_operand": bank.controls[0].operand, "maximum_operand": bank.controls[-1].operand,
        "by_corpus_operands": {name: len(values) for name, values in sorted(indices.items())},
        "original_capture_indices_zero_based_by_corpus": {name: sorted(values) for name, values in sorted(indices.items())},
        "ordered_operand_sha256": canonical_hash(c.operand + "\n" for c in bank.controls),
        "ordered_observed_tuple_sha256": canonical_hash(
            "fcos " + mode + " " + c.operand + " " + c.hardware(mode) + "\n"
            for c in bank.controls for mode in MODES),
        "metadata_not_retained_in_H1107": ["status_word", "C1", "precision_control", "per_row_CPUID"],
        "missing_metadata_policy": "unknown_not_zero_no_status_or_PC_inference",
        "overlap_with_named82_or_historical29_operands": 0,
        "selection": {
            "kind": "deterministic_sample_of_retained_correction_endpoint_visible_incumbent_exact_rows",
            "original_selection_modes": dict(bank.selection_mode_counts),
            "not_claimed": ["fresh_validation", "random_sampling", "global_accuracy", "independent_of_all_prior_searches"],
        },
        "provenance_warning": {
            "original_h1094_field_counts_including_header": dict(bank.original_h1094_field_counts),
            "used_for_capture_index_provenance": SELECTION_PATH,
            "original_truncated_file_used_for": "four_field_instruction_mode_operand_hardware_crosscheck_only",
            "raw_capture_streams": "original_h1107_importer_read_four_existing_corpus_status_streams_after_input_index_checks",
            "current_readiness_audit": "local_authenticated_extract_and_crosschecks_no_remote_fetch_or_new_raw_status_claim",
        },
        "sha256": {"script": digest(Path(__file__)), "evidence": dict(bank.evidence)},
    }


def selftest() -> dict:
    assert direct_positive("3ffc 8000000000000000")
    assert direct_positive("3ffc ffffffffffffffff")
    for operand in ("3ffb ffffffffffffffff", "3ffd 8000000000000000", "bffc 8000000000000000",
                    "3ffc 7fffffffffffffff", "3ffc 10000000000000000", "invalid", "no hex"):
        assert not direct_positive(operand)
    rows = [dict(insn="cos", mode=mode, op="3ffc 8000000000000000", hw="3ffe:ffffffffffffffff",
                 corpus="selftest", index="1", source_line=i+2) for i, mode in enumerate(MODES)]
    controls = group_records(rows)
    assert len(controls) == 1 and controls[0].hardware("rz") == rows[3]["hw"]
    rejected = 0
    for malformed in (rows[:-1], rows + [rows[0]], rows[:3] + [dict(rows[3], index="2")]):
        try:
            group_records(malformed)
        except AssertionError:
            rejected += 1
        else:
            raise AssertionError("invalid observed bank admitted")
    assert rejected == 3
    return {"domain_cases": 9, "complete_mode_group_case": 1, "malformed_bank_rejections": rejected}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    tests = selftest()
    if a.selftest:
        print(json.dumps(tests, sort_keys=True))
        return
    assert a.root and a.output
    if a.output.exists():
        raise SystemExit("refusing existing manifest")
    bank = load_controls(a.root)
    result = manifest(bank)
    result["selftest"] = tests
    with a.output.open("x") as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps({k: result[k] for k in ("operands", "observed_rows", "by_corpus_operands",
                                          "ordered_operand_sha256", "ordered_observed_tuple_sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()

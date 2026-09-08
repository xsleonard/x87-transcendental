#!/usr/bin/env python3
"""Replay saved F2XM1 rounding regressions in C and exact rational arithmetic.

The compact fixture contains original hardware lines and their archive offsets.
Its digest is pinned here. With --authenticate-archives, also verify both full
capture streams and compare every selected line with its source archive.
This test never runs a native F2XM1 instruction or requests a new capture.
"""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
FIXTURE_SHA256 = "56f0ac1bd9763c8f921cf84a58be0dceacc106b4f096b73590253aae02e19fbe"
MODES = ("rn", "rd", "ru", "rz")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_reference(path):
    spec = importlib.util.spec_from_file_location("f2xm1_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_constants(path):
    def literal(value):
        scale = value["scale"]
        power = Fraction(1 << scale) if scale >= 0 else Fraction(1, 1 << -scale)
        return (-1 if value["sign"] else 1) * int(value["significand"], 16) * power

    values = json.loads(path.read_text())["constants"]
    return {key: (literal(value) if key == "F2_LN2" else
                  {int(b): tuple(literal(v) for v in pair) for b, pair in value.items()}
                  if key == "TABLE" else [literal(v) for v in value])
            for key, value in values.items()}


def parse_hardware(line):
    fields = line.split()
    assert len(fields) == 11, "hardware field count"
    ident, rc, pc, se, sig = fields[:5]
    assert rc in MODES and pc in ("24", "53", "64")
    key = f"f2xm1-v1-masked-clear-depth1:{rc}:{pc}:{se}:{sig}"
    assert digest(key.encode())[:40] == ident, "input identity"
    cw, before, after, end, out_se, out_sig = map(lambda x: int(x, 16), fields[5:])
    wanted_cw = 0x7f | {24: 0, 53: 0x200, 64: 0x300}[int(pc)] | MODES.index(rc) << 10
    assert cw == wanted_cw, "control word"
    assert tuple((v >> 11) & 7 for v in (before, after, end)) == (7, 7, 0), "stack balance"
    return fields[:5], (out_se, out_sig, (after >> 9) & 1)


def authenticate(fixture, directory):
    for capture in fixture["captures"]:
        job = directory / capture["job"]
        manifest_data = (job / "MANIFEST.json").read_bytes()
        assert digest(manifest_data) == capture["manifest_sha256"], "capture manifest"
        manifest = json.loads(manifest_data)
        assert manifest["signature"] == capture["signature"]
        assert manifest["microcode"] == capture["microcode"]
        compressed = (job / "hardware.txt.gz").read_bytes()
        assert digest(compressed) == capture["hardware_gzip_sha256"], "compressed capture"
        raw = gzip.decompress(compressed)
        assert digest(raw) == capture["hardware_sha256"], "raw capture"
        lines = raw.decode().splitlines()
        assert len(lines) == capture["rows"], "capture row count"
        for case in fixture["cases"]:
            assert lines[case["archive_line"] - 1] == case["hardware"], "fixture extraction"


def check(fixture, driver, reference, constants):
    parsed = [parse_hardware(case["hardware"]) for case in fixture["cases"]]
    inputs = "".join(" ".join(fields) + "\n" for fields, _ in parsed)
    run = subprocess.run([str(driver.resolve())], input=inputs, text=True,
                         capture_output=True, check=True)
    assert not run.stderr, run.stderr
    predictions = run.stdout.splitlines()
    assert len(predictions) == len(parsed), "C result count"
    misses = Counter()
    controls = defaultdict(set)
    purposes = Counter()
    for case, (fields, expected), output in zip(fixture["cases"], parsed, predictions, strict=True):
        ident, rc, pc, se, sig = fields
        p = output.split()
        assert len(p) == 4 and p[0] == ident, "C output identity"
        c_value = (int(p[1], 16), int(p[2], 16), int(p[3]))
        raw, _, c1, _ = reference.evaluate("F2XM1", int(se, 16), int(sig, 16), rc, constants)
        misses["C_output"] += c_value[:2] != expected[:2]
        misses["C_C1"] += c_value[2] != expected[2]
        misses["rational_output"] += raw != expected[:2]
        misses["rational_C1"] += c1 != expected[2]
        controls[(se, sig)].add((rc, int(pc)))
        purposes[case["purpose"]] += 1
    assert all(len(v) == 12 for v in controls.values()), "missing RC/PC combination"
    assert {int(se, 16) >> 15 for se, _ in controls} == {0, 1}, "missing sign"
    assert not any(misses.values()), dict(misses)
    return dict(rows=len(parsed), operands=len(controls), misses=dict(misses),
                purposes=dict(purposes), hardware_executed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("driver", nargs="?", type=Path, default=HERE / "test_f2xm1_driver")
    parser.add_argument("--reference", type=Path, default=HERE.parent / "docs/sibling_reference.py")
    parser.add_argument("--authenticate-archives", type=Path)
    args = parser.parse_args()
    fixture_data = (HERE / "f2xm1_regressions.json").read_bytes()
    assert digest(fixture_data) == FIXTURE_SHA256, "regression fixture digest"
    fixture = json.loads(fixture_data)
    if args.authenticate_archives:
        authenticate(fixture, args.authenticate_archives)
    result = check(fixture, args.driver, load_reference(args.reference),
                   load_constants(HERE.parent / "docs/sibling-constants.json"))
    result["full_archives_authenticated"] = bool(args.authenticate_archives)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

"""Replay published sibling pseudocode against authenticated saved hardware.

This tool never captures hardware. It parses raw records and calls only the
exact-rational specification, not production or historical candidate code.
"""
import argparse
from collections import Counter
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

from suite_support import PROJECT, digest, sibling_constants, write_json
sys.path.insert(0, str(PROJECT / "docs"))
import sibling_reference as reference


def f2xm1(constants):
    capture = PROJECT / "capture-kit-captures/skylake-f2xm1-h257"
    inputs = PROJECT / "capture-kit/inputs/f2xm1_validation_h257.txt"
    for row in (capture / "SHA256SUMS").read_text().splitlines():
        sha, name = row.split(None, 1)
        assert digest(capture / name.strip().lstrip("*")) == sha
    pairs = [tuple(int(v, 16) for v in line.split()) for line in inputs.read_text().splitlines()]
    counts, witnesses = Counter(), []
    for mode in ("rn", "rd", "ru"):
        path = capture / f"f2xm1_validation_h257_{mode}_status.txt"
        for (se, sig), line in zip(pairs, path.read_text().splitlines(), strict=True):
            f = line.split()
            assert len(f) == 5 and f[0] == "OK" and f[3] == "SW"
            raw, _, c1, c2 = reference.evaluate("F2XM1", se, sig, mode, constants)
            actual = (int(f[1], 16), int(f[2], 16))
            sw = int(f[4], 16)
            misses = dict(output_misses=int(raw != actual), C1_misses=int(c1 != ((sw >> 9) & 1)))
            counts.update(rows=1, **misses)
            counts[f"RC:{mode}"] += 1
            assert not any(misses.values()), (mode, se, sig, raw, actual, c1, sw)
            if len(witnesses) < 12:
                witnesses.append(dict(instruction="F2XM1", mode=mode, input=[f"{se:04x}", f"{sig:016x}"],
                                      result=[f"{raw[0]:04x}", f"{raw[1]:016x}"], C1=c1))
    return dict(counts=counts, input_sha256=digest(inputs),
                capture_manifest_sha256=digest(capture / "SHA256SUMS"),
                hardware_files={p.name:digest(p) for p in capture.glob("*_status.txt")},
                witnesses=witnesses,
                scope="H257 saved input/output rows, RN/RD/RU; no inference of full raw80/state coverage")


def fptan(constants):
    base = PROJECT / "tmp/fptan-re"
    # Memoization only changes replay cost; the arithmetic code is unchanged.
    original = reference.fptan_ratio
    cached = lru_cache(maxsize=140000)(lambda x: original(x, constants))
    reference.fptan_ratio = lambda x, _: cached(x)
    reports = {}
    for name in ("t0002", "t0003"):
        folder = base / name
        manifest = json.loads((folder / "MANIFEST.json").read_text())
        complete = json.loads((folder / "COMPLETE.json").read_text())
        assert complete["state"] == "OBSERVED"
        assert digest(folder / "MANIFEST.json") == complete["manifest_sha256"]
        assert digest(folder / "inputs.txt.gz") == manifest["files"]["inputs.txt.gz"]
        assert digest(folder / "hardware.txt.gz") == complete["hardware_gzip_sha256"]
        counts, raw_hash = Counter(), hashlib.sha256()
        with gzip.open(folder / "inputs.txt.gz", "rt") as src, gzip.open(folder / "hardware.txt.gz", "rt") as obs:
            for request, observed in zip(src, obs, strict=True):
                f, h = request.split(), observed.split()
                assert len(f) == 5 and len(h) == 13 and h[:5] == f
                mode, pc = f[1], int(f[2])
                se, sig = int(f[3], 16), int(f[4], 16)
                key = f"fptan-v1-masked-clear-depth1:{mode}:{pc}:{se:04x}:{sig:016x}"
                assert hashlib.sha256(key.encode()).hexdigest()[:40] == f[0]
                cw, before, after, end, hs, hm, ps, pm = (int(v, 16) for v in h[5:])
                wanted = 0x7f | {24:0, 53:0x200, 64:0x300}[pc] | ("rn", "rd", "ru", "rz").index(mode) << 10
                assert cw == wanted
                c2 = (after >> 10) & 1
                assert ((before >> 11) & 7, (after >> 11) & 7, (end >> 11) & 7) == (7, 7 if c2 else 6, 0)
                raw, pushed, c1, predicted_c2 = reference.evaluate("FPTAN", se, sig, mode, constants)
                misses = dict(output_misses=int(raw != (hs, hm)),
                              pushed_misses=int((pushed or (0, 0)) != (ps, pm)),
                              C1_misses=int(c1 != ((after >> 9) & 1)), C2_misses=int(predicted_c2 != c2))
                counts.update(rows=1, **misses)
                counts[f"RC:{mode}"] += 1
                counts[f"PC:{pc}"] += 1
                counts["range_returns" if c2 else "successful"] += 1
                assert not any(misses.values()), (name, request, raw, pushed, c1, predicted_c2, h)
                raw_hash.update(observed.encode())
                if counts["rows"] % 100000 == 0:
                    print(name, counts["rows"], "rows pass", flush=True)
        assert counts["rows"] == complete["rows"] == manifest["rows"]
        assert raw_hash.hexdigest() == complete["hardware_sha256"]
        reports[name] = dict(counts=counts, input_sha256=digest(folder / "inputs.txt.gz"),
                             hardware_sha256=raw_hash.hexdigest(),
                             manifest_sha256=digest(folder / "MANIFEST.json"),
                             complete_sha256=digest(folder / "COMPLETE.json"),
                             signature=manifest["signature"], microcode=manifest["microcode"])
    assert reports["t0002"]["hardware_sha256"] == reports["t0003"]["hardware_sha256"]
    reference.fptan_ratio = original
    return dict(jobs=reports, scope="Normal-finite T0002/T0003; result, push, C1/C2; not exception-latch prediction")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruction", choices=("f2xm1", "fptan"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("Choose a new output path; verification receipts are preserved.")
    constants = sibling_constants()
    started = time.time()
    result = (f2xm1 if args.instruction == "f2xm1" else fptan)(constants)
    write_json(args.out, dict(status="PASS", hardware_executed=False,
        instruction=args.instruction.upper(), result=result, elapsed_seconds=time.time()-started,
        specification_sha256=digest(PROJECT / "docs/sibling_reference.py"),
        constants_sha256=digest(PROJECT / "docs/sibling-constants.json"),
        verifier_sha256=digest(Path(__file__))))
    print("PASS",args.instruction,"in",round(time.time()-started,1),"seconds",flush=True)


if __name__ == "__main__":
    main()

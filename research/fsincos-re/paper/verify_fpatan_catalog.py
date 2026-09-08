"""Replay the canonical FPATAN Markdown against the current saved catalog.

Unlike the historical publication-snapshot verifier, this tool discovers
only the named catalog packs. It never re-captures or modifies observations.
"""
import argparse
from collections import Counter
import csv
from fractions import Fraction
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from suite_support import PROJECT, digest, pseudocode_program_digest, write_json


def load_reference():
    rom = {}
    with (PROJECT / "data/pentium-rom/rom-constants.tsv").open() as f:
        for row in csv.DictReader(f, delimiter="\t"):
            i = int(row["row"])
            if i in (19, 20) or 114 <= i <= 123 or 125 <= i <= 156:
                e = int(row["exp"], 16) - 0xffff - 66
                n = int(row["sig68"], 16) * (-1 if int(row["sign"]) else 1)
                rom[i] = Fraction(n << e) if e >= 0 else Fraction(n, 1 << -e)
    path = PROJECT / "fpatan-re/PSEUDOCODE.md"
    blocks = re.findall(r"^```python\n(.*?)^```", path.read_text(), re.M | re.S)
    assert len(blocks) == 5 and len(rom) == 44
    ns = {"ROM": rom}
    exec(compile("\n".join(blocks), str(path), "exec"), ns)
    ns["finite_angle"] = lru_cache(maxsize=8192)(ns["finite_angle"])
    return ns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("Use a new report path")
    ns = load_reference()
    catalog_path = PROJECT / "fpatan-re/corpus-v1/CATALOG-D0066.json"
    catalog = json.loads(catalog_path.read_text())
    totals, jobs = Counter(), {}
    started = time.time()
    for name, pack in catalog["packs"].items():
        job = PROJECT / "tmp/fpatan-re" / name
        manifest = json.loads((job / "MANIFEST.json").read_text())
        complete = json.loads((job / "COMPLETE.json").read_text())
        assert complete["state"] == "OBSERVED"
        assert digest(job / "MANIFEST.json") == complete["manifest_sha256"]
        zipped = (job / "inputs.txt.gz").exists()
        ip = job / ("inputs.txt.gz" if zipped else "inputs.txt")
        hp = job / ("hardware.txt.gz" if zipped else "hardware.txt")
        assert digest(ip) == manifest["files"][ip.name]
        assert digest(hp) == complete["hardware_gzip_sha256" if zipped else "hardware_sha256"]
        counts, h = Counter(), hashlib.sha256()
        opener = gzip.open if zipped else open
        with opener(ip, "rt") as src, opener(hp, "rt") as obs:
            for request, observed in zip(src, obs, strict=True):
                f, o = request.split(), observed.split()
                assert o[:7] == f and len(o) == 12
                ys, ym, xs, xm = (int(v, 16) for v in f[3:])
                value, c1, flags, before = ns["fpatan"](
                    ns["Raw80"](ys, ym), ns["Raw80"](xs, xm), f[1].upper(), int(f[2]))
                cw, pre, sw, se, sig = (int(v, 16) for v in o[7:])
                wanted = 0x7f | {"24":0,"53":0x200,"64":0x300}[f[2]] | ("rn","rd","ru","rz").index(f[1]) << 10
                assert cw == wanted
                checks = dict(output_misses=int(value != (se, sig)), C1_misses=int(c1 != ((sw >> 9) & 1)),
                              exception_misses=int(flags != (sw & 63)), preload_misses=int(before != (pre & 63)))
                assert not any(checks.values()), (name, request, checks, observed)
                counts.update(rows=1, **checks)
                counts[f"rc:{f[1]}"] += 1
                counts[f"pc:{f[2]}"] += 1
                h.update(observed.encode())
        assert counts["rows"] == complete["rows"] == manifest["rows"] == pack["counts"]["rows"]
        assert h.hexdigest() == complete["hardware_sha256"]
        jobs[name] = dict(counts=counts, hardware_sha256=h.hexdigest(), input_sha256=digest(ip),
                          manifest_sha256=digest(job / "MANIFEST.json"))
        totals.update(counts)
        print(name,counts["rows"],"PASS; elapsed",round(time.time()-started,1),flush=True)
    assert {k:totals[k] for k in catalog["counts"]} == catalog["counts"]
    write_json(args.out, dict(status="PASS", hardware_executed=False, counts=totals, jobs=jobs,
        pseudocode_sha256=digest(PROJECT / "fpatan-re/PSEUDOCODE.md"),
        pseudocode_program_sha256=pseudocode_program_digest(PROJECT / "fpatan-re/PSEUDOCODE.md"),
        catalog_sha256=digest(catalog_path), verifier_sha256=digest(Path(__file__)),
        elapsed_seconds=time.time()-started, scope="23 named Skylake packs; no new hardware or all-input proof"))


if __name__ == "__main__":
    main()

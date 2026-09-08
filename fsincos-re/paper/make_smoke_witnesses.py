"""Extract a bounded, deterministic set of saved hardware records for release.

Selection uses row positions and declared controls, never model predictions.
Full source-file digests connect each witness to its authenticated archive.
This extractor needs the research archive; the resulting JSON replay does not.
"""
from collections import Counter
import gzip
import json
from suite_support import HERE, PROJECT, digest, write_json


def main():
    rows, sources = [], {}

    def source(path):
        key = str(path.relative_to(PROJECT))
        sources[key] = digest(path)
        return key

    ip = PROJECT / "capture-kit/inputs/f2xm1_validation_h257.txt"
    source(ip)
    inputs = ip.read_text().splitlines()
    positions = {n*(len(inputs)-1)//23 for n in range(24)}
    for rc in ("rn", "rd", "ru"):
        hp = PROJECT / f"capture-kit-captures/skylake-f2xm1-h257/f2xm1_validation_h257_{rc}_status.txt"
        key = source(hp)
        for n, (inp, line) in enumerate(zip(inputs, hp.read_text().splitlines(), strict=True)):
            if n not in positions:
                continue
            f = line.split()
            rows.append(dict(instruction="f2xm1", rc=rc, pc=64, input=inp,
                             expected=" ".join(f[:3]), C1=(int(f[4],16)>>9)&1, C2=0,
                             source=key, line=n+1, raw=line))

    for instruction, job, width in (("fptan", "fptan-re/t0002", 5), ("fpatan", "fpatan-re/d0066", 7)):
        hp = PROJECT / "tmp" / job / "hardware.txt.gz"
        key = source(hp)
        complete = json.loads((hp.parent / "COMPLETE.json").read_text())
        assert sources[key] == complete["hardware_gzip_sha256"]
        seen = Counter()
        with gzip.open(hp, "rt") as stream:
            for n, line in enumerate(stream):
                f = line.split()
                rc, pc = f[1], int(f[2])
                sw = int(f[7 if instruction=="fptan" else 9],16)
                c2 = (sw>>10)&1 if instruction=="fptan" else 0
                group = (rc,pc,c2)
                position = seen[group]
                seen[group] += 1
                if position not in (0,1,17,97) and position % 4096:
                    continue
                if instruction=="fptan":
                    inp = " ".join(f[3:5])
                    expected = "C2" if c2 else "OK " + " ".join(f[9:13])
                else:
                    inp = " ".join(f[:width])
                    expected = " ".join([f[0], *f[10:12], str((sw>>9)&1),
                                         f"{sw&63:02x}", f"{int(f[8],16)&63:02x}"])
                rows.append(dict(instruction=instruction,rc=rc,pc=pc,input=inp,expected=expected,
                                 C1=(sw>>9)&1,C2=c2,source=key,line=n+1,raw=line.strip()))

    hp = PROJECT / "transfer-tests/h1722/run-skylake/outputs.txt"
    key = source(hp)
    receipt = json.loads((HERE / "evidence/trig-h1722-summary.json").read_text())
    assert sources[key] == receipt["hosts"]["skylake"]["artifact_sha256"]["raw"]
    seen = Counter()
    with hp.open() as stream:
        for n, line in enumerate(stream):
            f = dict(pair.split("=",1) for pair in line.split())
            insn,rc,pc = f["INSN"],f["MODE"],int(f["PC"][2:])
            group = (insn,rc,pc)
            position=seen[group];seen[group]+=1
            if position not in (0,1,19,97,997,2048,4095,6179):
                continue
            sw=int(f["A_SW"],16);c2=(sw>>10)&1
            lanes = [f["SIN"]] if insn=="fsin" else [f["COS"]] if insn=="fcos" else [f["SIN"],f["COS"]]
            expected="C2" if c2 else "OK " + " ".join(v.replace(":"," ") for v in lanes)
            rows.append(dict(instruction=insn,rc=rc,pc=pc,input=f["IN"].replace(":"," "),
                             expected=expected,C1=(sw>>9)&1,C2=c2,source=key,line=n+1,raw=line.strip()))
    counts=Counter(r["instruction"] for r in rows)
    write_json(HERE / "evidence/smoke-witnesses.json",dict(format="x87-offline-witnesses-v1",
        selection="Fixed row positions per declared instruction/control group; no prediction-based selection",
        sources=sources, counts=counts, rows=rows))
    print(dict(counts), "total",len(rows))


if __name__=="__main__":
    main()

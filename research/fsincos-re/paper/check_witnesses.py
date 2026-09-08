"""Check portable C models and exact references against bundled hardware examples.

This is a small offline regression, not a new hardware capture. Unary CLI
checks cover values/C2; sibling references additionally check C1. FPATAN
checks include result, C1, exception and preload fields. PC is metadata for
the unary CLI, which has no per-row PC option. No native x87 is executed.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path
import subprocess
import sys
from suite_support import HERE, PROJECT, sibling_constants, write_json
from verify_fpatan_catalog import load_reference
sys.path.insert(0,str(PROJECT / "docs"))
import sibling_reference


def main():
    data=json.loads((HERE / "evidence/smoke-witnesses.json").read_text())
    groups=defaultdict(list)
    for row in data["rows"]:
        groups[row["instruction"],row["rc"]].append(row)
    counts=Counter()
    constants=sibling_constants()
    atan=load_reference()
    flags={"fsin":["--fsin-standalone"],"fcos":["--fcos-standalone"],
           "fsincos":[],"f2xm1":["--f2xm1"],"fptan":["--fptan"]}
    for (insn,rc),rows in sorted(groups.items()):
        command = ([str(PROJECT / "fpatan-re/build/fpatan")] if insn=="fpatan" else
                   [str(PROJECT / "src/fsincos_skylake"),"--batch",*flags[insn],f"--rc={rc}"])
        result=subprocess.run(command,input="\n".join(r["input"] for r in rows)+"\n",
                              text=True,capture_output=True,check=True)
        lines=result.stdout.splitlines()
        assert len(lines)==len(rows),(insn,rc,"wrong output row count",len(lines),len(rows))
        for row,line in zip(rows,lines):
            assert line.lower()==row["expected"].lower(),(insn,rc,row["input"],line,row["expected"])
            if insn in ("f2xm1","fptan"):
                se,sig=(int(v,16) for v in row["input"].split())
                raw,pushed,c1,c2=sibling_reference.evaluate(insn.upper(),se,sig,rc,constants)
                out="C2" if c2 else "OK " + " ".join(f"{a:04x} {b:016x}" for a,b in [raw]+([] if pushed is None else [pushed]))
                assert out.lower()==row["expected"].lower() and (c1,c2)==(row["C1"],row["C2"])
                counts["sibling_reference_checks"]+=1
            elif insn=="fpatan":
                f=row["input"].split()
                ys,ym,xs,xm=(int(v,16) for v in f[3:])
                (se,sig),c1,exc,pre=atan["fpatan"](atan["Raw80"](ys,ym),atan["Raw80"](xs,xm),rc.upper(),row["pc"])
                out=f"{f[0]} {se:04x} {sig:016x} {c1} {exc:02x} {pre:02x}"
                assert out.lower()==row["expected"].lower()
                counts["fpatan_reference_checks"]+=1
            counts[f"C:{insn}"]+=1
    report=dict(status="PASS",hardware_executed=False,counts=counts,rows=len(data["rows"]),
                scope="Bundled saved hardware witnesses; unary CLI does not expose C1 or per-row PC")
    print(json.dumps(report,indent=2))
    if len(sys.argv)==3 and sys.argv[1]=="--out":
        write_json(Path(sys.argv[2]),report)


if __name__=="__main__":
    main()

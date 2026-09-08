#!/usr/bin/env python3
"""Independent paired-graph square contrast; software predictions only.

Transporting a standalone square witness to paired FSINCOS is an explicit
instruction-independent square-semantics hypothesis, NOT a proven transfer.
The comparison tests whether it is observable before any capture is considered.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import re
import subprocess
from collections import Counter
from pathlib import Path
import h1592_independent_integer_spec as spec


V = spec.Value
SINE = {
    1: V(-0x55555555555555555,-69),
    2: V(0x44444444444443E35,-73),
    3: V(-0x6806806806773C774,-79),
    4: V(0x5C778E94F50956D70,-85),
    5: V(-0x6B991122EFA0532F0,-92),
    6: V(0x58303F02614D5E4D8,-99),
}
SOURCE_SHA = "0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b"
GRAPH_SHA = "d1c4a18f462a24b2282a2e15eb6e0ac374e34f124b0bf3cd0a24663d98669f2f"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paired(operand: str, mode: str, square_policy: str) -> dict[str,V]:
    x = spec.decode_external(operand)
    assert x.n > 0 and x.e+x.n.bit_length()-1 == -3
    square = spec.mul(x,x,67,square_policy)
    p = SINE[6]
    for i in (5,4,3,2,1):
        p = spec.quantize(spec.exact_add(spec.exact_mul(p,square),SINE[i]),64,"rn")
    q = spec.COEFFICIENTS[6]
    for i in (5,4,3,2):
        q = spec.quantize(spec.exact_add(spec.exact_mul(q,square),spec.COEFFICIENTS[i]),64,"rn")
    qmul = spec.mul(q,square,67)
    q = spec.add(qmul,spec.COEFFICIENTS[1],64,"rn")
    sin_product = spec.mul(p,square,64,"rn")
    sin_correction = spec.mul(sin_product,x,67)
    cos_correction = spec.mul(q,square,67)
    return {"square":square,"p":p,"q":q,"sin_correction":sin_correction,
            "cos_correction":cos_correction,
            "sin":spec.add(x,sin_correction,64,mode),
            "cos":spec.add(V(1,0),cos_correction,64,mode)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    a = p.parse_args()
    if a.output_dir.exists():
        raise SystemExit("refusing existing output directory")
    cur = a.root/"tmp/ledger33/current"
    before = cur/"h1601_source_before.c"
    after = cur/"h1601_source_square_away.c"
    assert digest(before) == SOURCE_SHA
    needle = "            wv_t asq67 = wv_mul_round_bits(\n                mag.sig, mag.e2, 0, mag.sig, mag.e2, 0, 67, 0);"
    addition = "\n            /* H1601 analysis only: transport the alternate faithful square\n             * through the paired graph. This is not a proposed global rule. */\n            asq67 = p5_wv_mul_round(mag, mag, 67, P5_ROUND_AWAY);"
    assert before.read_text().count(needle)==1
    assert after.read_text() == before.read_text().replace(needle,needle+addition)
    header = a.root/"src/p5_rom_constants.h"
    coefficients = re.findall(r"P5S6_([1-6]) = \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull",header.read_text())
    assert len(coefficients)==6
    for i,sign,e,hi,lo in coefficients:
        value = (int(hi,16)<<64)|int(lo,16)
        assert V(-value if sign=="1" else value,int(e)) == SINE[int(i)]
    graph_path = cur/"h1595_coupled_faithful_reachability_v2/report.json"
    assert digest(graph_path)==GRAPH_SHA
    graph = json.loads(graph_path.read_text())
    assert digest(Path(spec.__file__)) == graph["sha256"]["evidence"]["experiments/h1592_independent_integer_spec.py"]
    observed = {(r["operand"],r["mode"]):r for r in graph["rows"]}
    named = sorted({r["operand"] for r in graph["rows"]})
    assert len(named)==36 and len(observed)==37
    rng = random.Random(0x1601)
    random_ops = sorted({f"3ffc {rng.randrange(1<<63,1<<64):016x}" for _ in range(2048)})
    assert len(random_ops)==2048 and not set(random_ops)&set(named)
    operands = sorted(named+random_ops)
    a.output_dir.mkdir(parents=True)
    model_reports = {}
    output_values = {}
    for name,source in (("paired_current",before),("paired_square_away",after)):
        model = (a.output_dir/name).resolve()
        subprocess.run(["cc","-O2","-std=c11","-DG_ROUND84=0","-I",str((a.root/"src").resolve()),
                        str(source.resolve()),"-lm","-o",str(model)],check=True,capture_output=True)
        traces = {}
        for mode in spec.MODES:
            proc = subprocess.run([str(model),"--batch",f"--rc={mode}"],input="".join(op+"\n" for op in operands),
                                  text=True,capture_output=True,check=True)
            lines = proc.stdout.splitlines()
            assert len(lines)==len(operands) and not proc.stderr
            path = a.output_dir/f"{name}_{mode}.stdout"
            with path.open("x") as out:
                out.write(proc.stdout)
            traces[path.name] = digest(path)
            for op,line in zip(operands,lines):
                words = line.split()
                assert len(words)==5 and words[0]=="OK"
                actual = {"sin":":".join(words[1:3]),"cos":":".join(words[3:5])}
                stages = paired(op,mode,"chop" if name=="paired_current" else "away")
                expected = {lane:spec.encode_external(stages[lane]) for lane in ("sin","cos")}
                assert actual==expected,(name,op,mode,actual,expected)
                output_values[name,op,mode] = actual
        model_reports[name] = {"binary_sha256":digest(model),"raw":traces,"software_mode_rows":len(operands)*4,
                               "independent_outputs_exact":True}
    rows = []
    changes = Counter()
    for op in operands:
        for mode in spec.MODES:
            base = output_values["paired_current",op,mode]
            alternative = output_values["paired_square_away",op,mode]
            changed = [lane for lane in base if base[lane]!=alternative[lane]]
            origin = "named_standalone" if op in named else "random_software_only"
            for lane in changed:
                changes[origin+"."+lane]+=1
            if op in named or changed:
                record = {"operand":op,"mode":mode,"origin":origin,"paired_hardware_label":None,
                          "paired_baseline":base,"paired_alternate_square":alternative,"changed_lanes":changed}
                if op in named:
                    record["independent_stages"]={policy:{k:v.record() for k,v in paired(op,mode,policy).items()}
                                                  for policy in ("chop","away")}
                    old = observed.get((op,mode))
                    record["standalone_mode_observed"] = old is not None
                    if old:
                        record["standalone_hardware"] = old["hardware"]
                        record["standalone_square_only_witness"] = {
                            variant:1 in detail["families"]["all_graph"]["successful_masks"]
                            for variant,detail in old["variants"].items()}
                rows.append(record)
    result = {"experiment":"h1601_paired_square_discriminator","hardware_execution":"none",
              "paired_hardware_labels_opened":0,"manifest_frozen":False,"selector_promotion":"none",
              "hypothesis":"instruction_independent_alternate_square_transports_to_paired_graph_vs_standalone_terminal_change_does_not",
              "claim_boundary":"paired_graph_and_cross_instruction_square_transfer_are_assumptions; software_contrast_is_not_silicon_evidence",
              "named_operands":len(named),"random_software_operands":len(random_ops),"changed_lane_counts":dict(changes),
              "models":model_reports,"rows":rows,
              "sha256":{"script":digest(Path(__file__)),"spec":digest(Path(spec.__file__)),"constants":digest(header),
                         "source_before":digest(before),"source_after":digest(after),"h1595":digest(graph_path)}}
    with (a.output_dir/"report.json").open("x") as out:
        json.dump(result,out,indent=2,sort_keys=True)
        out.write("\n")
    print(json.dumps(result["changed_lane_counts"],sort_keys=True))


if __name__=="__main__":
    main()

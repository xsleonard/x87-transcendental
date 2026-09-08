"""Build the unified article from canonical code and verified evidence.

Generated listings/numbers are never an independent authoring source.
This command does not capture hardware or change numerical implementations.
"""
import argparse
import ast
import csv
import json
from pathlib import Path
import re
import subprocess
from suite_support import (HERE, PROJECT, digest, write_json,
                           before_f2xm1_correction_digest, reference_ast_digest,
                           pseudocode_program_digest)

GEN = HERE / "generated-suite"
OUTPUT = PROJECT.parent / "output/pdf"


def number(n):
    return f"{n:,}".replace(",", "{,}")


def listings(code, stem):
    """Preserve all lines while keeping complete functions together."""
    (GEN / f"{stem}.py").write_text(code)
    tree = ast.parse(code)
    starts = [min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])]) for n in tree.body]
    chunks, first = [], 1
    for i, start in enumerate(starts):
        end = starts[i+1]-1 if i+1 < len(starts) else len(code.splitlines())
        if end-first+1 > 26 and start > first:
            chunks.append((first,start-1));first=start
    chunks.append((first,len(code.splitlines())))
    return "".join(
        "\\par\\noindent\\begin{minipage}{\\linewidth}\n"
        f"\\lstinputlisting[style=reference,firstline={a},lastline={b}]{{generated-suite/{stem}.py}}\n"
        "\\end{minipage}\\par\n" for a,b in chunks)


def sibling_family_listings(code):
    """Group canonical source by family; omit storage-history prose in print."""
    nodes = ast.parse(code).body
    lines = code.splitlines()
    history_note = "# The description below records the historical conversion behavior."
    assert lines.count(history_note) == 1
    note_start = lines.index(history_note) + 1
    assert lines[note_start].startswith("# F2XM1 now rounds directly")
    store_node = next(n for n in nodes if getattr(n, "name", None) == "store")
    doc = store_node.body[0]
    assert isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant)
    omitted = {note_start, note_start + 1, *range(doc.lineno, doc.end_lineno + 1)}
    starts = [min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])])
              for n in nodes]
    starts[0] = 1
    groups = {"tangent": [], "exponential": [], "sibling-common": []}
    tangent = {"reduce_angle", "horner", "fptan_polynomial", "fptan_table", "fptan_ratio"}
    exponential = {"f2xm1_long", "f2xm1_table"}
    for i, node in enumerate(nodes):
        name = getattr(node, "name", None)
        group = "tangent" if name in tangent else "exponential" if name in exponential else "sibling-common"
        end = starts[i+1] - 1 if i+1 < len(starts) else len(code.splitlines())
        groups[group].append((starts[i], end))
    covered = [line for ranges in groups.values() for a,b in ranges for line in range(a,b+1)]
    assert sorted(covered) == list(range(1, len(code.splitlines())+1))
    for group, ranges in groups.items():
        chunks = []
        for a,b in ranges:
            if chunks and a == chunks[-1][1]+1 and b-chunks[-1][0]+1 <= 26:
                chunks[-1] = (chunks[-1][0], b)
            else:
                chunks.append((a,b))
        display = []
        for a,b in chunks:
            intervals, start = [], None
            for line in range(a,b+2):
                if line <= b and line not in omitted:
                    if start is None: start = line
                elif start is not None:
                    intervals.append((start,line-1)); start = None
            line_ranges = ",".join(f"{x}-{y}" for x,y in intervals)
            display.append(
                "\\par\\noindent\\begin{minipage}{\\linewidth}\n"
                f"\\lstinputlisting[style=reference,linerange={{{line_ranges}}}]{{generated-suite/siblings.py}}\n"
                "\\end{minipage}\\par\n")
        (GEN / f"{group}-listings.tex").write_text("".join(display))


def prepare():
    GEN.mkdir(exist_ok=True)
    ev = HERE / "evidence"
    f2 = json.loads((ev / "f2xm1-current-replay.json").read_text())
    integrated = json.loads((ev / "f2xm1-integration.json").read_text())
    assert integrated['status'] == 'PASS_INTEGRATED_F2XM1_CORRECTION'
    assert integrated['verifier_sha256'] == digest(HERE / 'verify_f2xm1_integration.py')
    assert integrated['current_c_sha256'] == digest(PROJECT / 'src/fsincos_skylake.c')
    assert integrated['current_reference_sha256'] == digest(PROJECT / 'docs/sibling_reference.py')
    previous_c = before_f2xm1_correction_digest(PROJECT / 'src/fsincos_skylake.c')
    assert previous_c == integrated['previous_c_sha256']
    assert reference_ast_digest(PROJECT / 'docs/sibling_reference.py', True) == integrated['previous_reference_ast_sha256']
    followup = json.loads((ev / 'verification-followup.json').read_text())
    assert followup['status'] == 'PASS_SAVED_TWO_PROCESSOR_CONFIRMATIONS'
    assert followup['logarithm_i7_cases'] == 51636
    assert followup['fpatan_common_catalog_cases'] == 7571628
    tan = json.loads((ev / "fptan-pseudocode-replay.json").read_text())
    atan = json.loads((ev / "fpatan-pseudocode-current.json").read_text())
    trig = json.loads((ev / "trig-h1722-summary.json").read_text())
    trig_replay = json.loads((ev / "trig-h1719-summary.json").read_text())
    trig_native = json.loads((ev / "trig-native-fsin-summary.json").read_text())
    assert trig_replay['status'] == 'PASS_SAVED_LABEL_REPLAYS_BOTH_HOSTS'
    assert trig_native['status'] == 'COMPLETED_NATIVE_RUN_LOGS_ZERO_REPORTED_MISSES'
    for receipt in (trig_replay, trig_native):
        assert receipt['summary_builder_sha256'] == digest(HERE / 'audit_trig_history.py')
    for name, sha in trig_replay['source_files'].items():
        assert sha == (previous_c if name == 'src/fsincos_skylake.c' else digest(PROJECT / name))
    assert trig_native['review_main_source_sha256'] == previous_c
    assert trig_native['instruction_executions'] == sum(r['counts']['observations'] for r in trig_native['runs'])
    logs = json.loads((ev / "logarithm-replay.json").read_text())
    assert logs['status']=='AUTHENTICATED_LOGARITHM_REPLAY'
    assert logs['source_sha256']==digest(PROJECT/'fyl2x-re/log_model.c')
    assert logs['python_sha256']==digest(PROJECT/'fyl2x-re/model.py')
    assert f2["status"] == tan["status"] == atan["status"] == "PASS"
    assert f2['specification_sha256'] == integrated['current_reference_sha256']
    assert tan['specification_sha256'] == integrated['previous_reference_sha256']
    for receipt in (f2,tan):
        assert receipt["constants_sha256"] == digest(PROJECT / "docs/sibling-constants.json")
    assert atan["pseudocode_program_sha256"] == pseudocode_program_digest(PROJECT / "fpatan-re/PSEUDOCODE.md")
    ft = f2["result"]["counts"]
    tt = tan["result"]["jobs"]["t0002"]["counts"]
    at = atan["counts"]
    for counts in [ft,tt,at,logs['totals'],*[h["counts"] for h in trig["hosts"].values()],
                   *[h['total_counts'] for h in trig_replay['hosts'].values()],
                   *[r['counts'] for r in trig_native['runs']]]:
        assert all(v==0 for k,v in counts.items() if k.endswith("misses"))
    values = dict(FtwoRows=ft["rows"], TanRows=tt["rows"], TanSuccess=tt["successful"],
                  TanRange=tt["range_returns"], TanPerMode=tt["RC:rn"], TanSmallPC=tt["PC:24"],
                  AtanRows=at["rows"], AtanPacks=len(atan["jobs"]), AtanPerMode=at["rc:rn"])
    values.update(FtwoRawRows=integrated['cases_per_processor'],
                  FtwoOriginalResultMisses=integrated['original_result_misses_per_processor'],
                  FtwoOriginalCOneMisses=integrated['original_C1_misses_per_processor'])
    values.update(LogRows=logs['totals']['rows'],LogPacks=len(logs['jobs']),
        LogXRows=logs['totals']['fyl2x'],LogPoneRows=logs['totals']['fyl2xp1'],
        LogFreshRows=sum(j['counts']['rows'] for j in logs['jobs'] if j['current_c_identical_to_frozen']))
    values.update(TrigNativeRows=trig_native['instruction_executions'],
                  TrigNativeInputs=trig_native['inputs'],
                  TrigIsevenRows=trig_replay['hosts']['i7']['total_counts']['rows'],
                  TrigXeonRows=trig_replay['hosts']['skylake']['total_counts']['rows'],
                  TrigChallengeRows=trig['hosts']['skylake']['counts']['instruction_rows'])
    (GEN / "numbers.tex").write_text("% Generated from verified receipts.\n" + "".join(
        f"\\newcommand{{\\{k}}}{{{number(v)}}}\n" for k,v in values.items()))
    rows=[("FSIN native run (logs)",values['TrigNativeRows'],"RN/RD/RU; result, C1/C2"),
          ("Trig replay, i7 host",values['TrigIsevenRows'],"Available results and C1/C2"),
          ("Trig replay, Xeon host",values['TrigXeonRows'],"Available results and C1/C2"),
          ("Trig challenge, each CPU",values['TrigChallengeRows'],"Three instructions; four RC, three PC"),
          ("F2XM1 reference replay",ft["rows"],"RN/RD/RU; result, C1"),
          ("F2XM1 raw80, each CPU",values['FtwoRawRows'],"Four RC; result, C1; raw80 extremes"),
          ("FPTAN, each CPU",tt["rows"],"Four RC; result, push, C1/C2"),
          ("FPATAN reference replay",at["rows"],"Four RC; result, C1, exception fields"),
          ("Logarithm reference replay",logs['totals']['rows'],"Two instructions; result, C1, exceptions")]
    table="\\begin{table}[ht]\n\\centering\\small\n\\begin{tabular}{@{}lrl@{}}\n\\toprule\nEvidence & Instruction rows & Checks\\\\\n\\midrule\n"
    table += "".join(f"{name} & {number(n)} & {scope}\\\\\n" for name,n,scope in rows)
    table += "\\bottomrule\n\\end{tabular}\n\\caption{Completed tests, with no reported mismatches in the fields checked. Native runs count instructions executed; replays count saved rows checked in software. The text explains which flags were checked and what the native logs record. Tests can share inputs, so these counts should not be added together.}\n\\label{tab:evidence}\n\\end{table}\n"
    (GEN / "evidence-table.tex").write_text(table)
    trig_table = "\\begin{table}[ht]\n\\centering\\small\n\\begin{tabular}{@{}lrl@{}}\n\\toprule\nEvidence & Instruction rows & Checks\\\\\n\\midrule\n"
    trig_table += "".join(f"{name} & {number(n)} & {scope}\\\\\n" for name,n,scope in rows[:4])
    trig_table += "\\bottomrule\n\\end{tabular}\n\\caption{Completed sine and cosine tests, with no reported mismatches in the checked fields. Native executions and saved-row replays are separate evidence units. Test sets overlap; the counts should not be added together.}\\label{tab:trig-evidence}\n\\end{table}\n"
    (GEN / "trig-evidence-table.tex").write_text(trig_table)
    for stem, indices, caption in (
        ("tangent", (6,7), "Completed tangent and arctangent checks. Counts describe saved input/control rows in the indicated captures or catalogs; they are not added together."),
        ("explog", (4,5,8), "Completed exponential and logarithm checks. Earlier replays and later challenges have different scopes and can share inputs."),
    ):
        family_table = "\\begin{table}[ht]\n\\centering\\small\n\\begin{tabular}{@{}lrl@{}}\n\\toprule\nEvidence & Instruction rows & Checks\\\\\n\\midrule\n"
        family_table += "".join(f"{rows[i][0]} & {number(rows[i][1])} & {rows[i][2]}\\\\\n" for i in indices)
        family_table += f"\\bottomrule\n\\end{{tabular}}\n\\caption{{{caption}}}\\label{{tab:{stem}-evidence}}\n\\end{{table}}\n"
        (GEN / f"{stem}-evidence-table.tex").write_text(family_table)
    trig_md=(PROJECT / "docs/TRIG-PSEUDOCODE.md").read_text()
    blocks=re.findall(r"^```text\n(.*?)^```",trig_md,re.M|re.S)
    assert len(blocks)==4
    (GEN / "trig-listings.tex").write_text("".join(listings(b,f"trig-{i}") for i,b in enumerate(blocks,1)))
    (GEN / "sibling-listings.tex").write_text(listings((PROJECT / "docs/sibling_reference.py").read_text(),"siblings"))
    sibling_family_listings((PROJECT / "docs/sibling_reference.py").read_text())
    blocks=re.findall(r"^```python\n(.*?)^```",(PROJECT / "fpatan-re/PSEUDOCODE.md").read_text(),re.M|re.S)
    assert len(blocks)==5
    (GEN / "atan-listings.tex").write_text("".join(listings(b,f"atan-{i}") for i,b in enumerate(blocks,1)))
    (GEN / "log-listings.tex").write_text(listings((PROJECT/'fyl2x-re/model.py').read_text(),'logarithms'))
    constants=json.loads((PROJECT / "docs/sibling-constants.json").read_text())["constants"]
    literals=[]
    for group,value in constants.items():
        if group=="F2_LN2":items=[(group,value)]
        elif group=="TABLE":items=[(f"{kind}[{b}]",r) for b,pair in value.items() for kind,r in zip(("sin","cos"),pair)]
        else:items=[(f"{group}[{i}]",r) for i,r in enumerate(value)]
        for name,r in items:literals.append((name,r["rom_row"],r["sign"],r["scale"],r["significand"]))
    with (PROJECT / "data/pentium-rom/rom-constants.tsv").open() as f:
        for r in csv.DictReader(f,delimiter="\t"):
            i=int(r["row"])
            if i in (19,20) or 114<=i<=123 or 125<=i<=156:
                literals.append((f"atan ROM[{i}]",i,int(r["sign"]),int(r["exp"],16)-0xffff-66,r["sig68"]))
    log_literals=re.findall(r'\{(\d+), (\d+), (-?\d+), "([0-9a-f]+)"\}',(PROJECT/'fyl2x-re/log_model.c').read_text())
    assert len(log_literals)==77
    for i,s,q,sig in log_literals:literals.append((f'log ROM[{i}]',int(i),int(s),int(q),sig))
    text="{\\footnotesize\n\\begin{longtable}{@{}lrrrl@{}}\n\\toprule\nName & Row & $s$ & $q$ & $S$ (hex)\\\\\n\\midrule\n\\endfirsthead\n\\toprule\nName & Row & $s$ & $q$ & $S$ (hex)\\\\\n\\midrule\n\\endhead\n"
    for name,row,s,q,sig in literals:
        safe=name.replace("_",r"\_")
        text+=f"\\texttt{{{safe}}} & {row} & {s} & {q} & \\texttt{{{sig}}}\\\\\n"
    text+="\\bottomrule\n\\end{longtable}\n}\n"
    (GEN / "literals.tex").write_text(text)
    literal_header = text[:text.index("\\texttt")]
    literal_footer = "\\bottomrule\n\\end{longtable}\n}\n"
    family_literals = {"trig": [], "atan": [], "explog": []}
    for item in literals:
        name = item[0]
        family = "atan" if name.startswith("atan ROM") else "explog" if name.startswith(("F2", "log ROM")) else "trig"
        family_literals[family].append(item)
    assert sum(map(len, family_literals.values())) == len(literals)
    for family, items in family_literals.items():
        body = ""
        for name,row,s,q,sig in items:
            safe = name.replace("_", r"\_")
            body += f"\\texttt{{{safe}}} & {row} & {s} & {q} & \\texttt{{{sig}}}\\\\\n"
        (GEN / f"{family}-literals.tex").write_text(literal_header + body + literal_footer)
    return values,len(literals)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render",action="store_true")
    args=parser.parse_args()
    values,literal_count=prepare()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    subprocess.run(["tectonic","--keep-logs","--outdir",str(OUTPUT),"x87-suite.tex"],cwd=HERE,check=True)
    log=(OUTPUT / "x87-suite.log").read_text()
    problems=[line for line in log.splitlines() if any(s in line for s in ("Overfull", "undefined", "LaTeX Warning"))]
    if problems:raise SystemExit("TeX issues:\n"+"\n".join(problems))
    files=[HERE / "x87-suite.tex",HERE / "suite-references.bib",Path(__file__),
           HERE / "TRIG-FINDINGS.md",
           HERE / "suite_support.py",HERE / "verify_siblings.py",HERE / "audit_trig_history.py",
           HERE / "verify_f2xm1_integration.py",
           HERE / "verify_fpatan_catalog.py",HERE / "check_witnesses.py",
           PROJECT / "src/fsincos_skylake.c",PROJECT / "src/ia64_sf.h",
           PROJECT / "src/p5_rom_constants.h",PROJECT / "src/f2xm1_constants.h",
           PROJECT / "src/general/paired.h",PROJECT / "src/general/standalone_polynomial.h",
           PROJECT / "src/general/standalone_table.h",PROJECT / "src/general/standalone_tiny.h",
           PROJECT / "fpatan-re/fpatan_candidate.c",PROJECT / "fpatan-re/fpatan_library.c",
           PROJECT / "fpatan-re/fpatan_library.h",PROJECT / "data/pentium-rom/rom-constants.tsv",
           *[PROJECT/'fyl2x-re'/name for name in ('log_model.c','log_library.c','log_library.h','model.py','ALGORITHM.md','ACCEPTANCE.md','witnesses.json','witnesses.txt')],
           PROJECT / "docs/TRIG-PSEUDOCODE.md",PROJECT / "docs/sibling_reference.py",
           PROJECT / "docs/sibling-constants.json",PROJECT / "fpatan-re/PSEUDOCODE.md",
           PROJECT / "src/test_f2xm1.py",PROJECT / "src/test_f2xm1_driver.c",
           PROJECT / "src/f2xm1_regressions.json",
           *sorted((HERE / "evidence").glob("*.json")),
           *sorted(p for p in GEN.iterdir() if p.name != "suite-manifest.json")]
    write_json(GEN / "suite-manifest.json",dict(format="x87-suite-publication-v1",
        figures=values,literal_rows=literal_count,
        source_files={str(p.relative_to(PROJECT.parent)):digest(p) for p in files},
        pdf_sha256=digest(OUTPUT / "x87-suite.pdf"),licensing="Undecided for original work; per author instruction",
        status="BUILT_AWAITING_VISUAL_REVIEW"))
    if args.render:
        render=PROJECT / "tmp/pdfs/x87-suite"
        render.mkdir(parents=True,exist_ok=True)
        subprocess.run(["pdftoppm","-scale-to","1400","-png",str(OUTPUT / "x87-suite.pdf"),str(render / "page")],check=True)
    print("Built",OUTPUT / "x87-suite.pdf","with",literal_count,"literal rows",flush=True)


if __name__ == "__main__":
    main()

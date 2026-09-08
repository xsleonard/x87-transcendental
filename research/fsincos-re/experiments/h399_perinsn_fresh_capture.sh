#!/bin/bash
# Preserved verbatim from the 2026-08-07 Round-54 pass; ran in
# /home/coduoserver/fsincos-residual-20260807-1 on the Skylake capture host.
# See notes/skylake-comparison.md (Round 54) and notes/residual-ideas.md.
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
mkdir -p fresh
CAPBIN=src/x87_capture
for mode in rn rd ru; do
  for corpus in sweep dense; do
    IN=capture-kit/inputs/sweep_inputs.txt
    [ $corpus = dense ] && IN=capture-kit/inputs/dense_qn.txt
    $CAPBIN $mode sincos --status < $IN > fresh/${corpus}_fsincos_$mode.txt
    $CAPBIN $mode sin --status < $IN > fresh/${corpus}_fsin_$mode.txt
    $CAPBIN $mode cos --status < $IN > fresh/${corpus}_fcos_$mode.txt
  done
done
wc -l fresh/* | tail -1
python3 - <<'PYEOF'
# Hardware paired vs hardware standalone, fresh silicon, all modes/corpora.
def rows(p):
    return [l.split() for l in open(p)]
for corpus in ("sweep","dense"):
    for mode in ("rn","rd","ru"):
        hp = rows(f"fresh/{corpus}_fsincos_{mode}.txt")
        hs = rows(f"fresh/{corpus}_fsin_{mode}.txt")
        hc = rows(f"fresh/{corpus}_fcos_{mode}.txt")
        n = len(hp); assert len(hs)==n and len(hc)==n
        sin_d = cos_d = c2_d = sw_d = 0
        for i in range(n):
            if hp[i][0] != hs[i][0] or hp[i][0] != hc[i][0]:
                c2_d += 1; continue
            if hp[i][0] != "OK": continue
            if hp[i][1:3] != hs[i][1:3]: sin_d += 1
            if hp[i][3:5] != hc[i][1:3]: cos_d += 1
            swp = int(hp[i][6],16) & ~0x3800
            swc = int(hc[i][3],16) & ~0x3800
            if swp != swc: sw_d += 1
        print(corpus, mode, "n",n, "sin_diff",sin_d, "cos_diff",cos_d,
              "status_class_diff",c2_d, "sw_vs_fcos_diff",sw_d)
PYEOF

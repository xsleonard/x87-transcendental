#!/bin/bash
# h628b: extract the flag-ON mismatch inputs and trace them.
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
COMMON="--round18-poly --round21-table-bias --round23-narrow-coefficient \
 --round24-table-delta-rn67 --round29-p5-fmul-route \
 --round30-fsin-cosine-square --round31-fsin-cosine-tail \
 --round32-fsin-cosine-horner --round33-fsin-cosine-product \
 --round34-table-lookup-firc --round35-table-p-terminal \
 --round36-table-fadd-microcontrol --round37-p6-four-term \
 --round41-fsin-cosine-split --round42-p6-sine-split \
 --round43-p6-sine-bias --round44-p6-sine-bias \
 --round45-p6-sine-fraction --round46-p6-narrow-sine-fraction \
 --round47-p6-narrow-sine-fraction --round48-p6-narrow-sine-fraction \
 --round49-p6-carrier-interval --round50-fsin-operation-classes \
 --round51-fsin-fadd-signature"
FCOS="--fcos-standalone $COMMON --round38-p6-cosine-split --round39-fcos-tiny \
 --round52-fcos-low3-carrier --round53-fcos-operation-classes \
 --round57-fcos-borrow-rule"
> h628_survivors.txt
for s in h363 h372 h380 h384 h422; do
  if [ $s = h422 ]; then
    IN=h422/selected_inputs.txt; HD=h422; HP=hw
  else
    IN=shuffle/${s}_orig.txt; HD=captures/skylake-fcos-$s; HP=fcos
  fi
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    src/fsincos_skylake --batch $RC $FCOS < $IN > h410/t.txt
    HF=$HD/${HP}_${mode}_status.txt
    python3 - "$IN" "$HF" "$s" "$mode" <<'PYEOF' >> h628_survivors.txt
import sys
inf, hf, s, mode = sys.argv[1:5]
ins = open(inf).read().splitlines()
def norm(p):
    out=[]
    for l in open(p):
        t=l.split()
        out.append(tuple(t[1:3]) if t[0]=="OK" else ("C2",))
    return out
hw = norm(hf)
mo = norm("h410/t.txt")
for i,(a,b) in enumerate(zip(hw,mo)):
    if a!=b:
        print(f"{s} {mode} {i} {ins[i]} hw={a} model={b}")
PYEOF
  done
done
sort -u -k4,5 h628_survivors.txt | awk '{print $4, $5}' | sort -u > h628_uinputs.txt
echo "distinct inputs: $(wc -l < h628_uinputs.txt)"
cat h628_survivors.txt
src/fsincos_skylake --batch $FCOS --debug-cosine-carrier --debug-r57 \
    < h628_uinputs.txt > h628_out.txt 2> h628_tr.txt
echo "=== traces:"
cat h628_tr.txt
echo H628B_DONE

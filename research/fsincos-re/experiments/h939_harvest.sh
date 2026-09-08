#!/bin/bash
# h939: fresh-random harvest of visible-fire & B_e=0 rows, cos rn.
set -e
cd /root/r84
: > h939/candidates.tsv
for i in 0 1 2 3 4 5 6 7 8 9; do
  sed -e "s/random.seed(0x662662)/random.seed(0x9390 + $i)/" \
      -e "s/N = 8_000_000/N = 10_000_000/" \
      -e "s/randv1_inputs.txt/h939\/chunk.txt/" /root/r59/h727_gen.py \
      > h939/gen.py
  nice -n 10 python3 h939/gen.py > h939/gen.log 2>&1
  nice -n 10 ./model_r92 --batch --fcos-standalone < h939/chunk.txt > h939/base.txt 2>/dev/null
  nice -n 10 ./model_h937_v2 --batch --fcos-standalone < h939/chunk.txt > h939/v2.txt 2>/dev/null
  python3 - <<PYEOF
def norm(l):
    t = l.split()
    return ("C2",) if t and t[0] == "C2" else tuple(t[1:3])
idx = []
with open("h939/base.txt") as fb, open("h939/v2.txt") as fv:
    for k, (b, v) in enumerate(zip(fb, fv)):
        if norm(b) != norm(v):
            idx.append(k)
inp = open("h939/chunk.txt").read().splitlines()
with open("h939/fire_inp.txt", "w") as f:
    f.write("\n".join(inp[k] for k in idx) + "\n")
with open("h939/fire_idx.txt", "w") as f:
    f.write("\n".join(map(str, idx)) + "\n")
print("chunk $i fires:", len(idx))
PYEOF
  python3 h938_frames.py ./model_r92 cos h939/fire_inp.txt h939/fire_frames.tsv 2>/dev/null
  python3 h939_classify.py h939/fire_frames.tsv h939/fire_idx.txt h939/candidates.tsv >> h939/progress.log
  echo "chunk $i done $(wc -l < h939/candidates.tsv) candidates" >> h939/progress.log
  rm -f h939/chunk.txt h939/base.txt h939/v2.txt
done
# label candidates against hardware
cut -f1,2 h939/candidates.tsv | tr "\t" " " > h939/cand_inp.txt
/root/x87_capture cos rn < h939/cand_inp.txt > h939/cand_hw.txt
./model_r92 --batch --fcos-standalone < h939/cand_inp.txt > h939/cand_base.txt 2>/dev/null
./model_h937_v2 --batch --fcos-standalone < h939/cand_inp.txt > h939/cand_v2.txt 2>/dev/null
python3 - <<PYEOF
def norm(l):
    t = l.split()
    return ("C2",) if t and t[0] == "C2" else tuple(t[1:3])
hw = open("h939/cand_hw.txt").read().splitlines()
ba = open("h939/cand_base.txt").read().splitlines()
v2 = open("h939/cand_v2.txt").read().splitlines()
cand = open("h939/candidates.tsv").read().splitlines()
res = {"hw==base": 0, "hw==v2(DEFICIT)": 0, "hw==OTHER": 0}
with open("h939/verdicts.tsv", "w") as out:
    for i, (h, b, v) in enumerate(zip(hw, ba, v2)):
        lab = "BASE" if norm(h) == norm(b) else (
              "DEFICIT" if norm(h) == norm(v) else "OTHER")
        res["hw==base" if lab == "BASE" else
            ("hw==v2(DEFICIT)" if lab == "DEFICIT" else "hw==OTHER")] += 1
        out.write(cand[i] + "\t" + lab + "\n")
print("H939 VERDICT:", res)
PYEOF
echo H939_DONE

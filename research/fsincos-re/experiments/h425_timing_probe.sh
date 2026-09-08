#!/bin/bash
# h425: latency side-channel on behavior-classified collision-family rows.
# Game servers keep running; min-of-N serialized rdtsc discards preemption.
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
mkdir -p h425
python3 - <<'PYEOF'
import collections
exec(open("h423_gate_learning.py").read().split("rows = []")[0])
def correction(d, payload):
    le2 = int(d["le2"]); re2 = int(d["re2"])
    ls = int(d["ls"], 16); rs = int(d["rs"], 16)
    lsign = int(d["lsign"]); rsign = int(d["rsign"])
    scale = min(le2, re2)
    if payload: scale = min(scale, le2 - 8)
    acc = (-1 if lsign else 1) * (ls << (le2 - scale)) \
        + (-1 if rsign else 1) * (rs << (re2 - scale))
    if payload:
        acc += (-1 if lsign else 1) * (payload << (le2 - 8 - scale))
    return chop67(acc, scale)
inputs = [l.strip() for l in open("h422/selected_inputs.txt")]
traces = open("h422/selected_traces.txt").read().splitlines()
hw = {m: [l.split() for l in open(f"h422/hw_{m}.txt")] for m in MODES}
classes = collections.defaultdict(list)
for i, tr in enumerate(traces):
    d = parse_trace(tr)
    hw_sigs = {m: int(hw[m][i][2], 16) for m in MODES}
    v = variants(d)
    ok = {n: all(final_cos(c, e, m) == hw_sigs[m] for m in MODES) for n, (c, e) in v.items()}
    if ok["add"] and not ok["or"] and not ok["xor"]: cls = "add"
    elif not ok["add"] and (ok["or"] or ok["xor"]): cls = "merge"
    elif not ok["add"]: cls = "lane"
    else: cls = "ctrl"
    classes[cls].append(inputs[i])
for cls, lst in classes.items():
    keep = lst if cls != "ctrl" else lst[:100]
    with open(f"h425/{cls}.txt", "w") as f:
        f.write("\n".join(keep) + "\n")
    print(cls, len(keep))
PYEOF
# viability: two independent runs on the merge class, compare minima
for r in 1 2; do
  taskset -c 1 src/x87_capture rn cos --status --timing=2001 < h425/merge.txt > h425/viab_$r.txt
done
python3 - <<'PYEOF'
a = [int(l.split()[-1]) for l in open("h425/viab_1.txt")]
b = [int(l.split()[-1]) for l in open("h425/viab_2.txt")]
import statistics
d = [abs(x-y) for x,y in zip(a,b)]
print(f"viability: n={len(a)} median_min_a={statistics.median(a)} "
      f"median_min_b={statistics.median(b)} median_|delta|={statistics.median(d)} max_delta={max(d)}")
PYEOF
# full interleaved runs
for r in 1 2 3; do
  for cls in add merge lane ctrl; do
    taskset -c 1 src/x87_capture rn cos --status --timing=2001 < h425/$cls.txt > h425/${cls}_run$r.txt
  done
done
python3 - <<'PYEOF'
import statistics, collections
print("=== per-class latency (min over runs of per-input min cycles) ===")
merged = {}
for cls in ("add","merge","lane","ctrl"):
    per_input = None
    for r in (1,2,3):
        vals = [int(l.split()[-1]) for l in open(f"h425/{cls}_run{r}.txt")]
        per_input = vals if per_input is None else [min(x,y) for x,y in zip(per_input, vals)]
    merged[cls] = per_input
    c = collections.Counter(per_input)
    top = sorted(c.items())[:8]
    print(f"{cls}: n={len(per_input)} median={statistics.median(per_input)} "
          f"min={min(per_input)} max={max(per_input)} mode_head={top}")
PYEOF

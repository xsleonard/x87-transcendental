#!/bin/bash
# h403: FPTAN exact-N hypothesis + NaN-handling fixes + h377 triangulation captures.
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
make -C src fsincos_skylake sibling_exhaustive 2>&1 | tail -2
src/fsincos_skylake --selftest > /dev/null && echo SELFTEST_PASS
mkdir -p h403

# --- the 18 FPTAN large-arg residual inputs (sibling notes) ---
cat > h403/fptan18.txt <<'INPUTS'
4039 da28b87c53033000
403b c0f1dcd732738000
403b f5e5383a74aa0000
403c 8d8935f5895fa800
403c 91df36fdbaae1000
403c a1441327fdc24000
403c a5d8f19fd3df5000
403d b7fcfadbf0691800
403d c986dafe33b96800
403d d1c13506eb22e800
403d fdc9efd7eba71000
c03a 8a9c14926dce3000
c03c 8d4f7f2c28979000
c03c d9202f3036e10800
c03d abb7a5bd0276f800
c03d b1eab9beceafd000
c03d f0128b4324f76800
c03d feb53a190ad93800
INPUTS

# --- h377 3 surviving inputs + +-4 ulp neighbors ---
python3 - <<'PYEOF'
seeds = [("401a","ed5c03467a232800"),("c006","8a7da33ed97f1000"),("c01c","ccb8a935dddf4000")]
with open("h403/h377_neighbors.txt","w") as f:
    for se, sig in seeds:
        s = int(sig,16)
        for d in range(-4,5):
            f.write(f"{se} {s+d:016x}\n")
PYEOF

# --- hardware captures ---
for mode in rn rd ru; do
  src/x87_capture $mode fptan --status < h403/fptan18.txt > h403/hw_fptan18_$mode.txt
  for insn in sin cos sincos fptan; do
    src/x87_capture $mode $insn --status < h403/h377_neighbors.txt > h403/hw_h377_${insn}_$mode.txt
  done
done

# --- model runs on the 18 ---
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  src/fsincos_skylake --batch $RC --fptan < h403/fptan18.txt > h403/m_fptan18_seed_$mode.txt
  src/fsincos_skylake --batch $RC --fptan --fptan-exact-n < h403/fptan18.txt > h403/m_fptan18_exact_$mode.txt
done
echo "=== FPTAN 18-input test (result tokens 1-2) ==="
python3 - <<'PYEOF'
for var in ("seed","exact"):
    tot = 0
    for m in ("rn","rd","ru"):
        hw = [l.split()[1:3] for l in open(f"h403/hw_fptan18_{m}.txt")]
        mo = [l.split()[1:3] for l in open(f"h403/m_fptan18_{var}_{m}.txt")]
        tot += sum(1 for a,b in zip(hw,mo) if a!=b)
    print(var, "total result misses on 18x3:", tot)
PYEOF

# --- model-vs-model divergence scan (seed vs exact) on all fptan corpora ---
cat capture-kit/inputs/sweep_inputs.txt capture-kit/inputs/dense_qn.txt > h403/all_inputs.txt
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  src/fsincos_skylake --batch $RC --fptan < h403/all_inputs.txt > h403/m_all_seed_$mode.txt &
  src/fsincos_skylake --batch $RC --fptan --fptan-exact-n < h403/all_inputs.txt > h403/m_all_exact_$mode.txt &
  wait
done
echo "=== seed-vs-exact divergence on sweep+dense ==="
python3 - <<'PYEOF'
inp = [l.strip() for l in open("h403/all_inputs.txt")]
div = set()
for m in ("rn","rd","ru"):
    a = open(f"h403/m_all_seed_{m}.txt").read().splitlines()
    b = open(f"h403/m_all_exact_{m}.txt").read().splitlines()
    for i,(x,y) in enumerate(zip(a,b)):
        if x != y: div.add(i)
print("divergent inputs:", len(div))
with open("h403/divergent_inputs.txt","w") as f:
    for i in sorted(div): f.write(inp[i]+"\n")
PYEOF
if [ -s h403/divergent_inputs.txt ]; then
  echo "=== hardware check of divergent inputs ==="
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    src/x87_capture $mode fptan --status < h403/divergent_inputs.txt > h403/hw_div_$mode.txt
    src/fsincos_skylake --batch $RC --fptan < h403/divergent_inputs.txt > h403/m_div_seed_$mode.txt
    src/fsincos_skylake --batch $RC --fptan --fptan-exact-n < h403/divergent_inputs.txt > h403/m_div_exact_$mode.txt
  done
  python3 - <<'PYEOF'
for var in ("seed","exact"):
    tot = 0
    for m in ("rn","rd","ru"):
        hw = [l.split()[1:3] for l in open(f"h403/hw_div_{m}.txt")]
        mo = [l.split()[1:3] for l in open(f"h403/m_div_{var}_{m}.txt")]
        tot += sum(1 for a,b in zip(hw,mo) if a!=b)
    print(var, "misses on divergent set:", tot)
PYEOF
fi

# --- sibling NaN verification ---
echo "=== sibling f2xm1 bits=16 ==="
src/sibling_exhaustive --instruction=f2xm1 --bits=16 --threads=2 --mode=all --max-report=4 2>&1 | tail -8
echo "=== sibling fptan bits=16 ==="
src/sibling_exhaustive --instruction=fptan --bits=16 --threads=2 --mode=all --max-report=4 2>&1 | tail -8

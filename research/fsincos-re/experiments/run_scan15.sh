#!/bin/sh
# comb-9: BLIND near-tie corpus for the h662 block-start law.
# comb7 [0xA8,0xC8) x128 + comb8 [0xC8,0xF0) x160 start grids, each
# shifted +2^53 (gap midpoints — no overlap with any mined segment),
# h491_scan3 (theta in {-2..+2}).  Capture cos x rn/rd/ru.
cd /root/h491
export LC_ALL=C
rm -f comb9_*.txt ties_comb9.txt comb9.done
python3 - <<'PYEOF' > starts_comb9.txt
for base, n in ((0xA800000000000000, 128), (0xC800000000000000, 160)):
    for i in range(n):
        print(f"{base + i * 2**54 + 2**53:016x}")
PYEOF
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan3 {} 250000000 > comb9_{}.txt" < starts_comb9.txt
for s in $(cat starts_comb9.txt); do cat "comb9_$s.txt"; done > ties_comb9.txt
awk '{print $1}' ties_comb9.txt | sort -u | sed 's/^/3ffc /' > comb9_inputs.txt
n=$(wc -l < comb9_inputs.txt)
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < comb9_inputs.txt > "comb9_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb9_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD $mode $l/$n" > comb9.done; exit 1; }
done
wc -l ties_comb9.txt > comb9.done
echo DONE >> comb9.done

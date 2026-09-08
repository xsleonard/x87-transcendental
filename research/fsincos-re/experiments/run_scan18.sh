#!/bin/sh
# comb-12: BLIND validation corpus for the h664b (66,0) theta-band
# tap vectors — all 160 comb11 W1 segment starts shifted +2^53 (gap
# midpoints, zero overlap with the mined segments).  h491_scan3
# near-ties, capture cos x rn/rd/ru.
cd /root/h491
export LC_ALL=C
rm -f comb12_*.txt ties_comb12.txt comb12.done
python3 - <<'PYEOF' > starts_comb12.txt
for i in range(160):
    print(f"{0x8000000000000000 + i * 2**54 + 2**53:016x}")
PYEOF
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan3 {} 250000000 > comb12_{}.txt" < starts_comb12.txt
for s in $(cat starts_comb12.txt); do cat "comb12_$s.txt"; done > ties_comb12.txt
awk '{print $1}' ties_comb12.txt | sort -u | sed 's/^/3ffc /' > comb12_inputs.txt
n=$(wc -l < comb12_inputs.txt)
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < comb12_inputs.txt > "comb12_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb12_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD $mode $l/$n" > comb12.done; exit 1; }
done
wc -l ties_comb12.txt > comb12.done
echo DONE >> comb12.done

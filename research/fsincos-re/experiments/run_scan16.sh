#!/bin/sh
# comb-10: near-collision pool extension for the sc read-depth
# campaign.  comb7 [0xA8,0xC8) x128 + comb8 [0xC8,0xF0) x160 start
# grids shifted +2^52 (disjoint from originals and from comb9's
# +2^53), h491_scan3 near-ties.  Capture cos AND sincos x rn/rd/ru.
cd /root/h491
export LC_ALL=C
rm -f comb10_*.txt ties_comb10.txt comb10.done
python3 - <<'PYEOF' > starts_comb10.txt
for base, n in ((0xA800000000000000, 128), (0xC800000000000000, 160)):
    for i in range(n):
        print(f"{base + i * 2**54 + 2**52:016x}")
PYEOF
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan3 {} 250000000 > comb10_{}.txt" < starts_comb10.txt
for s in $(cat starts_comb10.txt); do cat "comb10_$s.txt"; done > ties_comb10.txt
awk '{print $1}' ties_comb10.txt | sort -u | sed 's/^/3ffc /' > comb10_inputs.txt
n=$(wc -l < comb10_inputs.txt)
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < comb10_inputs.txt > "comb10_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb10_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD cos $mode $l/$n" > comb10.done; exit 1; }
    taskset -c 2 "$RUNNER" sincos "$mode" --status \
        < comb10_inputs.txt > "comb10_sc_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb10_sc_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD sc $mode $l/$n" > comb10.done; exit 1; }
done
wc -l ties_comb10.txt > comb10.done
echo DONE >> comb10.done

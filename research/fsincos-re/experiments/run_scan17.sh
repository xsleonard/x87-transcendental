#!/bin/sh
# comb-11: W1 window [0x80,0xA8) near-ties (theta in {-2..+2}) —
# the quadrant-(66,0) theta-band corpus (structurally absent from
# the [A8,F0) windows; comb5 covered W1 with the old theta=0-only
# scanner).  160 segs x 250M, h491_scan3.  Capture cos x rn/rd/ru.
cd /root/h491
export LC_ALL=C
rm -f comb11_*.txt ties_comb11.txt comb11.done
python3 - <<'PYEOF' > starts_comb11.txt
for i in range(160):
    print(f"{0x8000000000000000 + i * 2**54:016x}")
PYEOF
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan3 {} 250000000 > comb11_{}.txt" < starts_comb11.txt
for s in $(cat starts_comb11.txt); do cat "comb11_$s.txt"; done > ties_comb11.txt
awk '{print $1}' ties_comb11.txt | sort -u | sed 's/^/3ffc /' > comb11_inputs.txt
n=$(wc -l < comb11_inputs.txt)
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < comb11_inputs.txt > "comb11_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb11_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD $mode $l/$n" > comb11.done; exit 1; }
done
wc -l ties_comb11.txt > comb11.done
echo DONE >> comb11.done

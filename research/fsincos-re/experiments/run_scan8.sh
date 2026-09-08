#!/bin/sh
# comb-6: W2 primary [0xF0,0x100) x64 + shifted-validation W1/W2
# (+2^53) x224.  288 segments x 250M at 2^54 spacing, starts from
# Python.  Capture cos x rn/rd/ru.
cd /root/h491
export LC_ALL=C
rm -f comb6_*.txt ties_comb6.txt scan8.done cap522.done
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan {} 250000000 > comb6_{}.txt" < starts8.txt
for s in $(cat starts8.txt); do cat "comb6_$s.txt"; done > ties_comb6.txt
wc -l ties_comb6.txt > scan8.done
awk '{print $1}' ties_comb6.txt | sort -u | sed 's/^/3ffc /' > comb6_inputs.txt
n=$(wc -l < comb6_inputs.txt)
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < comb6_inputs.txt > "comb6_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb6_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD $mode $l/$n" > cap522.done; exit 1; }
done
echo DONE > cap522.done

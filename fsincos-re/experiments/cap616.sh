#!/bin/sh
cd /root/r57val
RUNNER=/root/x87_capture_x86_64
N=$(wc -l < h616_inputs.txt)
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" sin "$mode" --status \
        < h616_inputs.txt > "h616_${mode}_status.txt" || exit 1
    lines=$(wc -l < "h616_${mode}_status.txt")
    [ "$lines" -eq "$N" ] || { echo "BAD count $mode"; exit 1; }
done
echo DONE > h616.done

#!/bin/sh
# h597 blind disagreement test: 1600 dn-side FCOS inputs x rn/rd/ru.
cd "$(dirname "$0")"
RUNNER=/root/x87_capture_x86_64
N=$(wc -l < h597_inputs.txt)
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < h597_inputs.txt > "h597_${mode}_status.txt" || exit 1
done
for mode in rn rd ru; do
    lines=$(wc -l < "h597_${mode}_status.txt")
    [ "$lines" -eq "$N" ] || { echo "BAD count $mode: $lines"; exit 1; }
done
echo DONE > h597.done

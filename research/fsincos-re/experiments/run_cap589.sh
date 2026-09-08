#!/bin/sh
# h589 blind disagreement test: 1190 FCOS inputs x rn/rd/ru.
cd "$(dirname "$0")"
RUNNER=/root/x87_capture_x86_64
N=$(wc -l < h589_inputs.txt)
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < h589_inputs.txt > "h589_${mode}_status.txt" || exit 1
done
for mode in rn rd ru; do
    lines=$(wc -l < "h589_${mode}_status.txt")
    [ "$lines" -eq "$N" ] || { echo "BAD count $mode: $lines"; exit 1; }
done
echo DONE > h589.done

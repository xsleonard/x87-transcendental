#!/bin/sh
# h590f cross-schedule pairs: cos + sincos x rn/rd/ru.
cd "$(dirname "$0")"
RUNNER=/root/x87_capture_x86_64
N=$(wc -l < h590f_inputs.txt)
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < h590f_inputs.txt > "h590f_${mode}_status.txt" || exit 1
    taskset -c 2 "$RUNNER" sincos "$mode" --status \
        < h590f_inputs.txt > "h590f_sc_${mode}_status.txt" || exit 1
done
for f in h590f_rn h590f_rd h590f_ru h590f_sc_rn h590f_sc_rd h590f_sc_ru; do
    lines=$(wc -l < "${f}_status.txt")
    [ "$lines" -eq "$N" ] || { echo "BAD count $f: $lines"; exit 1; }
done
echo DONE > h590f.done

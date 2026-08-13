#!/bin/sh
# h590k cross-schedule pairs: cos + sincos x rn/rd/ru.
cd "$(dirname "$0")"
RUNNER=/root/x87_capture_x86_64
N=$(wc -l < h590k_inputs.txt)
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < h590k_inputs.txt > "h590k_${mode}_status.txt" || exit 1
    taskset -c 2 "$RUNNER" sincos "$mode" --status \
        < h590k_inputs.txt > "h590k_sc_${mode}_status.txt" || exit 1
done
for f in h590k_rn h590k_rd h590k_ru h590k_sc_rn h590k_sc_rd h590k_sc_ru; do
    lines=$(wc -l < "${f}_status.txt")
    [ "$lines" -eq "$N" ] || { echo "BAD count $f: $lines"; exit 1; }
done
echo DONE > h590k.done

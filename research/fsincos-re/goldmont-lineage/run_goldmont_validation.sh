#!/bin/sh
# Capture every (instruction, rounding mode, operand) tuple exactly once.
# Timing is deliberately disabled: x87_capture's timing mode repeats samples.
set -eu

if [ "$#" -ne 2 ]; then
    echo "usage: sh run_goldmont_validation.sh X87_CAPTURE OUTPUT_DIRECTORY" >&2
    exit 2
fi

goldmont_capture=$1
goldmont_output=$2
goldmont_here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
goldmont_inputs="$goldmont_here/validation-inputs.txt"

if [ ! -x "$goldmont_capture" ]; then
    echo "capture binary is not executable: $goldmont_capture" >&2
    exit 2
fi
if [ -e "$goldmont_output" ]; then
    echo "refusing to overwrite existing output: $goldmont_output" >&2
    exit 2
fi

mkdir -p "$goldmont_output"
sh "$goldmont_here/../capture-kit/cpu_info.sh" > "$goldmont_output/cpu_info.txt" 2>&1

for goldmont_mode in rn rd ru rz; do
    for goldmont_instruction in fsincos fsin fcos fptan; do
        case "$goldmont_instruction" in
            fsincos) goldmont_capture_instruction=sincos ;;
            fsin) goldmont_capture_instruction=sin ;;
            fcos) goldmont_capture_instruction=cos ;;
            fptan) goldmont_capture_instruction=fptan ;;
        esac
        "$goldmont_capture" "$goldmont_mode" pc64 \
            "$goldmont_capture_instruction" --status \
            < "$goldmont_inputs" \
            > "$goldmont_output/${goldmont_instruction}_${goldmont_mode}.txt"
    done
done

(
    cd "$goldmont_output"
    shasum -a 256 ./*.txt > SHA256SUMS
)

echo "captured 96 unique tuples in $goldmont_output"
echo "compare with: python3 $goldmont_here/compare_goldmont_capture.py $goldmont_output"

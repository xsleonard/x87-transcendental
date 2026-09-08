#!/bin/bash
# h440: build a second informative corpus for the product-gate labeling.
#
# Intent: the gate extraction is data-starved (only 127 fire rows total).
# This script, run entirely on the bare-metal i7 oracle:
#   1. builds the reconstruction model from source with gcc;
#   2. generates 8,000,000 random direct-path FCOS inputs in the e=-3
#      binade (the region where the phenomenon lives);
#   3. traces each input's terminal-correction state with the model's
#      --debug-cosine-carrier flag;
#   4. keeps only PRODUCT-BOUNDARY-SENSITIVE rows: inputs where
#      incrementing the left or right terminal product by one retained
#      unit changes the final result in some rounding mode — these are
#      the rows that can label the gates;
#   5. captures the kept inputs on this machine's own silicon under
#      RN/RD/RU (it is a verified byte-exact Skylake oracle);
#   6. leaves results in /root/corpus2/ for download.
set -e
mkdir -p /root/corpus2
cd /root/corpus2

gcc -O2 -o model /root/fsincos_skylake.c -lm

python3 - <<'PYEOF'
import random
rng = random.Random(0x440440)
with open("candidates.txt", "w") as f:
    for _ in range(8000000):
        significand = rng.getrandbits(64) | (1 << 63)
        sign = rng.getrandbits(1)
        sign_exponent = (sign << 15) | (-3 + 16383)
        f.write(f"{sign_exponent:04x} {significand:016x}\n")
print("candidates written")
PYEOF

FLAGS="--fcos-standalone --round18-poly --round21-table-bias \
 --round23-narrow-coefficient --round24-table-delta-rn67 \
 --round29-p5-fmul-route --round30-fsin-cosine-square \
 --round31-fsin-cosine-tail --round32-fsin-cosine-horner \
 --round33-fsin-cosine-product --round34-table-lookup-firc \
 --round35-table-p-terminal --round36-table-fadd-microcontrol \
 --round37-p6-four-term --round41-fsin-cosine-split \
 --round42-p6-sine-split --round43-p6-sine-bias --round44-p6-sine-bias \
 --round45-p6-sine-fraction --round46-p6-narrow-sine-fraction \
 --round47-p6-narrow-sine-fraction --round48-p6-narrow-sine-fraction \
 --round49-p6-carrier-interval --round50-fsin-operation-classes \
 --round38-p6-cosine-split --round39-fcos-tiny \
 --round52-fcos-low3-carrier --round53-fcos-operation-classes"
./model --batch $FLAGS --debug-cosine-carrier < candidates.txt \
    > /dev/null 2> traces_all.txt
echo "traced $(wc -l < traces_all.txt) rows"

python3 /root/corpus2_filter.py
echo "selected $(wc -l < selected_inputs.txt) product-boundary rows"

for mode in rn rd ru; do
    /root/x87_capture_x86_64 $mode cos --status < selected_inputs.txt \
        > hw_$mode.txt
done
echo CORPUS2_COMPLETE

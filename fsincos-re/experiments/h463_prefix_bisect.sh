#!/bin/sh
# h463: corpus-prefix bisection on the bare-metal i7 (archival copy of
# the remote script; ran in /root/h463).
#
# Intent: after h461 proved the full corpus2 stream replays
# byte-for-byte while short replay windows (h459/h462, depths 1-32) did
# not reproduce the then-suspected "context fires", this script
# captured two probe inputs after corpus prefixes of increasing length
# K, each in a fresh runner invocation.  Outcome: flat in K — no stream
# state exists.  The suspected context dependence was subsequently
# explained as a pre-patch/post-patch labeling coordinate artifact (see
# skylake-comparison.md, h456-h463 section); this run is part of the
# context-independence proof suite.
cd /root/h463
IN=/root/corpus2/selected_inputs.txt
probe () {
    name=$1; x=$2
    for K in 0 64 256 1024 4096 8192 12288 14500; do
        for mode in rn rd ru; do
            { head -n $K $IN; echo "$x"; } | \
                taskset -c 2 /root/x87_capture_x86_64 cos $mode --status | \
                tail -1 > "out_${name}_${K}_${mode}.txt"
        done
    done
}
probe flip14572 "bffc da1f16bbf007c83e"
probe flip19905 "3ffc 8672d9bcb999eb5a"
echo DONE > h463.done

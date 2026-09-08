#!/bin/bash
# Build a frozen, ledger-disabled R96 adversarial bank and its absolute
# endpoint-response probes.  Refuse to replace any prior h1068 binary.
set -eu

SOURCE=${1:-fsincos_skylake.c}
if [ ! -r "$SOURCE" ]; then
    echo "missing source: $SOURCE" >&2
    exit 1
fi

for output in h1068_base h1068_candidate \
    h1068_force1 h1068_force2 h1068_force3 h1068_force4 h1068_force5 \
    h1068_force6 h1068_force7 h1068_force8 h1068_force9 h1068_force10; do
    if [ -e "$output" ]; then
        echo "refusing to overwrite existing binary: $output" >&2
        exit 1
    fi
done

COMMON="-O2 -ffp-contract=off -DG_ROUND84=0"
gcc $COMMON -DG_R96TOPCLOSED=0 -DG_R96ACTCLOSED=0 \
    -o h1068_base "$SOURCE" -lm
gcc $COMMON -o h1068_candidate "$SOURCE" -lm

index=1
while [ "$index" -le 10 ]; do
    gcc $COMMON -DG_R96TOPCLOSED=0 -DG_R96ACTCLOSED=0 \
        -DG_R96FORCE="$index" -o "h1068_force$index" "$SOURCE" -lm
    index=$((index + 1))
done

./h1068_candidate --selftest
echo H1068_MODELS_READY

#!/bin/bash
# h922 v2: r59 ON-vs-OFF differential over the comb corpora, all 4
# modes, streaming (process substitution — no /tmp transients).
# Output: h922_diff.txt.gz, lines "corpus mode NR on_se on_sig off_se
# off_sig" — the scope-constraint set for the R91 decline-r59
# candidate.  ON = shipped R90 ledger-off; OFF = same with
# g_round59_fcos_theta_band=0 (all four r59 sub-branches skipped).
cd /root/r84
: > h922_diff.txt
for c in comb7 comb9 comb13 comb15 comb16 comb17 comb18; do
  for m in rn rd ru rz; do
    RC=""; [ $m != rn ] && RC="--rc=$m"
    paste -d"|" \
      <(./model_h917_noled --batch --fcos-standalone $RC \
          < /root/h491/${c}_inputs.txt) \
      <(./model_h921_nor59 --batch --fcos-standalone $RC \
          < /root/h491/${c}_inputs.txt) \
      | awk -F"|" -v c=$c -v m=$m '$1!=$2{gsub(/OK /,""); print c, m, NR, $1, $2}' \
      >> h922_diff.txt
    echo "$c $m done $(wc -l < h922_diff.txt) $(date +%H:%M) free=$(df -m / | tail -1 | awk "{print \$4}")M" >> h922_progress.log
  done
done
gzip -f h922_diff.txt
echo H922V2_DONE >> h922_progress.log

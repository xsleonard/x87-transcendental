#!/bin/bash
# Resume of h914_chain.sh: the original died at seed 94486 (chunk 38
# of batch 8) on ENOSPC 2026-08-27 ~08:36 (disk filled by the h918
# harvest — collateral).  Remaining span: 94487-94511 (rest of batch
# 8) + 94512-94575 (batch 9) + 94576-94639 (batch 10).
/root/r84/h913_tailscan.sh 25 94487 >> /root/r84/h914_fringe.log 2>&1
/root/r84/h913_tailscan.sh 64 94512 >> /root/r84/h914_fringe.log 2>&1
/root/r84/h913_tailscan.sh 64 94576 >> /root/r84/h914_fringe.log 2>&1
echo H914_CHAIN_DONE >> /root/r84/h914_fringe.log

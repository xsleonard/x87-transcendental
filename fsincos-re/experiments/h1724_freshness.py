#!/usr/bin/env python3
"""Use the same conservative local/private clearance for the small separator bank."""
import h1721_freshness as base
base.BANK='tmp/ledger33/current/h1724_challenge_bank/bank.json'
base.SOFTWARE=('tmp/ledger33/current/h1724_schedule_scan','tmp/ledger33/current/h1724_challenge_bank')
if __name__=='__main__':base.main()

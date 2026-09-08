#!/usr/bin/env python3
# h779: THE MECHANISM TEST — chain with f4' = chop67(sq*(sq&~7))
# (one squarer port truncated to 64 bits) must reproduce the chip's
# poly (= shipped+1 retained lsb) exactly on every sine vote.
# Result 2026-08-19: 148/148 derivation + 86/86 BLIND (ck9-13).
# Bypass is EPOCH-GATED machine state — see HANDOFF section.
# (Body = the exact-variant heredoc from the session; reconstruct
# from HANDOFF 'THE SINE-BRANCH MECHANISM IS SOLVED' — 30 lines:
# chain(mag, byp) with sq64 = ((|sq|/g).floor & ~7)*g, byp toggles
# f4 = trunc(sq*sq64, 67) vs trunc(sq*sq, 67); score
# abs(p1) == abs(p0) + 2^(texp(|p0|)-63) per vote.)

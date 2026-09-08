"""Unpromoted D0008 discovery candidate, FALSIFIED by fresh D0009.

Use the short physically decoded ROM coefficients on the table-reduced
path, and retain the long set on the direct path. The last tail multiplier
reads z through magnitude CHOP64; the lead z and square retain CHOP67.
These are fixed operation roles, not tests of particular operands/residues.
"""
from dataclasses import replace
from graph_v3 import prevalue as _prevalue
from graph_v4 import PROGRAM as V4

PROGRAM=replace(V4,table_coefficients='short',tail_z_read='chop64')


def prevalue(ys,ym,xs,xm,program=PROGRAM,trace=None):
    return _prevalue(ys,ym,xs,xm,program,trace)

"""Single finite numerical candidate, still analysis-only and unpromoted.

The direct/table boundary is the midpoint between ROM entries 1/32 and 2/32.
There is no table-index-1 path in this candidate. The reduced kernel sum is
an intermediate on the table path, hence CHOP67 before adding the ROM angle.
The direct kernel sum is final unless quadrant restoration follows. This is
an operation-role distinction, not an exception keyed to error operands.

Fresh validation and special-value/encoding coverage are still required.
"""
from graph_v3 import Program,prevalue as _prevalue

PROGRAM=Program(direct_numerator=3,direct_limit=64,table_kernel_cut='chop67')


def prevalue(ys,ym,xs,xm,program=PROGRAM,trace=None):
    return _prevalue(ys,ym,xs,xm,program,trace)

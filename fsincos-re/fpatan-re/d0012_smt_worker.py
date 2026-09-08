"""Isolated local SMT worker; its parent enforces an external deadline."""
import argparse
import json
import z3


def main():
    ap=argparse.ArgumentParser();ap.add_argument('query');ap.add_argument('--timeout-ms',type=int,required=True);a=ap.parse_args()
    s=z3.Solver();s.from_file(a.query);s.set(timeout=a.timeout_ms);r=s.check()
    report=dict(result=str(r),reason_unknown=s.reason_unknown() if r==z3.unknown else None)
    if r==z3.sat:
        m=s.model();report['offsets']={k:m.eval(z3.Int(f'delta_{k}'),model_completion=True).as_long() for k in range(118,124)}
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()

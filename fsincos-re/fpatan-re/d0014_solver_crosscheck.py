"""Externally bounded independent parser/solver checks of frozen SMT queries.

The parent never edits a query. CVC5 consumes the exact Z3-exported SMT2.
Every child outcome, including UNKNOWN or a termination, is retained.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from prepare import save


def worker(path, timeout, logic):
    import cvc5
    solver = cvc5.Solver()
    solver.setLogic(logic)
    solver.setOption('tlimit-per', str(timeout))
    parser = cvc5.InputParser(solver)
    parser.setFileInput(cvc5.InputLanguage.SMT_LIB_2_6, str(path))
    symbols = parser.getSymbolManager()
    replies = []
    while True:
        command = parser.nextCommand()
        if command.isNull():
            break
        reply = command.invoke(solver, symbols)
        if reply:
            replies.append(reply.strip())
    outcomes = [line for reply in replies for line in reply.splitlines() if line in ('sat', 'unsat', 'unknown')]
    assert len(outcomes) == 1, replies
    print(json.dumps(dict(solver='CVC5 ' + cvc5.__version__, result=outcomes[0], replies=replies)), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('query', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--timeout-ms', type=int, default=60000)
    ap.add_argument('--worker', action='store_true')
    ap.add_argument('--logic', choices=('QF_LIA', 'QF_LRA'), default='QF_LIA')
    args = ap.parse_args()
    if args.worker:
        worker(args.query, args.timeout_ms, args.logic)
        return
    assert args.out and not args.out.exists()
    content = args.query.read_bytes()
    started = time.monotonic()
    child = subprocess.Popen([sys.executable, str(Path(__file__)), str(args.query), '--worker',
                              '--timeout-ms', str(args.timeout_ms), '--logic', args.logic],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = False
    try:
        stdout, stderr = child.communicate(timeout=args.timeout_ms / 1000 + 2)
    except subprocess.TimeoutExpired:
        deadline = True
        child.terminate()
        stdout, stderr = child.communicate(timeout=10)
    result = (dict(result='unknown', reason='external deadline; child terminated') if deadline
              else json.loads(stdout) if child.returncode == 0
              else dict(result='error', reason='worker failed', stdout=stdout))
    assert content == args.query.read_bytes(), 'Frozen query changed'
    report = dict(status='INDEPENDENT_FROZEN_QUERY_CROSSCHECK', query=str(args.query),
                  query_sha256=hashlib.sha256(content).hexdigest(), query_bytes=len(content),
                  logic=args.logic,
                  timeout_ms=args.timeout_ms, external_deadline=deadline, worker_returncode=child.returncode,
                  worker_stderr=stderr, outcome=result, elapsed_seconds=time.monotonic() - started,
                  hardware_executed=False)
    save(args.out, report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()

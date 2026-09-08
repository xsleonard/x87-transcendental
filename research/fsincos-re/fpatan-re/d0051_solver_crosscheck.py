"""Cross-check an immutable SMT query; preserve diagnostic UNKNOWN replies.

Unlike the frozen D0048 parser, this accepts CVC5's `unknown (TIMEOUT)`
reply. The original failed D0048 receipts are not changed or reclassified.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from compressed_guard import digest
from prepare import save


def parse_result(replies):
    results = []
    for reply in replies:
        for line in reply.splitlines():
            match = re.fullmatch(r'(sat|unsat|unknown)(?:\s+\(([^\n]*)\))?', line.strip())
            if match:
                results.append((match.group(1), match.group(2)))
    assert len(results) == 1, replies
    return results[0]


def worker(query, timeout):
    sys.path.insert(0, '/private/tmp/fsincos-smt-deps')
    import cvc5
    solver = cvc5.Solver()
    # The immutable SMT2 file selects its original logic.
    solver.setOption('tlimit-per', str(timeout))
    solver.setOption('produce-models', 'true')
    parser = cvc5.InputParser(solver)
    parser.setFileInput(cvc5.InputLanguage.SMT_LIB_2_6, str(query))
    symbols, replies = parser.getSymbolManager(), []
    while True:
        command = parser.nextCommand()
        if command.isNull():
            break
        reply = command.invoke(solver, symbols)
        if reply:
            replies.append(reply.strip())
    result, reason = parse_result(replies)
    report = dict(result=result, reason=reason, replies=replies,
                  solver='CVC5 ' + cvc5.__version__)
    if result == 'sat':
        terms = {str(t): t for t in symbols.getDeclaredTerms()}
        value = solver.getValue(terms['u_significand'])
        report['u_significand'] = (value.getBitVectorValue(16) if value.isBitVectorValue()
                                  else f'{int(str(value)):016x}')
    print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--timeout-ms', type=int, default=10000)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        worker(args.query, args.timeout_ms)
        return
    assert args.out and not args.out.exists()
    sha, started = digest(args.query), time.monotonic()
    process = subprocess.Popen([sys.executable, str(Path(__file__)), str(args.query),
        '--worker', '--timeout-ms', str(args.timeout_ms)], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = False
    try:
        stdout, stderr = process.communicate(timeout=args.timeout_ms / 1000 + 5)
    except subprocess.TimeoutExpired:
        deadline = True
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
    outcome = (dict(result='unknown', reason='external deadline') if deadline else
               json.loads(stdout) if process.returncode == 0 else dict(result='error'))
    assert digest(args.query) == sha
    report = dict(status='IMMUTABLE_QUERY_CROSSCHECK', query_sha256=sha,
        timeout_ms=args.timeout_ms, elapsed_seconds=time.monotonic() - started,
        external_deadline=deadline, returncode=process.returncode,
        stdout=stdout, stderr=stderr, outcome=outcome,
        source_sha256=digest(Path(__file__)), hardware_executed=False,
        limits='Scope is exactly the original query, including any relaxation. UNKNOWN is not exclusion. SAT still requires exact arithmetic and external endpoint checks.')
    save(args.out, report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()

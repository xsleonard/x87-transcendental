"""Independent CVC5 parsing/solving of immutable D0047 queries."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from compressed_guard import digest
from prepare import save


def worker(query, timeout):
    sys.path.insert(0, '/private/tmp/fsincos-smt-deps')
    import cvc5
    solver = cvc5.Solver()
    solver.setLogic('QF_BV')
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
    outcomes = [r for reply in replies for r in reply.splitlines() if r in ('sat', 'unsat', 'unknown')]
    assert len(outcomes) == 1, replies
    result = dict(result=outcomes[0], solver='CVC5 ' + cvc5.__version__, replies=replies)
    if outcomes[0] == 'sat':
        variables = {str(term): term for term in symbols.getDeclaredTerms()}
        result['u_significand'] = solver.getValue(variables['u_significand']).getBitVectorValue(16)
    print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--timeout-ms', type=int, default=30000)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        worker(args.query, args.timeout_ms)
        return
    assert args.out and not args.out.exists()
    sha, started = digest(args.query), time.monotonic()
    process = subprocess.Popen([sys.executable, str(Path(__file__)), str(args.query),
        '--worker', '--timeout-ms', str(args.timeout_ms)], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True)
    deadline = False
    try:
        stdout, stderr = process.communicate(timeout=args.timeout_ms / 1000 + 5)
    except subprocess.TimeoutExpired:
        deadline = True
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
    outcome = (dict(result='unknown', reason='external deadline') if deadline else
               json.loads(stdout) if process.returncode == 0 else dict(result='error', stdout=stdout))
    assert digest(args.query) == sha
    report = dict(status='INDEPENDENT_IMMUTABLE_QUERY_CHECK', query_sha256=sha,
        timeout_ms=args.timeout_ms, elapsed_seconds=time.monotonic() - started,
        external_deadline=deadline, returncode=process.returncode, stderr=stderr,
        outcome=outcome, source_sha256=digest(Path(__file__)), hardware_executed=False,
        limits='The original normalization-template scope is unchanged. UNKNOWN is not an exclusion; any SAT value needs independent exact replay and external lifting.')
    save(args.out, report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()

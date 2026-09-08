#!/usr/bin/env python3
"""Authenticate the target binary and its once-only fault observation cuts.

Static machine-code checks only. Never execute this hardware harness as a test.
"""
import argparse
import json
import re
from pathlib import Path
from h1650_score_masked_state import digest
from h1640_remaining_scope_freshness import save

BUILD = 'tmp/ledger33/current/h1654_capture_build/'
LOCKS = {
    'capture-kit/x87_exception_transition_capture.c': '7ac8b93ff9361fd4160d969c3fb4f750f1caa310479e8f282abc8131782e6fb7',
    'capture-kit/x87_state_capture.c': '1b2df713deeb44576169c7f75e86a1365f92b6315da284280e8c76437588980b',
    BUILD+'x87_exception_transition_capture': '1f0be29e0447c4b8390e3edf0b69a78f996d7c2e6293e0588ef7087cb870212e',
    BUILD+'capture.disassembly.txt': 'eebc646467582d364cd6770d90895d7adf735f6f7c5851b9c2a53fa2b975e12f',
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root, out = a.root.resolve(), a.output_dir.resolve()
    assert not out.exists()
    for name, sha in LOCKS.items():
        assert digest(root/name) == sha, name
    symbols, instructions = {}, []
    for line in (root/BUILD/'capture.disassembly.txt').read_text().splitlines():
        label = re.fullmatch(r'([0-9a-f]+) <([^>]+)>:', line)
        if label:
            symbols[label[2]] = int(label[1], 16)
        fields = line.split('\t')
        if len(fields) >= 3 and re.fullmatch(r'\s*[0-9a-f]+:', fields[0]):
            instructions.append((int(fields[0].strip()[:-1], 16), fields[2].strip()))
    sites = {}
    for family, op in (('sin', 'fsin'), ('cos', 'fcos')):
        start = symbols['h1654_once_'+family]
        wait = symbols['h1654_'+family+'_wait']
        resume = symbols['h1654_'+family+'_resume']
        body = [(address, code) for address, code in instructions if start <= address <= resume+2]
        assert [code.split()[0] for _, code in body] == [op, 'fxsave64', 'movl', 'fwait', 'fnclex', 'ret']
        assert body[1][1] == 'fxsave64 (%rdi)'
        assert '$0x1' in body[2][1] and '<h1654_after_valid>' in body[2][1]
        assert body[3][0] == wait and body[4][0] == resume and resume == wait+1
        sites[op] = dict(site=hex(start), no_wait_snapshot=hex(body[1][0]),
                         wait=hex(wait), resume=hex(resume), instruction_count=6)
    handler = [code for address, code in instructions if symbols['catch_fpe'] <= address < symbols['load_stack']]
    calls = [code for code in handler if code.startswith('call')]
    assert len(calls) == 2 and all('<_exit@plt>' in code for code in calls)
    assert not any(re.search(r'\b(?:xmm|ymm|zmm|st\()[0-9]?', code) for code in handler)
    assert not any(code.split()[0].startswith(('f', 'v')) for code in handler)
    copy_limit = next(i for i, code in enumerate(handler) if '$0x200,%rax' in code)
    clear = next(i for i, code in enumerate(handler) if '$0x7f00,0x2(%rcx)' in code)
    assert copy_limit < clear
    assert any('$0x3f,(%rcx)' in code for code in handler)
    assert any('<expected_resume>' in code for code in handler)
    main_code = [code for address, code in instructions if symbols['main'] <= address < symbols['_start']]
    active_calls = [code for code in main_code if re.search(r'call.*<h1654_once_(sin|cos)>', code)]
    assert len(active_calls) == 2
    assert not any(re.search(r'call.*<(execute_once|h1400_archived_main_not_used)>', code) for code in main_code)
    out.mkdir(parents=True)
    report = dict(experiment='h1654_capture_static_audit', status='PASS_STATIC_NOT_EXECUTED',
        sites=sites, handler_library_calls='Two fail-closed _exit calls only; no vector/x87 instructions',
        capture_build='gcc -O2 -std=c11 -Wall -Wextra -Werror -fno-builtin',
        observed_remote_compiler='gcc (Debian 12.2.0-14+deb12u1) 12.2.0',
        remote_directory='/root/fsincos-h1654-exception-state',
        hardware_execution='none', manifest_frozen=False, private_ledger_access='none',
        claim_boundary='Authenticated source/ELF/disassembly and finite straight-line instruction cuts, not Linux signal-delivery or silicon-state validation. The archived included main is not on the active call path.',
        sha256=dict(evidence=LOCKS, script=digest(Path(__file__))))
    save(out/'report.json', report)
    print(json.dumps(dict(status=report['status'], sites=sites), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()

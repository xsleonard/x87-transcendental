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

BUILD = 'tmp/ledger33/current/h1672_capture_build/'
LOCKS = {
    BUILD+'linux-v6.1-traps.c': 'da2b5ca41fbbec6594be05cdd9d6a246be81c85e859c1ef4fd967d30e43e659d',
    BUILD+'linux-v6.1-fpu-core.c': 'de01bb51a8963aa5cd8eebcdc229b40e98fb0682e6b0f93cba82c973bf05e9d8',
    'capture-kit/x87_guarded_summary_capture.c': '9b5c6f81d666382c5d4acc9ec90a70a65531f09d955fbb921bb9b1edf30ae1c4',
    'capture-kit/x87_state_capture.c': '1b2df713deeb44576169c7f75e86a1365f92b6315da284280e8c76437588980b',
    BUILD+'x87_guarded_summary_capture': '72d49ae21259b15c2941a19537976221459a731f5dc6d99d90de0e33e30e7bb6',
    BUILD+'capture.disassembly.txt': 'f9a2b4d37b96e58e4fae23c111c400d431e55d375cdd7bc850a75a523104d8ca',
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root, out = a.root.resolve(), a.output_dir.resolve()
    assert not out.exists()
    for name, sha in LOCKS.items():
        assert digest(root/name) == sha, name
    source = (root/'capture-kit/x87_guarded_summary_capture.c').read_text()
    assert '(summary & ~0x8080u)' in source
    assert 'summary != !!' not in source
    assert '((load_u16(before.bytes + 2) ^ sw) & ~0x8080u)' in source
    assert 'SUMMARY=%04x EMPTY=%u REQ_SW=%04x' in source
    assert [v for v in range(65536) if not v & ~0x8080] == [0, 128, 32768, 32896]
    assert '!!(actual_sw & ~actual_cw & 0x3fu) || !(actual_sw & 0x8080u)' in source
    assert 'ATTEMPTED=%d' in source
    traps=(root/BUILD/'linux-v6.1-traps.c').read_text()
    core=(root/BUILD/'linux-v6.1-fpu-core.c').read_text()
    assert re.search(r'si_code = fpu__exception_code.*?if \(!si_code\)\s*goto exit;',traps,re.S)
    function=core[core.index('int fpu__exception_code('):]
    assert 'err = swd & ~cwd;' in function and 'return 0;' in function
    allowed=skipped=0
    for flags in range(64):
        for masks in range(64):
            for summary in (0,128,32768,32896):
                attempt=bool(flags & ~masks & 63) or not summary
                allowed+=attempt; skipped+=not attempt
    assert (allowed,skipped)==(14197,2187)
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
        start = symbols['h1672_once_'+family]
        wait = symbols['h1672_'+family+'_wait']
        resume = symbols['h1672_'+family+'_resume']
        body = [(address, code) for address, code in instructions if start <= address <= resume+2]
        assert [code.split()[0] for _, code in body] == [op, 'fxsave64', 'movl', 'fwait', 'fnclex', 'ret']
        assert body[1][1] == 'fxsave64 (%rdi)'
        assert '$0x1' in body[2][1] and '<h1672_after_valid>' in body[2][1]
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
    active_calls = [code for code in main_code if re.search(r'call.*<h1672_once_(sin|cos)>', code)]
    assert len(active_calls) == 2
    assert not any(re.search(r'call.*<(execute_once|h1400_archived_main_not_used)>', code) for code in main_code)
    code={address:text.split('#',1)[0].strip() for address,text in instructions}
    assert re.fullmatch(r'test\s+\$0x3f,%al',code[0x158a])
    assert code[0x158c].startswith('jne') and '159a' in code[0x158c]
    assert re.fullmatch(r'test\s+\$0x8080,%r13w',code[0x158e])
    assert code[0x1594].startswith('jne') and '1749' in code[0x1594]
    assert code[0x1749]=='fnclex' and code[0x1750].startswith('jmp') and '15f6' in code[0x1750]
    assert not any(text.startswith('call') for address,text in instructions if 0x1749<=address<=0x1750)
    out.mkdir(parents=True)
    report = dict(experiment='h1672_capture_static_audit', status='PASS_STATIC_NOT_EXECUTED',
        sites=sites, handler_library_calls='Two fail-closed _exit calls only; no vector/x87 instructions',
        capture_build='gcc -O2 -std=c11 -Wall -Wextra -Werror -fno-builtin',
        observed_remote_compiler='gcc (Debian 12.2.0-14+deb12u1) 12.2.0',
        remote_directory='/root/fsincos-h1672-guarded-summary',
        requested_summary_values=['0000', '0080', '8000', '8080'],
        preserved_invariants='CW, SW excluding ES/B, FTW and raw ST0 must restore exactly. Requested SW and actual before SW are recorded separately.',
        guard_checks=dict(mask_flag_summary_cases=16384,allowed=allowed,skipped=skipped,
            compiled_branch='158a tests U; 158e tests summary; unsafe edge 1594->1749 executes FNCLEX then jumps beyond both transcendental calls.',
            unsafe_semantics='BEFORE_ONLY with ATTEMPTED=0. No FSIN/FCOS/FWAIT consumption observation.'),
        kernel_hazard=dict(upstream_version='v6.1',observed_host_release='6.1.0-52-amd64',
            traps_url='https://github.com/torvalds/linux/blob/v6.1/arch/x86/kernel/traps.c',
            classifier_url='https://github.com/torvalds/linux/blob/v6.1/arch/x86/kernel/fpu/core.c',
            limit='Conditional risk established from upstream source in the host kernel series; exact Debian binary not disassembled. No #MF or retry was induced.'),
        hardware_execution='none', manifest_frozen=False, private_ledger_access='none',
        claim_boundary='Authenticated source/ELF/disassembly and finite straight-line instruction cuts, not Linux signal-delivery or silicon-state validation. The archived included main is not on the active call path.',
        sha256=dict(evidence=LOCKS, script=digest(Path(__file__))))
    save(out/'report.json', report)
    print(json.dumps(dict(status=report['status'], sites=sites), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()

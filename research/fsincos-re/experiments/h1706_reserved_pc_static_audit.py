#!/usr/bin/env python3
"""Authenticate an UNEXECUTED all-masked reserved-PC observation harness.

Only an isolated integer/string parser unit is executed locally. The Linux
capture ELF is parsed/disassembled, never launched or supplied with inputs.
No manifest freeze, freshness clearance, hardware labels or candidate change.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
from pathlib import Path
from h1640_remaining_scope_freshness import save
from h1650_score_masked_state import digest

BUILD = 'tmp/ledger33/current/h1706_capture_build/'
LOCKS = {
    'capture-kit/x87_exception_transition_capture.c': '7ac8b93ff9361fd4160d969c3fb4f750f1caa310479e8f282abc8131782e6fb7',
    'capture-kit/x87_state_capture.c': '1b2df713deeb44576169c7f75e86a1365f92b6315da284280e8c76437588980b',
    'capture-kit/x87_reserved_precision_capture.c': '28459c28ccea803905945f001578fb9f31dc0064872c255eecf52456faad0175',
    BUILD+'x87_reserved_precision_capture': '05627412309d580122365eeb88006c9e84de88c1e153d42cb96a1125aabdea4b',
    BUILD+'capture.disassembly.txt': '9ebeeb0806cf7d674629afa08e2dd8739a636defe611dbe58846099d898da518',
}
ORIGINAL_INCLUDE = '''#define main h1400_archived_main_not_used
#include "x87_state_capture.c"
#undef main'''
NEW_INCLUDE = '''#define main h1400_archived_main_not_used
#define parse_precision h1706_standard_precision
#include "x87_state_capture.c"
#undef parse_precision
#undef main

/* The archived included main retains its original parser. Only this probe's
 * active main accepts PC=01, so no historical capture source is changed. */
static int parse_precision(const char *text, uint16_t *bits)
{
    if (!strcmp(text, "pc01")) {
        *bits = 0x0100;
        return 1;
    }
    return h1706_standard_precision(text, bits);
}'''


def source_equivalence(root):
    old = (root/'capture-kit/x87_exception_transition_capture.c').read_text()
    new = (root/'capture-kit/x87_reserved_precision_capture.c').read_text()
    assert new.count('/* H1654:') == 1
    body = new[new.index('/* H1654:'):]
    assert body.count(NEW_INCLUDE) == 1
    assert body.count('|| masks != 0x3f || pending != 0 || depth < 1') == 1
    restored = body.replace(NEW_INCLUDE, ORIGINAL_INCLUDE).replace(
        '|| masks != 0x3f || pending != 0 || depth < 1', '|| masks > 0x3f || depth < 1')
    assert restored.rstrip() == old.rstrip()
    # This proves the once-sites, handler and before-state verification were
    # not source-edited. It does not prove the OS or hardware will accept PC01.
    return dict(changes=['Added isolated pc01 parser with standard-PC fallback',
        'Restricted input to masks3f and pending0', 'Added unexecuted-probe header'],
        other_H1654_source_and_comments_unchanged=True)


def machine_code(root):
    symbols, instructions = {}, []
    for line in (root/BUILD/'capture.disassembly.txt').read_text().splitlines():
        label = re.fullmatch(r'([0-9a-f]+) <([^>]+)>:', line)
        if label: symbols[label[2]] = int(label[1], 16)
        fields = line.split('\t')
        if len(fields) >= 3 and re.fullmatch(r'\s*[0-9a-f]+:', fields[0]):
            instructions.append((int(fields[0].strip()[:-1], 16), fields[2].strip()))
    sites = {}
    for family, op in (('sin', 'fsin'), ('cos', 'fcos')):
        start = symbols['h1654_once_'+family]
        wait, resume = (symbols['h1654_'+family+'_'+label] for label in ('wait', 'resume'))
        body = [(address, code) for address, code in instructions if start <= address <= resume+2]
        assert [code.split()[0] for _, code in body] == [op, 'fxsave64', 'movl', 'fwait', 'fnclex', 'ret']
        assert body[1][1] == 'fxsave64 (%rdi)'
        assert '$0x1' in body[2][1] and '<h1654_after_valid>' in body[2][1]
        assert body[3][0] == wait and body[4][0] == resume and resume == wait+1
        sites[op] = dict(site=hex(start), no_wait_snapshot=hex(body[1][0]), wait=hex(wait), resume=hex(resume), instructions=6)
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
    main = [code for address, code in instructions if symbols['main'] <= address < symbols['_start']]
    active_calls = [code for code in main if re.search(r'call.*<h1654_once_(sin|cos)>', code)]
    assert len(active_calls) == 2
    assert not any(re.search(r'call.*<(execute_once|h1400_archived_main_not_used)>', code) for code in main)
    return dict(sites=sites, handler='Two fail-closed _exit calls, no vector/x87 instructions; copy precedes context repair',
        active_main_has_only_two_once_site_calls=True,
        boundary='Source-delta and fixed observation-cut checks, not a general machine-code CFG or kernel/silicon proof.')


def parser_test(root, out):
    base = (root/'capture-kit/x87_state_capture.c').read_text()
    match = re.search(r'static int parse_precision\(const char \*text, uint16_t \*bits\)\n\{.*?\n\}', base, re.S)
    assert match
    old = match.group().replace('parse_precision', 'h1706_standard_precision')
    new = NEW_INCLUDE[NEW_INCLUDE.index('static int parse_precision'):]
    # Only these actual parser bodies enter the portable executable. There is
    # no include of the capture source, inline asm or numerical instruction.
    program = '''#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
'''+old+'\n'+new+'''
static unsigned cases;
static void check(const char *s) {
    int wanted = -1;
    if (!strcmp(s, "pc24")) wanted=0;
    if (!strcmp(s, "pc01")) wanted=0x100;
    if (!strcmp(s, "pc53")) wanted=0x200;
    if (!strcmp(s, "pc64")) wanted=0x300;
    uint16_t bits=0xbeef, prior=0xbeef;
    int got=parse_precision(s, &bits);
    assert(got==(wanted>=0));
    assert(bits==(wanted>=0 ? wanted : 0xbeef));
    int standard=h1706_standard_precision(s, &prior);
    assert(standard==(wanted>=0 && wanted!=0x100));
    assert(prior==(standard ? wanted : 0xbeef));
    ++cases;
}
int main(void) {
    const char *extra[]={"", "pc", "pc1", "PC01", "pc01 ", "pc01\\n", "pc128", "24", "01", "pc-1"};
    for(unsigned i=0;i<sizeof(extra)/sizeof(extra[0]);++i) check(extra[i]);
    for(unsigned a=0;a<128;++a) for(unsigned b=0;b<128;++b) {
        char s[]={'p','c',(char)a,(char)b,0}; check(s);
    }
    printf("PARSER_ONLY_PASS cases=%u\\n", cases);
    return 0;
}
'''
    assert '__asm__' not in program and 'fxsave' not in program
    source, binary = out/'parser_unit.c', out/'parser_unit'
    with source.open('x') as target: target.write(program)
    command = ['clang', '-O2', '-std=c11', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(binary)]
    compiled = subprocess.run(command, capture_output=True, text=True)
    assert compiled.returncode == 0 and not compiled.stderr, compiled.stderr
    proc = subprocess.run([str(binary)], capture_output=True, text=True)
    assert proc.returncode == 0 and not proc.stderr
    assert proc.stdout == 'PARSER_ONLY_PASS cases=16394\n'
    with (out/'parser_stdout.txt').open('x') as target: target.write(proc.stdout)
    return dict(cases=16394, actual_extracted_parser=True, capture_ELF_executed=False,
        source_sha256=digest(source), stdout_sha256=digest(out/'parser_stdout.txt'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(); root, out = args.root.resolve(), args.output_dir.resolve()
    assert not out.exists()
    for name, sha in LOCKS.items(): assert digest(root/name) == sha, name
    source, code = source_equivalence(root), machine_code(root)
    out.mkdir(parents=True); unit = parser_test(root, out)
    report = dict(experiment='h1706_reserved_pc_static_audit', status='PASS_STATIC_PARSER_ONLY_CAPTURE_UNEXECUTED',
        source_delta=source, machine_code=code, portable_parser_test=unit,
        capture_build='gcc -O2 -std=c11 -Wall -Wextra -Werror -fno-builtin',
        observed_compiler='gcc (Debian 12.2.0-14+deb12u1) 12.2.0',
        remote_build_directory='/root/fsincos-h1706-reserved-pc-build',
        proposed_scope='All exceptions masked, pending0; pc01 vs standard PCs on genuinely fresh operands. No bank exists yet.',
        hypothesis='PC01 may or may not agree with PC64; no physical equivalence is asserted by parser acceptance.',
        hardware_execution='none', manifest_frozen=False, labels_opened=False,
        private_ledger_access='none', candidate_default_or_paper_change=False,
        remaining=['Fresh domain-discriminating bank and independent fixed predictions',
            'Public/private/generated-history freshness and tuple audit',
            'Immutable freeze and guarded one-shot runner', 'Hardware prestate acceptance and outcomes'],
        sha256=dict(script=digest(Path(__file__)), evidence=LOCKS))
    save(out/'report.json', report)
    print(json.dumps(dict(status=report['status'], parser=unit, sites=code['sites']), sort_keys=True), flush=True)


if __name__ == '__main__': main()

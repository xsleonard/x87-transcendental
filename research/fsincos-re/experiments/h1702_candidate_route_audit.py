#!/usr/bin/env python3
"""Configured candidate route and rounding-history dependency audit.

Clang parses the exact prior candidate source; a small conservative walker
prunes constant branches and unconditional returns. Two legacy tiny calls
are excluded by separately stated/proved H1700/H1701 route invariants.
This is not a general C verifier, runtime memory proof or silicon proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from collections import Counter, deque
from pathlib import Path
import z3
import cvc5
import h1638_tiny_c_transfer as candidate
from h1700_exact_reduction_certificate import solve
from h1640_remaining_scope_freshness import save
from h1665_small_denormal_provenance import digest

LOCKS = {
    'src/fsincos_skylake.c': '0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b',
    'src/ia64_sf.h': 'a5e9d085f2607cbc43fecbadcce3cebf57620fb07d9509627ce2d27164d7758d',
    'src/p5_rom_constants.h': '2189e0063c913ee4004e09c8b80cb17afb16c95715ea579854e152088bbfce97',
    'experiments/h1630_shared_polynomial.h': '5c279565bf3ab5b1a02d92a24fb2e40dc3b12ab23498522768118890cf5c5310',
    'experiments/h1633_shared_table.h': '238ee52346049bbb292cb43958c01f8f1ddae20e4d3fad004bf74423f6dae66b',
    'experiments/h1638_tiny_closed_form.h': '910cbb03c7310ad86b77bce4ae64fd611d96374c794df0048922b7dc2f199227',
    'experiments/h1638_tiny_c_transfer.py': 'db99dc020ab7372af7f8018a11c4e81a7c73afd227c4dccbbcc080d3b38a4fd1',
    'experiments/h1633_shared_table_audit.py': '3f23458fff3cc1b4965215554874eb011d53283ab18c93a6fa8fce933bbf864b',
    'experiments/h1630_shared_polynomial_audit.py': '706a7ed6a2556cb8aa03ca9c7842ece37d70f99f0cbe01479eb9e76e58828834',
    'experiments/h1700_exact_reduction_certificate.py': 'ac6ece113c44b2dc6d172a0eaacb9082c61e09c68d44dbef2b8e71902a9d0802',
    'tmp/ledger33/current/h1700_exact_reduction_certificate/report.json': 'bd2f4b8d2a5449058b67feb827fcfa19392470ff8d9d0f5de3ca003dbe1f4b3a',
    'tmp/ledger33/current/h1701_conversion_certificate/report.json': 'f1ac755d778a09c46ab076bdcf1c7c99591157c318136d111ba06b32b690200c',
}
SOURCE_SHA = '7c1eda2a245b9da3f4c24fa1abb06b8d929a24059909795b2303aa3bc9a22a4a'
ALLOWED = set('''fsin_ref fcos_ref h1638_tiny_entry x87_invalid_encoding
sf_from_parts sf_zero sf_abs sf_lt sf_lt_abs fsincos_compat_reduce_n_exact
sky_reduce_rc sf_qnan sf_to_x87 sincos_core sf_is_zero
fsincos_compat_operation_class_core wv_from_rc u128_width
fsin_operation_class_polynomial h1630_polynomial h1630_literal h1630_mul
h1630_add h1630_chain p5_wv_mul_round acc_add_product u128_mul_full acc_add
acc_round_bits_mode acc_round64_rc fsin_operation_class_table h1633_table
h1633_mul_rn64 h1633_horner4 r84_lookup'''.split())
# The SDK assert macro uses __builtin_expect(!(e),0); it is a branch hint,
# not another numerical datapath. The first audit retained it as unexpected
# until its origin in the actual SDK assert.h was checked.
EXTERNAL = {'fprintf', '__assert_rtn', '__builtin_clzll', '__builtin_expect'}
SEMANTIC_EXCLUSIONS = {'p5_fsin_standalone_tiny', 'fsin_operation_class_tiny_residual'}


def route_queries():
    xt, rt, phase = z3.Ints('input_top residual_top phase')
    reduced, correction = z3.Bools('reduced correction_nonzero')
    domain = [xt >= -16445, xt <= 62, phase >= 0, phase <= 1,
        z3.Implies(z3.Not(reduced), z3.And(xt <= -1, rt == xt, z3.Not(correction))),
        z3.Implies(reduced, z3.And(xt >= -1, rt >= -65, rt <= -1)),
        z3.Implies(correction, rt == -1)]
    hit = z3.If(reduced, z3.And(z3.Not(correction), rt < -32), xt < -32)
    after = domain + [z3.Not(hit)]
    yield 'tiny_override_iff_tiny', domain, hit != (rt < -32), 'UNSAT'
    yield 'no_legacy_residual_tiny', after, rt < -32, 'UNSAT'
    yield 'no_legacy_direct_sine_tiny', after, z3.And(z3.Not(reduced), phase == 0, xt < -32), 'UNSAT'
    yield 'no_legacy_direct_cosine_bypass', after, z3.And(z3.Not(reduced), phase == 1, xt < -68), 'UNSAT'
    yield 'reduced_tiny_has_no_correction', domain + [reduced, rt < -32], correction, 'UNSAT'
    polynomial = z3.And(rt >= -32, rt <= -3)
    table = z3.And(rt >= -2, rt <= -1)
    yield 'remaining_route_total', after, z3.Not(z3.Or(polynomial, table)), 'UNSAT'
    yield 'remaining_routes_disjoint', domain, z3.And(polynomial, table), 'UNSAT'
    # These are nonempty negative controls, not assertions that such inputs
    # evade the actual enabled tiny override.
    yield 'NEGATIVE_disabled_tiny_reaches_legacy', domain, rt < -32, 'SAT'
    # Without the reduction contract's c=>top=-1 invariant, the tiny header
    # could decline a tiny value because its correction is nonzero.
    weak = domain[:-1]
    yield 'NEGATIVE_missing_correction_invariant', weak, z3.And(rt < -32, z3.Not(hit)), 'SAT'


def constant(node, env):
    kind, inner = node.get('kind'), node.get('inner', [])
    if kind in ('IntegerLiteral', 'CharacterLiteral'):
        return int(node['value'])
    if kind in ('ImplicitCastExpr', 'ParenExpr', 'CStyleCastExpr', 'ConstantExpr') and len(inner) == 1:
        return constant(inner[0], env)
    if kind == 'DeclRefExpr':
        ref = node.get('referencedDecl', {})
        # Bind variables by declaration identity: a local shadow must not
        # accidentally inherit a constant from a global or formal parameter.
        if ref.get('kind') in ('VarDecl', 'ParmVarDecl'):
            return env.get(ref.get('id'))
        return env.get(ref.get('name'))
    if kind == 'UnaryOperator' and len(inner) == 1:
        v = constant(inner[0], env)
        if v is None: return None
        return {'!': lambda: int(not v), '-': lambda: -v, '+': lambda: v, '~': lambda: ~v}.get(node['opcode'], lambda: None)()
    if kind == 'BinaryOperator' and len(inner) == 2:
        a, b = (constant(n, env) for n in inner); op = node['opcode']
        if op == '&&' and (a == 0 or b == 0): return 0
        if op == '||' and ((a is not None and a != 0) or (b is not None and b != 0)): return 1
        if a is None or b is None: return None
        operations = {'&&': lambda: int(bool(a) and bool(b)), '||': lambda: int(bool(a) or bool(b)),
            '==': lambda: int(a == b), '!=': lambda: int(a != b), '<': lambda: int(a < b),
            '>': lambda: int(a > b), '<=': lambda: int(a <= b), '>=': lambda: int(a >= b),
            '&': lambda: a & b, '|': lambda: a | b, '^': lambda: a ^ b,
            '+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b}
        return operations.get(op, lambda: None)()
    return None


def canonical(node):
    # Exclude process-specific AST ids, locations and declaration addresses.
    out = {k: node[k] for k in ('kind', 'name', 'opcode', 'value', 'castKind', 'valueCategory') if k in node}
    if 'type' in node: out['type'] = node['type'].get('qualType')
    if 'referencedDecl' in node:
        ref = node['referencedDecl']; out['reference'] = {k: ref[k] for k in ('kind', 'name') if k in ref}
    if 'inner' in node: out['inner'] = [canonical(n) for n in node['inner']]
    return out


def parse(root, source, polynomial):
    args = ['clang', '-std=c11', '-DG_ROUND84=0', '-DG_H1630_POLYNOMIAL='+str(polynomial),
        '-DG_H1633_TABLE=1', '-DG_H1638_TINY=1', '-I', str(root/'src'), '-I', str(root/'experiments'),
        '-Xclang', '-ast-dump=json', '-fsyntax-only', '-x', 'c', '-']
    result = subprocess.run(args, input=source, text=True, capture_output=True)
    assert result.returncode == 0 and not result.stderr, result.stderr
    tree = json.loads(result.stdout); functions = {}; globals_ = {}; enums = {}; variable_ids = {}
    for node in tree['inner']:
        if node.get('kind') == 'EnumDecl':
            last = -1
            for item in node.get('inner', []):
                if item.get('kind') != 'EnumConstantDecl': continue
                known = constant(item['inner'][0], enums) if item.get('inner') else last+1
                if known is not None: enums[item['name']] = known; last = known
        if node.get('kind') == 'VarDecl':
            init = node.get('inner', [])
            name = node['name']; variable_ids[node['id']] = name
            if node.get('init'):
                globals_[name] = constant(init[-1], enums | globals_)
            elif name not in globals_:
                # An extern declaration (e.g. stderr) is not a zero-valued
                # tentative definition. Never invent its runtime value.
                globals_[name] = None if node.get('storageClass') == 'extern' else 0
            globals_[node['id']] = globals_[name]
        if node.get('kind') == 'FunctionDecl' and any(n.get('kind') == 'CompoundStmt' for n in node.get('inner', [])):
            functions[node['name']] = node
    # Earlier forward declarations and later definitions must share the
    # actual initializer, rather than freezing an earlier tentative zero.
    for identity, name in variable_ids.items(): globals_[identity] = globals_[name]
    return functions, globals_ | enums


def function_name(node):
    if node.get('kind') == 'DeclRefExpr' and node.get('referencedDecl', {}).get('kind') == 'FunctionDecl':
        return node['referencedDecl']['name']
    inner = node.get('inner', [])
    if len(inner) == 1: return function_name(inner[0])
    return None


def audit(functions, globals_, phase):
    assert globals_['g_round84_errata'] == 0
    for name in ('g_round63_invalid_encoding', 'g_round50_fsin_operation_classes', 'g_round53_fcos_operation_classes'):
        assert globals_[name] == 1, (name, globals_.get(name))
    globals_ = dict(globals_)
    # Their exact declaration ids are in the function references. All other
    # global initializers remain fixed by the configured candidate contract.
    overrides = {'g_fsin_standalone_path': int(not phase), 'g_fcos_standalone_path': phase}
    def override_ids(node):
        ref = node.get('referencedDecl', {})
        if ref.get('kind') == 'VarDecl' and ref.get('name') in overrides:
            globals_[ref['id']] = overrides[ref['name']]
        for child in node.get('inner', []): override_ids(child)
    for node in functions.values(): override_ids(node)
    globals_.update(overrides)
    root = 'fcos_ref' if phase else 'fsin_ref'
    pending = deque([(root, (None, None, None))]); visited = set()
    edges, excluded, fields, unsupported, branches = [], [], [], [], []
    def walk(node, env, owner):
        kind, inner = node.get('kind'), node.get('inner', [])
        if kind == 'CompoundStmt':
            for child in inner:
                if not walk(child, env, owner): return False
            return True
        if kind == 'IfStmt':
            assert len(inner) in (2, 3)
            walk(inner[0], env, owner); truth = constant(inner[0], env)
            if truth is not None:
                branches.append(dict(function=owner, value=int(bool(truth))))
                return walk(inner[1], env, owner) if truth else (walk(inner[2], env, owner) if len(inner) == 3 else True)
            left = walk(inner[1], env, owner)
            right = walk(inner[2], env, owner) if len(inner) == 3 else True
            return left or right
        if kind == 'CallExpr':
            name = function_name(inner[0])
            if name is None:
                unsupported.append(dict(function=owner, kind='indirect_call'))
            else:
                args = tuple(constant(n, env) for n in inner[1:])
                edge = dict(caller=owner, callee=name, arguments=args)
                if owner == 'fsincos_compat_operation_class_core' and name in SEMANTIC_EXCLUSIONS:
                    excluded.append(edge)
                else:
                    edges.append(edge)
                    if name in functions: pending.append((name, args))
            for n in inner[1:]: walk(n, env, owner)
            return True
        if kind == 'MemberExpr' and node.get('name') == 'rh':
            fields.append(dict(function=owner, category=node.get('valueCategory')))
        if kind in ('GotoStmt', 'IndirectGotoStmt', 'SwitchStmt'):
            # Do not silently reason past control flow unsupported by this
            # small constant-branch walker. Current reachable helpers use ifs.
            unsupported.append(dict(function=owner, kind=kind))
        for child in inner: walk(child, env, owner)
        return kind != 'ReturnStmt'
    while pending:
        name, arguments = pending.popleft(); key = (name, arguments)
        if key in visited: continue
        visited.add(key); node = functions[name]
        params = [n['id'] for n in node['inner'] if n.get('kind') == 'ParmVarDecl']
        assert len(params) == len(arguments), name
        env = globals_ | dict(zip(params, arguments))
        body = next(n for n in node['inner'] if n.get('kind') == 'CompoundStmt')
        walk(body, env, name)
    names = sorted({name for name, _ in visited})
    external = sorted({row['callee'] for row in edges} - functions.keys())
    signatures = {name: hashlib.sha256(json.dumps(canonical(functions[name]), sort_keys=True).encode()).hexdigest() for name in names}
    return dict(instruction=root, functions=names, contexts=len(visited), edges=edges,
        semantically_excluded_calls=excluded, rh_member_expressions=fields, unsupported_control_flow=unsupported,
        external_functions=external, unexpected_functions=sorted(set(names)-ALLOWED),
        unexpected_external=sorted(set(external)-EXTERNAL), constant_branches=branches,
        normalized_ast_sha256=signatures,
        configuration={name: globals_[name] for name in ('g_round84_errata', 'g_round63_invalid_encoding',
            'g_round50_fsin_operation_classes', 'g_round53_fcos_operation_classes',
            'g_fsin_standalone_path', 'g_fcos_standalone_path', 'g_dump_internals')})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path); p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root, out = a.root.resolve(), a.output_dir.resolve(); assert not out.exists()
    for name, expected in LOCKS.items(): assert digest(root/name) == expected, name
    source = candidate.source_string(root); assert hashlib.sha256(source.encode()).hexdigest() == SOURCE_SHA
    out.mkdir(parents=True); queries = out/'queries'; queries.mkdir(); results = []
    for name, domain, error, wanted in route_queries():
        row = solve(name, 'QF_LIA', domain, error, queries, 10000); row['expected'] = wanted; results.append(row)
    save(out/'solver_results.json', results)
    functions, globals_ = parse(root, source, 1)
    audits = [audit(functions, globals_, phase) for phase in (0, 1)]
    save(out/'candidate_callgraph.json', audits)
    for row in audits:
        save(out/(row['instruction']+'_ast.json'), {name: canonical(functions[name]) for name in row['functions']})
    del functions
    functions, globals_ = parse(root, source, 0)
    disabled = [audit(functions, globals_, phase) for phase in (0, 1)]
    save(out/'NEGATIVE_disabled_polynomial_callgraph.json', disabled)
    proved = all(r['z3'] == r['cvc5'] == r['expected'] for r in results)
    clean = all(not any(r[k] for k in ('unexpected_functions', 'unexpected_external', 'rh_member_expressions', 'unsupported_control_flow')) for r in audits)
    rejected = all(r['unexpected_functions'] for r in disabled)
    report = dict(experiment='h1702_candidate_route_audit', status='PASS_CONDITIONAL_ROUTE_AUDIT' if proved and clean and rejected else 'UNRESOLVED_OR_FAILED',
        solvers=dict(z3=z3.get_version_string(), cvc5=cvc5.__version__),
        solver_counts=dict(z3=dict(Counter(r['z3'] for r in results)), cvc5=dict(Counter(r['cvc5'] for r in results))),
        candidate_summary=[{k:r[k] for k in ('instruction','functions','contexts','rh_member_expressions','unexpected_functions','unexpected_external','unsupported_control_flow','configuration')} for r in audits],
        negative_disabled_polynomial=[dict(instruction=r['instruction'], unexpected_functions=r['unexpected_functions']) for r in disabled],
        source_sha256=SOURCE_SHA, clang=subprocess.run(['clang','--version'],text=True,capture_output=True,check=True).stdout,
        trust_boundary='Clang AST plus this reviewed limited walker, manual semantic H1700/H1701 route invariants, fixed standalone configuration and successful assertion/I/O behavior. Not a general C verifier, automatic memory-initialization/compiler proof, all-state contract or universal silicon proof.',
        semantic_exclusions='The entry tiny override consumes every nonzero finite tiny residual. H1700 gives residual!=0 and correction!=0 only at residual_top=-1. After override declines, both direct early tiny and residual-tiny legacy calls are unreachable. Special/zero/range and invalid gates precede finite operation-class evaluation.',
        metadata_scope='No .rh member expression occurs in the conservatively reachable numerical helper bodies after stated exclusions. wv_from_rc still leaves rh uninitialized; this does not establish absence of arbitrary padding/ABI reads or every C/compiler memory issue.',
        hardware_execution='none', private_ledger_access='none', labels_opened=False, production_default_or_paper_change=False,
        sha256=dict(script=digest(Path(__file__)), evidence=LOCKS, solver_results=digest(out/'solver_results.json'),
            callgraph=digest(out/'candidate_callgraph.json')))
    save(out/'report.json', report)
    print(json.dumps({k:report[k] for k in ('status','solver_counts','candidate_summary','negative_disabled_polynomial')}), flush=True)


if __name__ == '__main__': main()

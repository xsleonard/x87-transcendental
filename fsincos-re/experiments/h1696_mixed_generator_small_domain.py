#!/usr/bin/env python3
"""Replay documented mixed-generator history without capture or input files.

The original pinned Python generator executes with its file writer replaced
by an in-memory counting/hash sink and imports restricted to isolated random
and argv objects. No old shell runner executes. Generated absence is not raw
hardware verification, original-runtime proof or global freshness clearance.
"""
from __future__ import annotations
import argparse
import ast
import builtins
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from h1640_remaining_scope_freshness import save
from h1665_small_denormal_provenance import digest

LOCKS = {
    'experiments/h727_gen.py': '3a8056ca54e05ecdabdc6116ed5b86761fe464d135a1b55085f4b7c70e7c3374',
    'experiments/h773_gen.py': 'ba975e4de26b99641d7fc0b2f403c21efea920931e5fe650446c16c60c7a33fa',
    'experiments/h733_gen.py': 'cf76aa0e9adc30814d28a9f472d7d55ac54730f5863a7a7f60d64eea51352ffa',
    'experiments/r84_misses.tsv': 'e49222bd5499a26f02ab82cb4c59c094e15e33868a57cda6951e4fa15263c876',
    'tmp/ledger33/current/h1688_generated_small_operand_provenance/historically_reported_reservations.json': '79d3012fc501ec64329a7cd9974b6428d0102b911d594cb8a84fb4e49b92d3a1',
}
CAMPAIGNS = (
    ('randv1', 0x662662, 8_000_000, ('rn', 'rd', 'ru')),
    ('rv2', 0x773001, 8_000_000, ('rn', 'rd', 'ru')),
    ('rv3', 0x8623f4, 2_000_000, ('rn', 'rd', 'ru', 'rz')),
    ('rv4', 0x8725, 2_000_000, ('rn', 'rd', 'ru', 'rz')),
    ('rv5', 0x8726, 2_000_000, ('rn', 'rd', 'ru', 'rz')),
    ('rv6', 0x8727, 2_000_000, ('rn', 'rd', 'ru', 'rz')),
)
# Public historical statements, not instruction output labels.
HISTORY = (
    'RANDV1: 8M blind random operands (h727_gen.py, seed 0x662662;',
    'rv2_inputs.txt (8M, seed 0x773001, h727',
    'H780 (h773 completed): rv2 captured, FCOS+FSIN x rn/rd/ru.',
    'TASK-4 discipline).  rv3 = h727_gen.py fresh seed 0x8623f4, 2M',
    'rv4 (seed 0x8725, 2M x 8, epoch-probed 43/43 both sides)',
    'rv5 blind vs locked ecc63ce (seed 0x8726, 2M x 8, epoch-probed',
    'CORPUS: rv6 = h727 gen seed 0x8727, 2M operands x {cos,sin} x',
    'rv6 BLIND (vs locked a65895e;',
)


def prepared(source, seed, count):
    """Only seed, row count and the writer's name are configurable."""
    tree = ast.parse(source)
    edits = Counter()
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
                if (call.func.value.id, call.func.attr) == ('random', 'seed'):
                    call.args = [ast.Constant(seed)]; edits['seed'] += 1
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == 'N':
                node.value = ast.Constant(count); edits['count'] += 1
            elif node.targets[0].id == 'w':
                assert isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                assert node.value.func.id == 'open' and len(node.value.args) == 2
                assert isinstance(node.value.args[1], ast.Constant) and node.value.args[1].value == 'w'
                node.value.args[0] = ast.Constant('IN_MEMORY_ONLY'); edits['writer'] += 1
    assert edits == dict(seed=1, count=1, writer=1), edits
    ast.fix_missing_locations(tree)
    return tree


def anchor_rows(root):
    anchors = {}
    for line in (root / 'experiments/r84_misses.tsv').read_text().splitlines():
        fields = line.split('\t')
        if fields[0] != 'randv1':
            continue
        index, op = int(fields[3]), ' '.join(fields[4:6])
        assert index not in anchors or anchors[index] == op
        anchors[index] = op
    assert len(anchors) > 10
    return anchors


class Sink:
    def __init__(self, name, count, anchors):
        self.name, self.expected = name, count
        self.count = 0; self.closed = False; self.hash = hashlib.sha256()
        self.kinds = Counter(); self.small = []; self.minimum_denormal = None
        self.anchor_indices = {i + d for i in anchors for d in (-1, 0, 1)}
        self.anchor_neighborhood = {}; self.inf_counts = Counter(); self.first_inf = {}

    def write(self, text):
        assert not self.closed and len(text) == 22 and text[4] == ' ' and text[-1] == '\n'
        se, sig = int(text[:4], 16), int(text[5:21], 16)
        assert 0 <= se < 65536 and 0 <= sig < 1 << 64
        op, e = text[:-1], se & 0x7fff
        self.hash.update(text.encode('ascii'))
        if self.count in self.anchor_indices:
            self.anchor_neighborhood[self.count] = op
        if e == 0:
            if sig == 0:
                kind = 'zero'
            elif sig < 1 << 63:
                kind = 'true_denormal'
                self.minimum_denormal = sig if self.minimum_denormal is None else min(sig, self.minimum_denormal)
                if sig <= 15:
                    self.small.append(dict(index_zero_based=self.count, operand=op))
            else:
                kind = 'pseudo_denormal'
        elif e == 0x7fff:
            kind = 'infinity' if sig == 1 << 63 else 'NaN'
            if kind == 'infinity':
                self.inf_counts[op] += 1; self.first_inf.setdefault(op, self.count)
        else:
            kind = 'finite_normal'
        self.kinds[kind] += 1; self.count += 1
        if self.count % 2_000_000 == 0:
            print(json.dumps(dict(campaign=self.name, generated_rows=self.count)), flush=True)
        return len(text)

    def close(self):
        assert not self.closed; self.closed = True

    def report(self, seed, modes, anchors):
        assert self.closed and self.count == self.expected
        assert sum(self.kinds.values()) == self.expected
        # Check a single consistent indexing convention, never a per-row fit.
        offsets = [d for d in (-1, 0, 1) if anchors and all(
            self.anchor_neighborhood.get(i + d) == op for i, op in anchors.items())]
        if anchors:
            assert len(offsets) == 1, 'Indexed historical operands do not replay'
        return dict(campaign=self.name, seed=hex(seed), generated_rows=self.count,
            generated_stream_sha256=self.hash.hexdigest(), class_counts=dict(self.kinds),
            smallest_true_denormal_significand=None if self.minimum_denormal is None else str(self.minimum_denormal),
            small_denormal_occurrences=self.small, zero_occurrences=self.kinds['zero'],
            infinity_occurrences=dict(self.inf_counts), first_infinity_input_indices=self.first_inf,
            reported_instructions=['fsin', 'fcos'], reported_RC=list(modes),
            original_PC_masks_and_prestates='not authenticated; unknown PC reserves all PC',
            indexed_public_operand_anchor_count=len(anchors), index_offsets_that_match_all_anchors=offsets,
            raw_output_status_credit=0, generator_role='Software replay of reported history, not fresh observation')


def execute(source, seed, count, sink):
    state = random.Random()
    sys_proxy = SimpleNamespace(argv=['h773_gen.py', hex(seed), 'IN_MEMORY_ONLY'])
    def import_only(name, *args, **kwargs):
        if name == 'random': return state
        if name == 'sys': return sys_proxy
        raise AssertionError('Unexpected generator import')
    opens = []
    def open_only(name, mode):
        assert not opens and name == 'IN_MEMORY_ONLY' and mode == 'w'
        opens.append(name); return sink
    safe = {name: getattr(builtins, name) for name in ('int', 'len', 'range', 'tuple')}
    safe.update(__import__=import_only, open=open_only, print=lambda *a, **k: None)
    namespace = {'__builtins__': safe}
    exec(compile(prepared(source, seed, count), '<pinned-generator-in-memory>', 'exec'), namespace)
    assert opens == ['IN_MEMORY_ONLY']


def structural_contract(root):
    source = (root / 'experiments/h733_gen.py').read_text()
    tree = ast.parse(source)
    loop = next(n for n in tree.body if isinstance(n, ast.For))
    # These exact assignments bound E on every path through this small body.
    writes = [ast.unparse(n) for n in ast.walk(loop) if isinstance(n, (ast.Assign, ast.AugAssign))
              and ((isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'se' for t in n.targets))
                   or (isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id == 'se'))]
    assert writes == ['se = random.randrange(16387, 16446)', 'se |= 32768'], writes
    # The OR changes sign only. Every possible unsigned exponent is nonzero,
    # nonspecial, and well above the tiny domain, independently of RNG/seed/N.
    for e in range(0x4003, 0x403e):
        for sign in (0, 0x8000):
            assert (e | sign) & 0x7fff == e and 0 < e < 0x7fff
    return dict(generator='h733_gen.py', unsigned_exponent_interval_inclusive=['4003', '403d'],
        proof='Only assignment selects E in [0x4003,0x403e); later update ORs sign only. Therefore no E=0 or E=0x7fff on any generated path, for all seeds and row counts.',
        excludes=['true_denormal', 'pseudo_denormal', 'zero', 'infinity', 'NaN'],
        scope='Pinned h733 generator, not arbitrary modified generators or all capture history')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(); root, out = args.root.resolve(), args.output_dir.resolve()
    assert not out.exists()
    for name, expected in LOCKS.items(): assert digest(root / name) == expected, name
    history = (root / 'notes/HANDOFF-collision-gate.md').read_text()
    assert all(fragment in history for fragment in HISTORY)
    a = (root / 'experiments/h727_gen.py').read_text()
    b = (root / 'experiments/h773_gen.py').read_text()
    # The parameterized copy adds only an import of sys; the operative bodies
    # are AST-identical after the documented seed/N/writer substitutions.
    ta, tb = prepared(a, 123, 4), prepared(b, 123, 4)
    tb.body = [n for n in tb.body if not (isinstance(n, ast.Import) and [x.name for x in n.names] == ['sys'])]
    assert ast.dump(ta) == ast.dump(tb)
    anchors = anchor_rows(root); rows = []
    out.mkdir(parents=True)
    for name, seed, count, modes in CAMPAIGNS:
        selected = anchors if name == 'randv1' else {}
        sink = Sink(name, count, selected)
        execute(a if name == 'randv1' else b, seed, count, sink)
        row = sink.report(seed, modes, selected)
        save(out / (name + '.json'), row); rows.append(row)
        print(json.dumps(dict(campaign=name, complete=True, small_occurrences=len(sink.small),
            zeros=sink.kinds['zero'], infinity_occurrences=sum(sink.inf_counts.values()))), flush=True)
    aggregate = Counter()
    for row in rows: aggregate.update(row['class_counts'])
    report = dict(experiment='h1696_mixed_generator_small_domain', status='BOUNDED_GENERATOR_HISTORY_REPLAY_COMPLETE',
        generated_rows=sum(r['generated_rows'] for r in rows), campaigns=len(rows), class_counts=dict(aggregate),
        small_denormal_occurrences=sum(len(r['small_denormal_occurrences']) for r in rows),
        indexed_randv1_anchors=len(anchors), h727_h773_operational_AST_equal=True,
        all_seed_h733_contract=structural_contract(root), historical_public_fragments=list(HISTORY),
        software_runtime=sys.version, hardware_execution='none', new_labels_opened=False,
        manifest_frozen=False, freshness_clearance=False, private_ledger_access='none',
        production_default_or_paper_change=False,
        limits='Replay uses the pinned generator and current Python RNG. Indexed randv1 operands anchor its history; full original generated streams/runtime and raw captures are not independently authenticated here. This closes these source/seed replay questions, not all public/private generators or global freshness. H1688 reservations remain in force. H939 uses filtered candidates, not 100M hardware inputs, and is not replayed here.',
        sha256=dict(script=digest(Path(__file__)), evidence=LOCKS,
            campaigns={p.name: digest(p) for p in sorted(out.iterdir())}))
    save(out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'generated_rows', 'campaigns', 'small_denormal_occurrences', 'indexed_randv1_anchors')}), flush=True)


if __name__ == '__main__':
    main()

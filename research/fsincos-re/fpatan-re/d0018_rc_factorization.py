"""Can separate architectural RC entry paths rescue the tested families?

Unlike prior all-mode screens, each program is tested independently in RN,
RD, RU and RZ. A different fixed program may serve each architectural mode;
there is still no per-operand selection. This is a necessary discovery test
for an RC-conditioned algorithm, not permission to promote one from a small
frontier. Any survivor must next pass all saved observations in its mode.
"""
import collections
import hashlib
import json
from d0010_causal_intervals import BASE, restore
from d0015_internal_rc_audit import kernel as rc_kernel
from d0017_signed_truncation_audit import kernel as signed_kernel
from d0017_residual_state_audit import kernel as residual_kernel
from graph_v5 import prevalue
from model import encode, value
from prepare import save

FAMILIES = (
    ('internal-rc', 'd0015-internal-rc-audit.json', rc_kernel,
     ('square_read', 'square', 'horner_product', 'horner_add', 'horner_scope', 'tail_first', 'tail_last', 'tail_z_read', 'tail_order')),
    ('signed', 'd0017-signed-truncation-audit.json', signed_kernel,
     ('square_read', 'square', 'horner_multiply', 'horner_add', 'horner_scope', 'tail_first', 'tail_last', 'tail_z_read', 'tail_order')),
    ('residual', 'd0017-residual-state-audit.json', residual_kernel,
     ('square_format', 'residual_format', 'square_residual', 'product_residual', 'add_residual',
      'first_residual', 'last_residual', 'zread', 'read_residual', 'tail_order', 'merge')),
)


def main():
    data = collections.defaultdict(list)
    for pair in json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs']:
        t = {}
        prevalue(*pair['raw'], trace=t)
        if t['kind'] == 'direct':
            for row in pair['rows']:
                data[row['rc']].append((pair, t, row))
    reports = []
    for name, filename, kernel, keys in FAMILIES:
        source = BASE / filename
        records = json.loads(source.read_text())['results']
        survivors = {rc: [] for rc in ('rn', 'rd', 'ru', 'rz')}
        rejection_counts = {rc: collections.Counter() for rc in survivors}
        results = []
        for index, item in enumerate(records):
            recipe = item['recipe']
            arguments = [recipe[k] for k in keys]
            outcomes = {}
            for rc, rows in data.items():
                failure = None
                for ordinal, (pair, t, row) in enumerate(rows):
                    if name == 'internal-rc':
                        internal = rc
                        if recipe['rc_source'] == 'sign-reflected' and pair['raw'][0] & 32768:
                            internal = {'rd': 'ru', 'ru': 'rd'}.get(internal, internal)
                        k = kernel(t['z'], internal, *arguments)
                    else:
                        k = kernel(t['z'], *arguments)
                    v = restore(k, t, pair['raw'])
                    se, sig = encode(v, rc)
                    c1 = int(abs(value(se, sig)) > abs(v))
                    if (se, sig, c1) != (row['se'], row['sig'], row['C1']):
                        failure = dict(input=row['input'], predicted=[se, sig, c1], observed=[row['se'], row['sig'], row['C1']])
                        rejection_counts[rc][row['input']] += 1
                        break
                outcomes[rc] = dict(tested_rows=ordinal + 1, counterexample=failure)
                if failure is None:
                    survivors[rc].append(dict(program_index=index, recipe=recipe))
            results.append(dict(program_index=index, modes=outcomes))
            if (index + 1) % 10000 == 0:
                print(name, index + 1, 'programs;', {rc: len(v) for rc, v in survivors.items()}, flush=True)
        report = dict(family=name, source=filename, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                      programs=len(records), mode_rows={rc: len(v) for rc, v in data.items()},
                      survivors=survivors, rejected_by_input={rc: dict(v) for rc, v in rejection_counts.items()},
                      results=results, hardware_executed=False, numerical_model_promoted=False)
        save(BASE / f'd0018-rc-factorization-{name}.json', report)
        reports.append(dict(family=name, programs=len(records), survivors={rc: len(v) for rc, v in survivors.items()}))
        print('COMPLETE', name, reports[-1]['survivors'], flush=True)
    save(BASE / 'd0018-rc-factorization-summary.json', dict(status='PER_ARCHITECTURAL_MODE_DISCOVERY_AUDIT',
         families=reports, hardware_executed=False, numerical_model_promoted=False))


if __name__ == '__main__':
    main()

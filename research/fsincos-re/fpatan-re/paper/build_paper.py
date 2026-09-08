"""Mechanically synchronize paper exhibits, compile, and render for review.

The manuscript and Markdown pseudocode are the authoring sources. Generated
listings, numeric exhibits and constant rows must not be hand-edited. This
builder checks their supporting local evidence before regenerating them.
No model change, historical-record rewrite or hardware capture is performed.
"""
import argparse
import ast
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
FPATAN = HERE.parent
REPO = FPATAN.parent.parent
BASE = FPATAN.parent / 'tmp/fpatan-re'
sys.path.insert(0, str(FPATAN))
from compressed_guard import digest


def number(value):
    return f'{value:,}'.replace(',', '{,}')


def prepare():
    delivery = json.loads((BASE / 'd0027-delivery-checks.json').read_text())
    style = json.loads((BASE / 'd0029-style-verification.json').read_text())
    replay = json.loads((BASE / 'd0030-pseudocode-replay-v2.json').read_text())
    assert delivery['status'] == style['status'] == replay['status'] == 'PASS'
    assert replay['pseudocode_sha256'] == digest(FPATAN / 'PSEUDOCODE.md')
    assert style['after_sha256'] == digest(FPATAN / 'fpatan_candidate.c')
    assert replay['counts']['rows'] == delivery['observations'] == 2783208
    assert all(v == 0 for k, v in replay['counts'].items() if k != 'rows')
    assert len(replay['jobs']) == 14
    generated = HERE / 'generated'
    generated.mkdir(exist_ok=True)
    inventory = delivery['inventory']
    assert set(replay['rounding_modes'].values()) == {695802}
    assert {str(pc): inventory[f'pc-{pc}'] for pc in (24, 53, 64)} == replay['precision_controls']
    values = dict(CorpusRows=delivery['observations'],
                  ProspectiveRows=delivery['prospective_observations'],
                  RowsPerMode=695802, PCtwentyfour=inventory['pc-24'],
                  PCfiftythree=inventory['pc-53'], PCsixtyfour=inventory['pc-64'],
                  FinalChallengeRows=replay['jobs']['d0026']['counts']['rows'])
    (generated / 'evidence-numbers.tex').write_text(
        '% Generated from authenticated evidence; do not hand-edit.\n' +
        ''.join(f'\\newcommand{{\\{key}}}{{{number(value)}}}\n' for key, value in values.items()))
    prior = sum(v['counts']['rows'] for k, v in replay['jobs'].items()
                if k not in ('d0023', 'd0024', 'd0026'))
    assert prior + delivery['prospective_observations'] == delivery['observations']
    rows = [(r'Earlier eleven campaigns', prior, 'Discovery/regression'),
            ('D0023: exact midpoints', 194808, 'Prospective V7'),
            ('D0024: denominator low bits', 66248, 'Prospective V7'),
            ('D0026: final-rounding boundaries', 363256, 'Prospective V7')]
    (generated / 'campaign-table.tex').write_text(
        '% Generated; observation counts are not unconditioned pair counts.\n'
        '\\begin{tabular}{@{}lrl@{}}\n\\toprule\n'
        'Evidence set & Observations & Role for the final graph \\\\\n\\midrule\n' +
        ''.join(f'{name} & {number(count)} & {role} \\\\\n' for name, count, role in rows) +
        '\\midrule\n' + f'Total & {number(delivery["observations"])} & Fourteen campaigns \\\\\n' +
        '\\bottomrule\n\\end{tabular}\n')
    source = (FPATAN / 'fpatan_candidate.c').read_text()
    entries = re.findall(r'\{\s*(\d+)\s*,\s*([01])\s*,\s*(-?\d+)\s*,\s*"([0-9a-f]+)"\s*\}', source)
    assert len(entries) == 44
    with (FPATAN.parent / 'data/pentium-rom/rom-constants.tsv').open() as stream:
        rom = {int(r['row']): r for r in csv.DictReader(stream, delimiter='\t')}
    lines = []
    for index, sign, scale, significand in entries:
        row = rom[int(index)]
        assert row['sign'] == sign and row['sig68'] == significand
        assert int(scale) == int(row['exp'], 16) - 0xffff - 66
        if index in ('114', '118', '125'):
            lines.append('\\midrule\n')
        lines.append(f'{index} & {sign} & {scale} & \\texttt{{{significand}}} \\\\\n')
    (generated / 'rom-table.tex').write_text(
        '% Generated from the literal C entries, checked against the public TSV.\n'
        '{\\footnotesize\n\\begin{longtable}{@{}rrrl@{}}\n'
        '\\toprule\nROM row $i$ & Sign $s$ & Scale $q$ & Integer significand $S$ (hex) \\\\\n'
        '\\midrule\n\\endfirsthead\n'
        '\\toprule\nROM row $i$ & Sign $s$ & Scale $q$ & Integer significand $S$ (hex) \\\\\n'
        '\\midrule\n\\endhead\n' + ''.join(lines) +
        '\\bottomrule\n\\end{longtable}\n}\n')
    markdown = (FPATAN / 'PSEUDOCODE.md').read_text()
    sections = re.findall(r'^## (\d+)\. ([^\n]+)\n(.*?)(?=^## |\Z)', markdown, re.M | re.S)
    listings = []
    for index, title, body in sections:
        code = re.findall(r'^```python\n(.*?)^```', body, re.M | re.S)
        assert len(code) == 1
        filename = f'pseudocode-{index}.py'
        (generated / filename).write_text(code[0])
        # Keep whole functions on a page. Group short neighboring definitions,
        # but never split a function just to fill the preceding page.
        tree = ast.parse(code[0])
        chunks = []
        start = 1
        for node in tree.body:
            if node.end_lineno - start + 1 > 24 and node.lineno > start:
                chunks.append((start, node.lineno - 1))
                start = node.lineno
        chunks.append((start, len(code[0].splitlines())))
        fragment = f'\\subsection{{{title}}}\n'
        for first, last in chunks:
            fragment += ('\\par\\noindent\\begin{minipage}{\\linewidth}\n'
                         f'\\lstinputlisting[style=pseudocode,firstline={first},lastline={last}]'
                         f'{{generated/{filename}}}\n'
                         '\\end{minipage}\\par\n')
        listings.append(fragment)
    assert len(listings) == 5
    (generated / 'pseudocode.tex').write_text(
        '% Generated verbatim from PSEUDOCODE.md; do not hand-edit.\n' + ''.join(listings))
    pins = {str(p.relative_to(REPO)): digest(p) for p in
            [FPATAN / 'PSEUDOCODE.md', FPATAN / 'fpatan_candidate.c',
             HERE / 'skylake-fpatan.tex', HERE / 'build_paper.py', HERE / 'verify_pseudocode.py',
             BASE / 'd0027-delivery-checks.json', BASE / 'd0029-style-verification.json',
             BASE / 'd0030-pseudocode-replay-v2.json', *sorted(generated.iterdir())]
            if p.is_file() and p.name != 'SOURCE-MANIFEST.json'}
    (generated / 'SOURCE-MANIFEST.json').write_text(json.dumps(dict(
        status='VERIFIED_DOCUMENT_EXHIBITS', hardware_executed=False, files=pins,
        observations=delivery['observations'], prospective_observations=delivery['prospective_observations']),
        indent=2, sort_keys=True) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args()
    prepare()
    if args.prepare_only:
        print('PASS generated exhibits and source/evidence pins')
        return
    work = REPO / 'tmp/pdfs/fpatan-paper'
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run(['tectonic', '--keep-logs', '--keep-intermediates',
                    '--outdir', str(work), str(HERE / 'skylake-fpatan.tex')], cwd=HERE, check=True)
    log = (work / 'skylake-fpatan.log').read_text()
    bad = [line for line in log.splitlines() if
           re.search(r'Overfull|Underfull|LaTeX Warning|Package .* Warning|^!', line)]
    if bad:
        print('\n'.join(bad))
        raise RuntimeError('Inspect and resolve TeX diagnostics before delivery')
    destination = REPO / 'output/pdf/skylake-fpatan.pdf'
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(work / 'skylake-fpatan.pdf', destination)
    subprocess.run(['pdfinfo', str(destination)], check=True)
    if args.render:
        # A content-addressed prefix keeps older reviewed drafts separate.
        # No intermediate or historical page image is deleted or overwritten.
        prefix = work / ('page-' + digest(destination)[:12])
        subprocess.run(['pdftoppm', '-r', '110', '-png', str(destination),
                        str(prefix)], check=True)
        print('Review images:', str(prefix) + '-*.png')
    print('PDF:', destination)
    print('Rendering must still be visually reviewed before delivery.')


if __name__ == '__main__':
    main()

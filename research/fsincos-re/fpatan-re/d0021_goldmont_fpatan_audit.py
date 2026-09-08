"""Pin a public Goldmont arctangent-shaped graph and test its transfer.

Exact facts: raw operation/register incidence, constant payload projections,
two polynomial banks and their addressed consumers. Hypotheses: architectural
FPATAN identification, sign/exponent/low-bit ROM transfer and numerical opcode
semantics on Skylake. No Goldmont hardware or decoder trace is available.
The numerical interpretation is a candidate; discovery agreement is not proof.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
from d0010_causal_intervals import BASE, observation_interval
from graph_v5 import prevalue as v5
from graph_v6 import kernel, prevalue
from model import F, ROM, cut
from prepare import save

PINS = {
    'listing': '46fb61bfaf174765c117de65b036b73ae4433b9c2b9871d5289fd02d4867067e',
    'rom': '87b9ee93e0c7a1f988906d8fd79d886590aa41a7368d06ef1954be8d5aca14db',
}
URLS = {
    'listing': 'https://github.com/chip-red-pill/uCodeDisasm/blob/ffc9070233a6e7a26dbabe723289259f087ee20b/ucode/ucode_glm.txt',
    'rom': 'https://github.com/pietroborrello/CustomProcessingUnit/blob/4237524fe7545c66e42dd986113f220662c06f6a/bios/dumps/rom.txt',
}


def parse_listing(path):
    sites = {}
    for line in path.read_text().splitlines():
        match = re.match(r'U([0-9a-f]+): ([0-9a-f]{12})\s+(.*)', line)
        if match:
            address, word = int(match[1], 16), int(match[2], 16)
            assert address not in sites
            sites[address] = dict(address=f'{address:04x}', raw=match[2], text=match[3],
                                  opcode=(word >> 32) & 4095, immediate=(word >> 24) & 255,
                                  destination=(word >> 12) & 63, source1=(word >> 6) & 63, source0=word & 63)
    return sites


def run_slice(z, sites, table, exact=False):
    regs = {0x3c if table else 0x3d: z}
    readmap = {k-114+0x12: k for k in range(114, 124)}
    for site in sites:
        op, dest = site['opcode'], site['destination']
        if op == 0x6a0:
            regs[dest] = ROM[readmap[site['immediate']]]
            continue
        # 0x702/0x496 are sign/metadata operations between the table square
        # and fourth-power nodes. The candidate starts with the already
        # signed reduced z; their hardware semantics are NOT asserted here.
        if op in (0x702, 0x496):
            continue
        a, b = regs[site['source0']], regs[site['source1']]
        if op == 0x661:
            result = a * b if exact else cut(a * cut(b, 'chop64'), 'rn64')
        elif op == 0x6e1:
            result = a * b if exact else cut(a * b, 'chop67')
        else:
            assert op in (0x649, 0x6c9)
            result = a + b if exact else cut(a + b, 'rn64' if op == 0x649 else 'chop67')
        regs[dest] = result
    return z + regs[0x3a if table else 0x3c]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--listing', type=Path, required=True)
    ap.add_argument('--rom', type=Path, required=True)
    args = ap.parse_args()
    for name in PINS:
        assert hashlib.sha256(getattr(args, name).read_bytes()).hexdigest() == PINS[name]
    values = [int(v, 16) for v in args.rom.read_text().split()]
    assert len(values) == 512
    p5path = Path(__file__).resolve().parents[1] / 'data/pentium-rom/rom-constants.tsv'
    projections = []
    with p5path.open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            k = int(row['row'])
            if not (114 <= k <= 123 or 125 <= k <= 156):
                continue
            high = int(row['sig68'], 16) >> 3
            expected = k - 114 + 0x12 if k <= 123 else k - 125 + 0xf6
            assert values[expected] == high
            projections.append(dict(p5_row=k, goldmont_row=f'{expected:03x}', high64=f'{high:016x}',
                                    all_equal_payload_rows=[f'{i:03x}' for i, v in enumerate(values) if v == high]))
    parsed = parse_listing(args.listing)
    slices = {name: [v for address, v in parsed.items() if lo <= address <= hi]
              for name, lo, hi in (('long', 0x70ca, 0x70e4), ('short', 0x6d1e, 0x6d32))}
    orders = {name: [v['immediate'] for v in rows if v['opcode'] == 0x6a0] for name, rows in slices.items()}
    assert orders == {'long': [0x1b, 0x1a, 0x19, 0x18, 0x17, 0x16], 'short': [0x14, 0x15, 0x12, 0x13]}
    text = args.listing.read_text()
    assert 'tmp8:= ADD_DSZ32(0x000000f5, tmp6)' in text
    assert 'tmm3:= FPREADROM_DTYPENOP(tmp8)' in text
    for table in (False, True):
        low, high = (114, 118) if table else (118, 124)
        for z in (F(1, 73), F(3, 128), -F(17, 512)):
            expected = z + sum(ROM[k] * z ** (2 * (k-low) + 3) for k in range(low, high))
            assert run_slice(z, slices['short' if table else 'long'], table, exact=True) == expected
    counts = dict(groups=0, output_C1_interval_misses=0, raw_slice_python_disagreements=0)
    results = []
    for pair in json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs']:
        t = {}
        v5(*pair['raw'], trace=t)
        table = t['kind'] == 'table'
        raw_kernel = run_slice(t['z'], slices['short' if table else 'long'], table)
        direct_kernel = kernel(t['z'], table)
        mismatch = raw_kernel != direct_kernel
        actual = prevalue(*pair['raw'])
        band = observation_interval(pair['rows'])
        failed = not band.contains(abs(actual))
        counts['groups'] += 1
        counts['raw_slice_python_disagreements'] += mismatch
        counts['output_C1_interval_misses'] += failed
        results.append(dict(raw=pair['raw'], kind=t['kind'], prevalue=str(actual), interval=band.json(),
                            raw_kernel=str(raw_kernel), kernel_matches=not mismatch, observations_match=not failed))
    assert not counts['raw_slice_python_disagreements']
    save(BASE / 'd0021-goldmont-fpatan-audit.json', dict(status='SOURCE_GUIDED_DISCOVERY_NOT_PROMOTED',
         primary_urls=URLS, primary_sha256=PINS, projections=projections, coefficient_reads=orders,
         source_slices=slices, counts=counts, results=results,
         missing=['Goldmont architectural dispatch trace', 'Goldmont low ROM bits and exponent/sign metadata',
                  'Goldmont arithmetic opcode semantics', 'Skylake prospective transfer validation'],
         hardware_executed=False, numerical_model_promoted=False))
    print('PASS 42 ROM projections; raw operation-slice replay', counts, flush=True)


if __name__ == '__main__':
    main()

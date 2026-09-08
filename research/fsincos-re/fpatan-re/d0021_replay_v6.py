"""Authenticate and replay every retained hardware job against unpromoted V6."""
import argparse
import json
from pathlib import Path
from d0008_schedule_replay import BASE, digest, replay
from prepare import save


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--binary', type=Path, required=True)
    args = ap.parse_args()
    destination = BASE / 'd0021-v6-full-corpus-replay.json'
    assert not destination.exists()
    report = dict(status='OPENED_CORPUS_DISCOVERY_ONLY', hardware_executed=False,
                  numerical_model_promoted=False, binary_sha256=digest(args.binary),
                  sources={name: digest(Path(__file__).with_name(name)) for name in
                           ('fpatan_candidate_v6.c', 'graph_v6.py', 'd0021_replay_v6.py', 'd0008_schedule_replay.py')}, jobs={})
    for job in [f'd{i:04d}' for i in range(1, 10)] + ['d0013']:
        result = replay(args.binary.resolve(), None, job)
        report['jobs'][job] = result
        print('V6', job, result['counts'], flush=True)
    save(destination, report)
    print('COMPLETE V6 full saved corpus', json.dumps({j:r['counts'] for j,r in report['jobs'].items()}), flush=True)


if __name__ == '__main__':
    main()

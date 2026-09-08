"""Read-only authenticated complete-corpus replay of the V7 tie hypothesis."""
import argparse
from pathlib import Path
from d0008_schedule_replay import BASE, digest, replay
from prepare import save


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--binary', type=Path, required=True)
    a = ap.parse_args()
    destination = BASE / 'd0023-v7-full-corpus-replay.json'
    assert not destination.exists()
    report = dict(status='OPENED_CORPUS_DISCOVERY_ONLY', hardware_executed=False,
                  numerical_model_promoted=False, binary_sha256=digest(a.binary),
                  sources={n:digest(Path(__file__).with_name(n)) for n in
                           ('fpatan_candidate_v7.c', 'graph_v7.py', 'd0023_index_hypotheses.py', 'd0023_replay_v7.py')}, jobs={})
    for job in [f'd{i:04d}' for i in range(1, 10)] + ['d0013', 'd0022']:
        result = replay(a.binary.resolve(), None, job)
        report['jobs'][job] = result
        print('V7', job, result['counts'], flush=True)
    save(destination, report)
    print('COMPLETE all eleven saved jobs', flush=True)


if __name__ == '__main__':
    main()

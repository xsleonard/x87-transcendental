#!/usr/bin/env python3
"""Server-owned continuation of the frozen H1725 campaign.

No network calls. Expand a byte-exact, already-cleared compact input plan,
predict with the isolated model, call the ORIGINAL reservation/capture guard,
score with the ORIGINAL scorer, and retain losslessly encoded observations.
The model is a compression dictionary, never a substitute for an observation:
every status word and every differing raw line is stored; decoding must match
the SHA256 of the actual native output stream. Unobserved rows have no archive.
"""
import argparse
import base64
import collections
import fcntl
import gzip
import hashlib
import importlib.util
import io
import json
import os
import shutil
import struct
import sys
import time
import traceback
import types
from pathlib import Path

import suite
import h1725_remote_capture as capture

INSNS = ('fsin', 'fcos', 'fsincos')
MODES = ('rn', 'rd', 'ru', 'rz')
RECORD = struct.Struct('<QHQH')
CORPUS = 'x87-trig-v1-2126cf9ff5272e9d'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def durable(path, data):
    with path.open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    syncdir(path.parent)


def syncdir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, value):
    durable(path, (json.dumps(value, sort_keys=True, indent=2) + '\n').encode())


def status(base, stage, **extra):
    value = dict(stage=stage, updated_unix=time.time(), pid=os.getpid(), **extra)
    temp = base / ('STATUS.' + str(time.time_ns()) + '.next')
    save(temp, value); os.replace(temp, base / 'STATUS.json'); syncdir(base)
    print(json.dumps(value, sort_keys=True), flush=True)


def original_functions(package, pins):
    # Only the original predictor/scorer are reused. Do not import workstation
    # preparation modules (in particular the local-only private-ledger audit).
    stub = types.ModuleType('h1725_full_campaign')
    for k, v in dict(ROOT=package, BASE=package, HOSTS={}, CORPUS=CORPUS,
                     INSNS=INSNS, MODES=MODES, PINS=pins, save=save, suite=suite).items():
        setattr(stub, k, v)
    sys.modules['h1725_full_campaign'] = stub
    spec = importlib.util.spec_from_file_location('h1725_original_score', package / 'h1725_run_full.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.predict, module.score


def plan_chunk(package, index, number):
    entry = index['jobs'][str(number)]
    with (package / 'plan.bin').open('rb') as f:
        f.seek(entry['offset']); packed = f.read(entry['bytes'])
    if sha(packed) != entry['packed_sha256']:
        raise ValueError('corrupt compact input plan')
    raw = gzip.decompress(packed)
    if sha(raw) != entry['records_sha256'] or len(raw) != entry['operands'] * RECORD.size:
        raise ValueError('input plan expansion differs from frozen selection')
    records = list(RECORD.iter_unpack(raw))
    if any(not 0 < m < 4096 for _, _, _, m in records):
        raise ValueError('invalid selected mask')
    if any(a[0] >= b[0] for a, b in zip(records, records[1:])):
        raise ValueError('nonmonotonic selected ordinals')
    return records


def cases(records):
    for ordinal, se, sig, mask in records:
        for i in range(12):
            if mask & (1 << i):
                case = suite.case_id(INSNS[i // 4], MODES[i % 4], 64, f'{se:04x} {sig:016x}')
                yield case, ordinal * 12 + i


def canonical_line(case, predicted, bsw, asw):
    insn, mode, pc, op = suite.decode_case(case)
    values = predicted['value'].split()
    sine = cosine = preserved = '-'
    if values[0] == 'C2':
        preserved = op.replace(' ', ':')
    elif values[0] == 'OK':
        if insn == 'fcos':
            cosine = values[1] + ':' + values[2]
        else:
            sine = values[1] + ':' + values[2]
            if insn == 'fsincos':
                cosine = values[3] + ':' + values[4]
    else:
        raise ValueError('invalid prediction')
    return (f'CASE={case} INSN={insn} MODE={mode} PC=pc{pc} IN={op.replace(" ", ":")} '
            f'CW={suite.expected_cw(mode, pc):04x} B_SW={bsw:04x} A_SW={asw:04x} '
            f'SIN={sine} COS={cosine} PRESERVED={preserved}\n').encode()


def prediction_hash(predictions):
    return sha(json.dumps(predictions, sort_keys=True, separators=(',', ':')).encode())


def encode_lines(raw_lines, ordered_cases, predictions):
    statuses = bytearray(); exceptions = {}; native = hashlib.sha256(); rows = 0
    stream = iter(raw_lines)
    for n, case in enumerate(ordered_cases):
        raw = next(stream); native.update(raw)
        fields = suite.parse_numeric(raw.decode('ascii'))
        insn, mode, pc, op = suite.decode_case(case)
        suite.validate_numeric(fields, insn, mode, pc, op, case)
        bsw, asw = int(fields['B_SW'], 16), int(fields['A_SW'], 16)
        statuses.extend(struct.pack('<HH', bsw, asw))
        if raw != canonical_line(case, predictions[case], bsw, asw):
            exceptions[str(n)] = base64.b64encode(raw).decode('ascii')
        rows += 1
    if next(stream, None) is not None:
        raise ValueError('extra native output rows')
    return dict(schema='h1725-native-delta-v1', rows=rows, native_text_sha256=native.hexdigest(),
                prediction_content_sha256=prediction_hash(predictions),
                statuses_b64=base64.b64encode(statuses).decode('ascii'), raw_line_overrides=exceptions)


def decode_lines(payload, ordered_cases, predictions):
    if payload['schema'] != 'h1725-native-delta-v1' or prediction_hash(predictions) != payload['prediction_content_sha256']:
        raise ValueError('wrong compression dictionary / predictor')
    raw_statuses = base64.b64decode(payload['statuses_b64'], validate=True)
    if len(raw_statuses) != payload['rows'] * 4 or len(ordered_cases) != payload['rows']:
        raise ValueError('truncated or excess observation statuses')
    overrides = payload['raw_line_overrides']; used = set(); native = hashlib.sha256()
    for n, (case, (bsw, asw)) in enumerate(zip(ordered_cases, struct.iter_unpack('<HH', raw_statuses))):
        key = str(n)
        if key in overrides:
            raw = base64.b64decode(overrides[key], validate=True); used.add(key)
        else:
            raw = canonical_line(case, predictions[case], bsw, asw)
        fields = suite.parse_numeric(raw.decode('ascii'))
        insn, mode, pc, op = suite.decode_case(case)
        suite.validate_numeric(fields, insn, mode, pc, op, case)
        if (int(fields['B_SW'], 16), int(fields['A_SW'], 16)) != (bsw, asw):
            raise ValueError('override/status conflict')
        native.update(raw); yield raw
    if used != set(overrides) or native.hexdigest() != payload['native_text_sha256']:
        raise ValueError('native observation round-trip hash mismatch')


def prepare(job, records, cfg, predict):
    job.mkdir(); syncdir(job.parent)
    predictions = predict(job, records, Path(cfg['predictor']))
    pairs = list(cases(records))
    with (job / 'inputs.txt.gz').open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=1) as f:
            for case, _ in pairs:
                f.write((suite.capture_line(case) + '\n').encode())
        raw.flush(); os.fsync(raw.fileno())
    durable(job / 'indices.bin', b''.join(struct.pack('<Q', index) for _, index in pairs))
    save(job / 'JOB.json', dict(corpus_id=CORPUS, host=cfg['host'], pc=64, rows=len(pairs),
        cpu_context_id=cfg['cpu_context_id'], binary_sha256=cfg['capture_sha256'],
        files={n: suite.digest(job / n) for n in ('inputs.txt.gz', 'indices.bin')},
        predictions_sha256=suite.digest(job / 'predictions.json.gz'),
        selection_sha256=cfg['selection_sha256'], first_ordinal=records[0][0], last_ordinal=records[-1][0],
        frozen_before_capture=True, algorithm_pins=cfg['algorithm_pins'],
        prediction_executable_sha256=cfg['predictor_sha256'],
        retention='lossless native-delta-v1, exact native text hash, all SW bits and differing raw lines'))
    return predictions


META_FILES = ('JOB.json', 'STARTED.json', 'COMPLETE.json', 'cpu.json', 'cpu-after.json',
              'score.json', 'observations/cpu.json', 'observations/provenance.json', 'observations/MANIFEST.json')


def seal(job, target, records, cfg, predictions):
    ordered = [case for case, _ in cases(records)]
    complete = json.loads((job / 'COMPLETE.json').read_text())
    if (complete['status'] != 'OPENED_ONCE_DO_NOT_RERUN' or complete['instruction_retries'] != 0
            or complete['outputs_sha256'] != suite.digest(job / 'outputs.txt.gz')
            or complete['inputs_sha256'] != suite.digest(job / 'inputs.txt.gz')
            or complete['rows'] != len(ordered) or complete['cpu_context_id'] != cfg['cpu_context_id']
            or complete['binary_sha256'] != cfg['capture_sha256']):
        raise ValueError('capture receipt mismatch')
    with gzip.open(job / 'outputs.txt.gz', 'rb') as f:
        payload = encode_lines(f, ordered, predictions)
    payload.update(job=job.name, predictor_sha256=cfg['predictor_sha256'],
        selection_sha256=cfg['selection_sha256'],
        records_sha256=sha(b''.join(RECORD.pack(*r) for r in records)),
        metadata={n: base64.b64encode((job / n).read_bytes()).decode('ascii') for n in META_FILES})
    packed = gzip.compress(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode(), compresslevel=9, mtime=0)
    if target.exists():
        if target.read_bytes() != packed:
            raise ValueError('different existing observation archive; preserve both for inspection')
    else:
        durable(target, packed)
    # Verify the ON-DISK archive against every actual raw byte before any
    # scratch release. This is not a numerical-only or model-only check.
    decoded = json.loads(gzip.decompress(target.read_bytes()))
    with gzip.open(job / 'outputs.txt.gz', 'rb') as original:
        for raw in decode_lines(decoded, ordered, predictions):
            if raw != next(original):
                raise ValueError('lossy native output encoding')
        if original.read(1):
            raise ValueError('excess original output')
    return dict(archive_sha256=suite.digest(target), native_text_sha256=payload['native_text_sha256'],
                archive_bytes=target.stat().st_size, rows=len(ordered))


def release_scratch(job, receipt):
    # ONLY new autonomous scratch is eligible. Every observation remains in
    # the verified self-contained codec package + native archive. Legacy jobs
    # and their Mac-offloaded raw outputs are never rewritten or removed.
    if receipt['status'] != 'PASS_NATIVE_OBSERVATIONS_RETAINED':
        raise ValueError('missing durable retention receipt')
    for name, expected in receipt['scratch_files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('unsafe scratch path')
        path = job / name
        if path.exists():
            if suite.digest(path) != expected:
                raise ValueError('scratch changed after archive verification')
            path.unlink()
    for path in (job / 'observations', job):
        if path.exists():
            path.rmdir()
    syncdir(job.parent)


def verify_package(package):
    manifest = json.loads((package / 'PACKAGE.json').read_text())
    for name, digest in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts or suite.digest(package / name) != digest:
            raise ValueError('changed frozen autonomous package: ' + name)
    return manifest


def run(package):
    manifest = verify_package(package)
    cfg = json.loads((package / 'CUTOVER.json').read_text())
    if suite.digest(package / 'CUTOVER.json') != manifest['cutover_sha256']:
        raise ValueError('changed cutover checkpoint')
    index = json.loads((package / 'PLAN.json').read_text())
    if index['selection_sha256'] != cfg['selection_sha256'] or index['corpus_id'] != CORPUS:
        raise ValueError('wrong frozen plan')
    base = Path(cfg['remote_base']); archives = package / 'observed'; archives.mkdir(exist_ok=True)
    predict, score = original_functions(package, cfg['algorithm_pins'])
    totals = collections.Counter(cfg['prior_totals']); started = time.time()
    if (package / 'STOPPED.json').exists():
        raise ValueError('latched failure: inspect, never blindly restart')
    with (package / 'owner.lock').open('a') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for number in range(cfg['start_job'], index['end_job']):
            name = f'job-{number:06d}'; job = base / name; archive = archives / (name + '.json.gz')
            receipt_path = archives / (name + '.DONE.json')
            if receipt_path.exists():
                receipt = json.loads(receipt_path.read_text())
                if suite.digest(archive) != receipt['archive_sha256']:
                    raise ValueError('changed retained observation archive')
                totals.update(receipt['counts'])
                if receipt['totals'] != dict(totals):
                    raise ValueError('noncontiguous cumulative checkpoints')
                if job.exists():
                    release_scratch(job, receipt)
                continue
            if archive.exists() or job.exists():
                # A torn checkpoint is not a fresh job. Complete saved outputs
                # may be recovered by a read-only repair; never re-execute it.
                raise ValueError('uncheckpointed/uncertain job retained; no recapture: ' + name)
            if suite.digest(cfg['predictor']) != cfg['predictor_sha256']:
                raise ValueError('changed frozen predictor')
            if shutil.disk_usage(base).free < 128 * 1024 * 1024:
                raise ValueError('insufficient safe disk headroom; observations preserved')
            records = plan_chunk(package, index, number)
            status(package, 'PREDICTING', job=name, verified_fresh_cases=totals['rows'])
            predictions = prepare(job, records, cfg, predict)
            # The old shared guard, old SQLite ledger, and old permanent bitmap
            # are unchanged. No new empty ledger or cleared reservation exists.
            with (base / 'campaign.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                status(package, 'CAPTURING_ONCE', job=name, verified_fresh_cases=totals['rows'])
                capture.run(base, job, Path(cfg['capture_binary']), Path(cfg['ledger']))
            status(package, 'SCORING', job=name, verified_fresh_cases=totals['rows'])
            counts, misses = score(job, predictions)
            # Retain every mismatch's complete original raw output and detailed
            # score; fail before another native shard, without any retry.
            if misses:
                raise ValueError('MODEL_MISMATCH retained in ' + str(job))
            receipt = seal(job, archive, records, cfg, predictions)
            totals.update(counts)
            receipt.update(status='PASS_NATIVE_OBSERVATIONS_RETAINED', counts=dict(counts), totals=dict(totals),
                           seconds=time.time() - started, completed_unix=time.time())
            files = {str(p.relative_to(job)): suite.digest(p) for p in job.rglob('*') if p.is_file()}
            save(job / 'RETAINED.json', dict(archive=str(archive), **receipt))
            files['RETAINED.json'] = suite.digest(job / 'RETAINED.json')
            receipt['scratch_files'] = files
            save(receipt_path, receipt)
            release_scratch(job, receipt)
            status(package, 'RUNNING', job=name, verified_fresh_cases=totals['rows'],
                   numerical_or_C1_C2_misses=0, selected_fresh_cases=cfg['selected_cases'],
                   completed_new_jobs=number - cfg['start_job'] + 1, elapsed_seconds=time.time() - started)
        if totals['rows'] != cfg['selected_cases']:
            raise ValueError('selected-case total mismatch')
        result = dict(status='PASS_SELECTED_REMAINING_CASES', totals=dict(totals),
                      full_matrix_complete=False, remaining_holds=cfg['selection_counts'],
                      paper_changed=False, algorithm_changed=False, completed_unix=time.time())
        if not (package / 'RUN_COMPLETE.json').exists():
            save(package / 'RUN_COMPLETE.json', result)
        status(package, 'SELECTED_RUN_COMPLETE_HOLDS_REMAIN', verified_fresh_cases=totals['rows'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args(); package = args.package.resolve()
    try:
        run(package)
    except BaseException as exc:
        status(package, 'STOPPED_INSPECT_RECEIPTS', error=repr(exc))
        if not (package / 'STOPPED.json').exists():
            save(package / 'STOPPED.json', dict(error=repr(exc), traceback=traceback.format_exc(), time=time.time()))
        raise

#!/usr/bin/env python3
"""Merge shards from one CPU context; reject conflicting case observations."""
import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path
import suite


def identity_key(cpu):
    if cpu.get('identity_kind')=='direct_reported_CPUID':return ('direct',cpu['context_id'])
    if cpu.get('identity_kind')=='historical_reported_FMS':return ('historical',json.dumps(cpu['reported'],sort_keys=True))
    raise ValueError('unrecognized or unverified CPU context')


def merge(inputs,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    with closing(suite.create_observation_db(out)) as db:
        key=None;cpu=None;duplicates=0;provenance=[]
        for directory in map(Path,inputs):
            suite.verify_dataset(directory);current=json.loads((directory/'cpu.json').read_text())
            if key is None:key=identity_key(current);cpu=current
            elif identity_key(current)!=key:raise ValueError('cannot merge different CPU contexts; compare them instead')
            count=0
            for row in suite.observations(directory):
                values=(row['case_id'],row['sin'],row['cos'],int(row['C2']),int(row['C1']),row['SW']);count+=1
                try:db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?)',values)
                except sqlite3.IntegrityError:
                    previous=db.execute('SELECT case_id,sin,cos,c2,c1,sw FROM observations WHERE case_id=?',(values[0],)).fetchone()
                    if previous!=values:raise ValueError('conflicting observations for '+values[0])
                    duplicates+=1
            provenance.append(dict(manifest_sha256=suite.digest(directory/'MANIFEST.json'),rows=count))
        if key is None:raise ValueError('no input datasets')
        db.commit();count=suite.finish_observations(out,db,cpu,dict(source='same_context_shard_union',inputs=provenance,
            identical_duplicate_appearances=duplicates,hardware_executions=0,observations_reused=True))
    return dict(merged_unique_rows=count,identical_duplicate_appearances=duplicates,source_datasets=len(inputs))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('observations',type=Path,nargs='+')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(merge(a.observations,a.output),sort_keys=True))


if __name__=='__main__':main()

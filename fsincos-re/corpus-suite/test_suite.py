#!/usr/bin/env python3
"""Synthetic protocol, mutation, identity, and no-repeat tests; no x87 runs."""
import contextlib
import csv
import io
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock
import suite
import run_capture
import merge_observations


class SuiteTests(unittest.TestCase):
    def setUp(self):self.root=Path(tempfile.mkdtemp(prefix='x87_suite_test_'))

    def raw(self,case,sine='3ffd:aaaaaaaaaaaaaaab',cosine='3ffe:eeeeeeeeeeeeeeee',c2=False):
        insn,mode,pc,op=suite.decode_case(case);cw=suite.expected_cw(mode,pc)
        sw=0x3c00 if c2 else (0x3000 if insn=='fsincos' else 0x3800)|0x220
        return dict(CASE=case,INSN=insn,MODE=mode,PC=f'pc{pc}',IN=op.replace(' ',':'),CW=f'{cw:04x}',
            B_SW='3800',A_SW=f'{sw:04x}',SIN='-' if c2 or insn=='fcos' else sine,
            COS='-' if c2 or insn=='fsin' else cosine,PRESERVED=op.replace(' ',':') if c2 else '-')

    def dataset(self,name,rows,cpu=None):
        out=self.root/name;out.mkdir();db=suite.create_observation_db(out)
        db.executemany('INSERT INTO observations VALUES(?,?,?,?,?,?)',rows);db.commit()
        suite.finish_observations(out,db,cpu or dict(identity_kind='synthetic_only'),dict(hardware_executions=0));db.close();return out

    def test_case_ids_and_protocol_mutations(self):
        n=0
        for insn in suite.INSNS:
            for mode in suite.MODES:
                for pc in suite.PCS:
                    for c2 in (False,True):
                        op='403e 8000000000000000' if c2 else '3ffd aaaaaaaaaaaaaaaa'
                        case=suite.case_id(insn,mode,pc,op);self.assertEqual(suite.decode_case(case),(insn,mode,pc,op))
                        d=self.raw(case,c2=c2);line=' '.join(k+'='+v for k,v in d.items())
                        self.assertEqual(suite.validate_numeric(suite.parse_numeric(line),insn,mode,pc,op,case)[0],case)
                        for key,value in (('CASE','wrong'),('CW','0000'),('IN','0000:0000000000000000'),('B_SW','0000'),('A_SW','0000')):
                            bad=dict(d);bad[key]=value
                            with self.assertRaises(ValueError):suite.validate_numeric(bad,insn,mode,pc,op,case)
                            n+=1
                        with self.assertRaises(ValueError):suite.parse_numeric(line+' SIN=-')
        self.assertEqual(n,360)

    def test_compare_missing_different_and_equal(self):
        a=suite.case_id('fsin','rn',64,'3ffc aaaaaaaaaaaaaaaa');b=suite.case_id('fcos','rd',53,'3ffd bbbbbbbbbbbbbbbb')
        c=suite.case_id('fsincos','ru',24,'3ffe cccccccccccccccc')
        x=(a,'3ffc:abababababababab','-',0,0,'3820');y=(b,'-','3ffe:abababababababab',0,1,'3a20')
        left=self.dataset('left',[x,y]);right=self.dataset('right',[(a,'3ffc:abababababababaa','-',0,1,'3a20'),(c,'3ffe:abababababababab','3ffd:abababababababab',0,0,'3020')])
        r=suite.compare(left,right,self.root/'comparison');self.assertEqual(r['counts']['common'],1)
        self.assertEqual(r['counts']['left_only'],1);self.assertEqual(r['counts']['right_only'],1)
        self.assertEqual(r['counts']['numeric_or_C2_differences'],1);self.assertEqual(r['counts']['C1_observed_differences'],1)
        same=suite.compare(left,left,self.root/'same');self.assertEqual(same['status'],'MATCH_ON_COMMON_CASES')
        none=suite.compare(self.dataset('a',[x]),self.dataset('b',[y]),self.root/'none');self.assertEqual(none['status'],'NO_COMMON_CASES')

    def test_export_dedup_shards_and_reproducibility(self):
        corpus=self.root/'corpus';corpus.mkdir()
        with suite.gzwrite(corpus/'operands.tsv.gz') as f:f.write('se\tsig\tprofiles\tsources\n3ffc\taaaaaaaaaaaaaaaa\t3\t1\n3ffd\tbbbbbbbbbbbbbbbb\t0\t2\n')
        suite.save(corpus/'MANIFEST.json',dict(kind='input_corpus',corpus_id='test',files={'operands.tsv.gz':suite.digest(corpus/'operands.tsv.gz')}))
        case=suite.case_id('fsin','rn',64,'3ffc aaaaaaaaaaaaaaaa');prior=self.dataset('prior',[(case,'3ffc:aaaaaaaaaaaaaaab','-',0,1,'3a20')])
        r=suite.export(corpus,self.root/'export','core',['rn'],[64],1,[prior])
        self.assertEqual(r['exported_rows'],2);self.assertEqual(r['skipped_existing_observations'],1);self.assertEqual(len(r['jobs']),2)
        for directory in ('det1','det2'):
            with suite.gzwrite(self.root/(directory+'.gz')) as f:f.write('identical payload\n')
        self.assertEqual(suite.digest(self.root/'det1.gz'),suite.digest(self.root/'det2.gz'))

    def test_merge_context_and_conflict_guards(self):
        a=suite.case_id('fsin','rn',64,'3ffc aaaaaaaaaaaaaaaa');b=suite.case_id('fcos','rd',64,'3ffd bbbbbbbbbbbbbbbb')
        x=(a,'3ffc:aaaaaaaaaaaaaaab','-',0,1,'3a20');y=(b,'-','3ffe:bbbbbbbbbbbbbbbb',0,0,'3820')
        cpu=dict(identity_kind='direct_reported_CPUID',context_id='synthetic-a')
        left=self.dataset('left',[x],cpu);right=self.dataset('right',[y],cpu)
        report=merge_observations.merge([left,right],self.root/'merged');self.assertEqual(report['merged_unique_rows'],2)
        duplicate=merge_observations.merge([left,left],self.root/'identical');self.assertEqual(duplicate['identical_duplicate_appearances'],1)
        changed=self.dataset('changed',[(a,'3ffc:aaaaaaaaaaaaaaaa','-',0,0,'3820')],cpu)
        with self.assertRaises(ValueError):merge_observations.merge([left,changed],self.root/'conflict')
        other=self.dataset('other',[y],dict(identity_kind='direct_reported_CPUID',context_id='synthetic-b'))
        with self.assertRaises(ValueError):merge_observations.merge([left,other],self.root/'mixed-cpus')

    def test_bounded_export_and_runtime_budget(self):
        corpus=self.root/'bounded';corpus.mkdir()
        with suite.gzwrite(corpus/'operands.tsv.gz') as f:
            f.write('se\tsig\tprofiles\tsources\n3ffc\taaaaaaaaaaaaaaaa\t3\t1\n3ffd\tbbbbbbbbbbbbbbbb\t1\t1\n')
        suite.save(corpus/'MANIFEST.json',dict(kind='input_corpus',corpus_id='bounded',
            files={'operands.tsv.gz':suite.digest(corpus/'operands.tsv.gz')},profiles={'full':{'operands':2}}))
        result=suite.export(corpus,self.root/'bounded-jobs','full',['rn'],[64],100,[],1,1)
        self.assertEqual(result['exported_rows'],3);self.assertEqual(result['next_operand'],2)
        with (self.root/'bounded-jobs/job-00000/inputs.txt').open() as f:
            self.assertTrue(all('3ffd bbbbbbbbbbbbbbbb' in line for line in f))
        estimate=suite.plan(corpus,'full',list(suite.MODES),[64],1,1)
        self.assertEqual(estimate['executions'],24);self.assertTrue(estimate['within_budget'])
        self.assertFalse(suite.plan(corpus,'full',list(suite.MODES),[64],1,0.001)['within_budget'])
        for rate in (0,-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):suite.plan(corpus,'full',['rn'],[64],rate,1)

    def test_full_cli_uses_pc64_and_explicit_pcs_override(self):
        for options,want in (([],[64]),(['--pcs','24','53','64'],[24,53,64])):
            argv=['suite.py','export','unused','--profile','full','--output','unused-output',*options]
            with mock.patch.object(sys,'argv',argv),mock.patch.object(suite,'export',return_value={}) as export,contextlib.redirect_stdout(io.StringIO()):
                suite.main()
            self.assertEqual(export.call_args.args[4],want)

    def test_numeric_import_authenticates_cpu_and_outputs(self):
        case=suite.case_id('fsincos','rn',64,'3ffc aaaaaaaaaaaaaaaa');run=self.root/'run';run.mkdir()
        (run/'inputs.txt').write_text(suite.capture_line(case)+'\n');d=self.raw(case)
        (run/'outputs.txt').write_text(' '.join(k+'='+v for k,v in d.items())+'\n')
        suite.save(run/'cpu.json',dict(identity_kind='synthetic_only'))
        suite.save(run/'COMPLETE.json',dict(status='OPENED_ONCE_DO_NOT_RERUN',rows=1,
            inputs_sha256=suite.digest(run/'inputs.txt'),outputs_sha256=suite.digest(run/'outputs.txt'),cpu_sha256=suite.digest(run/'cpu.json')))
        self.assertEqual(suite.import_numeric(run,self.root/'observations'),1)
        (run/'cpu.json').write_text('{}\n')
        with self.assertRaises(ValueError):suite.import_numeric(run,self.root/'tampered')

    def test_runner_reservation_is_atomic_and_partial_is_not_retried(self):
        binary=self.root/'synthetic_binary';binary.write_bytes(b'not executable; tests mock execution\n')
        case=suite.case_id('fsin','rn',64,'3ffc aaaaaaaaaaaaaaaa');other=suite.case_id('fcos','rd',64,'3ffd bbbbbbbbbbbbbbbb')
        metadata=dict(context_id='synthetic-cpu',identity_kind='synthetic_only')
        calls=[]
        def job(name,cases):
            path=self.root/name;path.mkdir();(path/'inputs.txt').write_text(''.join(suite.capture_line(x)+'\n' for x in cases))
            suite.save(path/'JOB.json',dict(rows=len(cases),inputs_sha256=suite.digest(path/'inputs.txt')));return path
        first=job('job1',[case]);overlap=job('job2',[other,case]);fresh=job('job3',[other])
        def execute(args,stdin,stdout,stderr):
            calls.append(args)
            for line in stdin.read().decode().splitlines():
                d=self.raw(line.split()[0]);stdout.write((' '.join(k+'='+v for k,v in d.items())+'\n').encode())
            return types.SimpleNamespace(returncode=0)
        def invoke(j,out,execute_function):
            argv=['run_capture.py','--job',str(j),'--binary',str(binary),'--ledger',str(self.root/'ledger.sqlite'),
                '--output',str(self.root/out),'--label','synthetic']
            with mock.patch.object(sys,'argv',argv),mock.patch.object(run_capture.os,'sched_getaffinity',return_value={0},create=True),\
                 mock.patch.object(run_capture.os,'sched_setaffinity',create=True),mock.patch.object(run_capture,'identify',return_value=metadata),\
                 mock.patch.object(run_capture.subprocess,'run',side_effect=execute_function),contextlib.redirect_stdout(io.StringIO()):run_capture.main()
        invoke(first,'run1',execute);self.assertEqual(len(calls),1)
        with self.assertRaises(SystemExit):invoke(first,'run-again',execute)
        with self.assertRaises(SystemExit):invoke(overlap,'run-overlap',execute)
        self.assertEqual(len(calls),1)
        db=sqlite3.connect(self.root/'ledger.sqlite')
        self.assertEqual(db.execute('SELECT count(*) FROM reservations WHERE case_id=?',(other,)).fetchone()[0],0);db.close()
        def fail(*args,**kwargs):calls.append('failure');return types.SimpleNamespace(returncode=3)
        with self.assertRaises(RuntimeError):invoke(fresh,'run-failed',fail)
        self.assertTrue((self.root/'run-failed/FAILED.json').exists())
        with self.assertRaises(SystemExit):invoke(fresh,'run-failed-again',execute)
        self.assertEqual(len(calls),2)


if __name__=='__main__':unittest.main()

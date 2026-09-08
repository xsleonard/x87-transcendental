#!/usr/bin/env python3
"""Closed stage predicates checked against the actual restricted Python AST.

Only classify/plan are translated automatically. Writeback/wrapped predicates
also assume the existing numerical-C2 and state-result contracts. This is not
a general Python verifier, complete machine-state model or silicon proof.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
import z3
import cvc5
import h1703_composed_transition as actual
from h1700_exact_reduction_certificate import solve
from h1640_remaining_scope_freshness import save
from h1650_score_masked_state import digest

WIDTH = 128
STRINGS = ('fsin', 'fcos', 'zero', 'denormal', 'pseudo_denormal', 'unsupported',
    'infinity', 'quiet_nan', 'signaling_nan', 'normal_in_range', 'normal_out_of_range',
    'empty_stack', 'pending', 'early', 'masked_empty', 'number',
    'ASSERTION_ERROR', 'RESERVED_PC', 'INCOHERENT_SUMMARY', 'FALLTHROUGH')
CODES = {name: index for index, name in enumerate(STRINGS)}
LOCKS = {
    'experiments/h1645_masked_status_model.py': 'd00bbf0adf069be0e2553712c45df96eb1e457dfe74b8403e27b61f69eda0fc5',
    'experiments/h1703_composed_transition.py': 'ccd3c802d5f28318f504e8d9dfc55c8dca0cc41d258fd5216b431172dc9fca87',
    'experiments/h1700_exact_reduction_certificate.py': 'ac6ece113c44b2dc6d172a0eaacb9082c61e09c68d44dbef2b8e71902a9d0802',
}


def word(value):
    return z3.BitVecVal(CODES[value] if isinstance(value, str) else value, WIDTH)


def truth(value):
    return value if z3.is_bool(value) else value != word(0)


class RestrictedAST:
    """Fail-closed translator for the syntax actually present in classify/plan.

    All public integers are nonnegative <=64-bit. The 128-bit carrier holds
    even the assertion bound2^64. Invert occurs only inside a masked flags
    expression; its finite two's-complement low bits equal Python's unbounded
    complement there. No arithmetic overflow, negative ordering, arbitrary
    calls, loops, attributes-as-data or general Python semantics are modeled.
    """
    def __init__(self, classify, planner):
        self.functions = {'raw.classify': classify, 'plan': planner}
        self.nodes = Counter()

    def expr(self, node, env):
        self.nodes[type(node).__name__] += 1
        if isinstance(node, ast.Constant):
            assert isinstance(node.value, (int, str)) and not isinstance(node.value, bool)
            return word(node.value)
        if isinstance(node, ast.Name): return env[node.id]
        if isinstance(node, ast.Tuple): return [self.expr(n, env) for n in node.elts]
        if isinstance(node, ast.BinOp):
            a,b = self.expr(node.left,env), self.expr(node.right,env)
            if isinstance(node.op,ast.BitAnd): return a & b
            if isinstance(node.op,ast.BitOr): return a | b
            if isinstance(node.op,ast.BitXor): return a ^ b
            if isinstance(node.op,ast.LShift): return a << b
            if isinstance(node.op,ast.RShift): return z3.LShR(a,b)
            raise AssertionError(('unsupported binary operator',ast.dump(node)))
        if isinstance(node, ast.UnaryOp):
            v=self.expr(node.operand,env)
            if isinstance(node.op,ast.Not): return z3.Not(truth(v))
            if isinstance(node.op,ast.Invert): return ~v
            raise AssertionError(('unsupported unary operator',ast.dump(node)))
        if isinstance(node, ast.BoolOp):
            values=[truth(self.expr(n,env)) for n in node.values]
            # These source BoolOps occur in predicates, not value-producing
            # Python 'and/or' expressions with non-Boolean return values.
            if isinstance(node.op,ast.And): return z3.And(*values)
            if isinstance(node.op,ast.Or): return z3.Or(*values)
            raise AssertionError(ast.dump(node))
        if isinstance(node,ast.Compare):
            left=self.expr(node.left,env); comparisons=[]
            for op,n in zip(node.ops,node.comparators):
                right=self.expr(n,env)
                if isinstance(op,ast.In): result=z3.Or(*(left==r for r in right))
                elif isinstance(op,ast.Eq): result=left==right
                elif isinstance(op,ast.NotEq): result=left!=right
                elif isinstance(op,ast.Lt): result=z3.ULT(left,right)
                elif isinstance(op,ast.LtE): result=z3.ULE(left,right)
                elif isinstance(op,ast.Gt): result=z3.UGT(left,right)
                elif isinstance(op,ast.GtE): result=z3.UGE(left,right)
                else: raise AssertionError(('unsupported comparison',ast.dump(node)))
                comparisons.append(result);left=right
            return z3.And(*comparisons)
        if isinstance(node,ast.IfExp):
            return z3.If(truth(self.expr(node.test,env)),self.expr(node.body,env),self.expr(node.orelse,env))
        if isinstance(node,ast.Call):
            if isinstance(node.func,ast.Name) and node.func.id=='bool':
                assert len(node.args)==1 and not node.keywords
                return truth(self.expr(node.args[0],env))
            assert isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name)
            name=node.func.value.id+'.'+node.func.attr
            assert name=='raw.classify' and len(node.args)==2 and not node.keywords
            args=[self.expr(n,env) for n in node.args]
            return self.compile(name,dict(zip(('se','sig'),args)))[0]
        raise AssertionError(('unsupported expression',ast.dump(node)))

    def block(self, statements, env, guard):
        if not statements: return [(guard,word('FALLTHROUGH'))]
        node,*rest=statements;self.nodes[type(node).__name__]+=1
        if isinstance(node,ast.Assert):
            test=truth(self.expr(node.test,env))
            return [(z3.And(guard,z3.Not(test)),word('ASSERTION_ERROR'))]+self.block(rest,env,z3.And(guard,test))
        if isinstance(node,ast.Assign):
            assert len(node.targets)==1 and isinstance(node.targets[0],ast.Name)
            return self.block(rest,env|{node.targets[0].id:self.expr(node.value,env)},guard)
        if isinstance(node,ast.If):
            test=truth(self.expr(node.test,env))
            return self.block(node.body+rest,dict(env),z3.And(guard,test))+self.block(node.orelse+rest,dict(env),z3.And(guard,z3.Not(test)))
        if isinstance(node,ast.Return): return [(guard,self.expr(node.value,env))]
        if isinstance(node,ast.Raise):
            assert isinstance(node.exc,ast.Call) and isinstance(node.exc.func,ast.Name) and node.exc.func.id=='NotImplementedError'
            message=node.exc.args[0].value
            code={'Reserved precision control remains unresolved':'RESERVED_PC',
                'Incoherent ES/B/flags/masks remain outside the state contract':'INCOHERENT_SUMMARY'}[message]
            return [(guard,word(code))]
        raise AssertionError(('unsupported statement',ast.dump(node)))

    def compile(self,name,args):
        env={'B63':word(1<<63),'Q':word(1<<62)}|args
        leaves=self.block(self.functions[name].body,env,z3.BoolVal(True))
        value=word('FALLTHROUGH')
        for guard,result in reversed(leaves):value=z3.If(guard,result,value)
        return z3.simplify(value),leaves


def functions(root):
    def find(path,name):
        tree=ast.parse((root/path).read_text())
        return next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    return find('experiments/h1645_masked_status_model.py','classify'),find('experiments/h1703_composed_transition.py','plan')


def symbols():
    names=('se','sig','instruction','before_status','before_tag','control_word')
    variables={name:z3.BitVec(name,WIDTH) for name in names}
    domain=[z3.ULT(variables[name],word(1<<bits)) for name,bits in
        (('se',16),('sig',64),('before_status',16),('before_tag',8),('control_word',16))]
    domain.append(z3.Or(variables['instruction']==word('fsin'),variables['instruction']==word('fcos')))
    return variables,domain


def reference(v):
    se,sig,sw,tag,cw=(v[n] for n in ('se','sig','before_status','before_tag','control_word'))
    e=se&0x7fff;j=(sig&(1<<63))!=0;q=(sig&(1<<62))!=0
    occupied=(z3.LShR(tag,z3.LShR(sw,11)&7)&1)!=0
    mask=cw&63;pending=(sw&63&~mask)!=0
    valid_pc=(cw&0x300)!=0x100
    coherent=(sw&0x8080)==z3.If(pending,word(0x8080),word(0))
    accepted=z3.And(valid_pc,coherent)
    invalid=z3.Or(z3.Not(occupied),z3.And(e!=0,z3.Not(j)),z3.And(e==0x7fff,z3.Not(q)))
    denormal=z3.And(occupied,e==0,sig!=0)
    early=z3.Or(z3.And(invalid,(mask&1)==0),z3.And(denormal,(mask&2)==0))
    range_reject=z3.And(occupied,j,z3.UGE(e,word(0x403e)),z3.ULT(e,word(0x7fff)))
    active=z3.And(accepted,z3.Not(pending),z3.Not(early))
    number=z3.And(active,occupied)
    writeback=z3.And(active,z3.Not(range_reject))
    wrapped=z3.And(active,occupied,e==0,sig!=0,z3.Not(j),v['instruction']==word('fsin'),(mask&0x10)==0)
    stage=z3.If(z3.Not(valid_pc),word('RESERVED_PC'),z3.If(z3.Not(coherent),word('INCOHERENT_SUMMARY'),
        z3.If(pending,word('pending'),z3.If(early,word('early'),z3.If(z3.Not(occupied),word('masked_empty'),word('number'))))))
    return dict(stage=stage,accepted=accepted,occupied=occupied,pending=pending,early=early,
        number=number,writeback=writeback,wrapped=wrapped,range_reject=range_reject,mask=mask)


def queries(classifier,planner):
    v,domain=symbols();compiler=RestrictedAST(classifier,planner)
    translated,leaves=compiler.compile('plan',v);r=reference(v)
    yield 'actual_plan_AST_equals_closed_stage',domain,translated!=r['stage'],'UNSAT'
    yield 'valid_inputs_never_assert_or_fallthrough',domain,z3.Or(translated==word('ASSERTION_ERROR'),translated==word('FALLTHROUGH')),'UNSAT'
    yield 'numerical_request_closed_form',domain,(translated==word('number'))!=r['number'],'UNSAT'
    # This writeback expression is a separate small manual translation of
    # the Composed-return branches, conditional on backend C2 iff raw range.
    writeback=z3.Or(translated==word('masked_empty'),z3.And(translated==word('number'),z3.Not(r['range_reject'])))
    yield 'writeback_under_C2_contract',domain,writeback!=r['writeback'],'UNSAT'
    yield 'pending_never_evaluates_or_commits',domain+[r['accepted'],r['pending']],z3.Or(r['number'],r['writeback']),'UNSAT'
    yield 'early_never_evaluates_or_commits',domain+[r['accepted'],z3.Not(r['pending']),r['early']],z3.Or(r['number'],r['writeback']),'UNSAT'
    yield 'wrapped_requires_DM_masked',domain+[r['wrapped']],(r['mask']&2)==0,'UNSAT'
    yield 'wrapped_requires_evaluation_and_commit',domain+[r['wrapped']],z3.Not(z3.And(r['number'],r['writeback'])),'UNSAT'
    changed=v|{'se':v['se']^0x8000}
    other=RestrictedAST(classifier,planner).compile('plan',changed)[0]
    yield 'planner_sign_independence',domain,translated!=other,'UNSAT'
    nuisance=z3.BitVec('nuisance_control_bits',WIDTH)
    changed=v|{'control_word':v['control_word']^(nuisance&0xfcc0)}
    other=RestrictedAST(classifier,planner).compile('plan',changed)[0]
    yield 'planner_unused_CW_RC_bits_independence',domain,translated!=other,'UNSAT'
    changed=v|{'before_status':v['before_status']^(nuisance&0x4740)}
    other=RestrictedAST(classifier,planner).compile('plan',changed)[0]
    yield 'planner_CC_SF_independence',domain,translated!=other,'UNSAT'
    # Numerical request is not writeback: masked empty and C2 distinguish them.
    yield 'NEGATIVE_request_is_not_writeback',domain,r['number']!=r['writeback'],'SAT'
    class LosePseudo(ast.NodeTransformer):
        def visit_Constant(self,node):
            return ast.copy_location(ast.Constant('normal_in_range'),node) if node.value=='pseudo_denormal' else node
    bad_class=LosePseudo().visit(ast.parse(ast.unparse(classifier)).body[0])
    bad=RestrictedAST(bad_class,planner).compile('plan',v)[0]
    yield 'NEGATIVE_canonicalize_pseudo_before_classify',domain,bad!=r['stage'],'SAT'
    class LosePending(ast.NodeTransformer):
        def visit_Return(self,node):
            return ast.copy_location(ast.Return(ast.Constant('number')),node) if isinstance(node.value,ast.Constant) and node.value.value=='pending' else node
    bad_plan=LosePending().visit(ast.parse(ast.unparse(planner)).body[0])
    bad=RestrictedAST(classifier,bad_plan).compile('plan',v)[0]
    yield 'NEGATIVE_evaluate_pending_fault',domain,bad!=r['stage'],'SAT'


def concrete_reference(se,sig,insn,sw,tag,cw):
    e=se&0x7fff;j=bool(sig&(1<<63));q=bool(sig&(1<<62));occupied=bool(tag&(1<<((sw>>11)&7)))
    m=cw&63;p=bool((sw&63)&~m)
    if cw&0x300==0x100:return 'RESERVED_PC'
    if sw&0x8080!=(0x8080 if p else 0):return 'INCOHERENT_SUMMARY'
    invalid=not occupied or bool(e and not j) or (e==0x7fff and not q)
    d=occupied and not e and sig!=0
    early=(invalid and not m&1) or (d and not m&2)
    return 'pending' if p else 'early' if early else 'masked_empty' if not occupied else 'number'


def runtime_checks():
    classes=((0,0),(0,1),(0,(1<<63)+1),(1,0),(0x7fff,1<<63),
        (0x7fff,(1<<63)+1),(0x7fff,3<<62),(0x3ffd,1<<63),(0x403e,1<<63))
    counts=Counter();stamp=hashlib.sha256()
    for se,sig in classes:
        for occupied in (0,1):
            for insn in ('fsin','fcos'):
                for mask in range(64):
                    for flags in range(64):
                        for pc in (0,0x100,0x200,0x300):
                            rc=(mask^flags)&3;top=(mask+flags)&7
                            tag=0xff if occupied else 0xff^(1<<top)
                            cw=0x40|mask|pc|(rc<<10)
                            sw=(top<<11)|flags|(0x4700 if mask&1 else 0)|(0x40 if flags&1 else 0)
                            if flags&~mask:sw|=0x8080
                            # Coherent support plus an explicitly inconsistent
                            # summary alternative. Neither is a hardware trial.
                            for status in (sw,sw^0x80):
                                wanted=concrete_reference(se,sig,insn,status,tag,cw)
                                try:got=actual.plan(se,sig,insn,before_status=status,before_tag=tag,control_word=cw)
                                except NotImplementedError as error:
                                    got='RESERVED_PC' if 'precision' in str(error) else 'INCOHERENT_SUMMARY'
                                assert got==wanted,(se,sig,insn,status,tag,cw,got,wanted)
                                counts[got]+=1;stamp.update((got+'\n').encode())
    return dict(rows=sum(counts.values()),counts=dict(counts),outcome_sha256=stamp.hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    args=p.parse_args();root,out=args.root.resolve(),args.output_dir.resolve();assert not out.exists()
    for name,sha in LOCKS.items():assert digest(root/name)==sha,name
    classifier,planner=functions(root)
    out.mkdir(parents=True);qdir=out/'queries';qdir.mkdir()
    save(out/'source_AST.json',{name:ast.dump(node,include_attributes=False) for name,node in (('classify',classifier),('plan',planner))})
    results=[]
    for name,domain,error,wanted in queries(classifier,planner):
        row=solve(name,'QF_BV',domain,error,qdir,10000);row['expected']=wanted;results.append(row)
    save(out/'solver_results.json',results)
    runtime=runtime_checks();save(out/'runtime.json',runtime)
    v,_=symbols();compiler=RestrictedAST(classifier,planner);_,leaves=compiler.compile('plan',v)
    report=dict(experiment='h1704_stage_predicate_certificate',status='PASS_CONDITIONAL_STAGE_CERTIFICATE' if all(r['z3']==r['cvc5']==r['expected'] for r in results) else 'UNRESOLVED_OR_FAILED',
        queries=len(results),solver_counts=dict(z3=dict(Counter(r['z3'] for r in results)),cvc5=dict(Counter(r['cvc5'] for r in results))),
        solvers=dict(z3=z3.get_version_string(),cvc5=cvc5.__version__),runtime=runtime,
        translation=dict(word_bits=WIDTH,plan_return_paths=len(leaves),node_counts=dict(compiler.nodes),input_bits=121,
            complement_argument='The sole invert is masks inside before_status & ~masks &63. Nonnegative bounded before_status removes every high complement bit; low128 complement equals Python unbounded complement. All other values/shifts fit128, including the assertion constant2^64.',
            syntax_scope='Actual classify/plan AST only; unsupported syntax fails. Boolean and/or occur as predicates, supported calls are bool and raw.classify. String identities are injectively encoded; comparisons never mix string and numeric domains.'),
        boundary='Whole121-bit planner-input space, including explicit PC/summary rejection, conditional on the restricted AST translator and bitvector justification. Not a general Python verifier, numerical kernel proof, all-state/physical behavior theorem or supported-control expansion. Writeback/wrapped results additionally assume H1702/H1703 numerical/state contracts.',
        hardware_execution='none',private_ledger_access='none',new_labels_opened=False,production_default_or_paper_change=False,
        sha256=dict(script=digest(Path(__file__)),evidence=LOCKS,source_AST=digest(out/'source_AST.json'),solver_results=digest(out/'solver_results.json')))
    save(out/'report.json',report)
    print(json.dumps({k:report[k] for k in ('status','queries','solver_counts','runtime')}),flush=True)


if __name__=='__main__':main()

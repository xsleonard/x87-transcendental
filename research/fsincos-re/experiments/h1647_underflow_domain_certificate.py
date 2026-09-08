#!/usr/bin/env python3
"""All-input underflow-domain enclosure for the fixed numerical program.

Uses exact rational interval bounds, not sampled inputs or hardware labels.
It proves a property of H1630/H1633/H1638, NOT that silicon implements those
programs or generates flags by inspecting their rounded output.
"""
from __future__ import annotations
import argparse
from fractions import Fraction as F
from pathlib import Path
import h1636_retained_rz_pc_transfer as independent
from h1640_remaining_scope_freshness import save

LOCKS={
    'src/p5_rom_constants.h':'2189e0063c913ee4004e09c8b80cb17afb16c95715ea579854e152088bbfce97',
    'experiments/h1630_shared_polynomial.h':'5c279565bf3ab5b1a02d92a24fb2e40dc3b12ab23498522768118890cf5c5310',
    'experiments/h1633_shared_table.h':'238ee52346049bbb292cb43958c01f8f1ddae20e4d3fad004bf74423f6dae66b',
    'experiments/h1638_tiny_closed_form.h':'910cbb03c7310ad86b77bce4ae64fd611d96374c794df0048922b7dc2f199227',
    'experiments/h1634_independent_table_certificate.py':'41393ef2dd4fc42ff4d047b8fae87af529f9cb51e2ef784a78bf7ddc1a20cefa',
    'experiments/h1636_retained_rz_pc_transfer.py':'9d44c92b5c6267752da7bab906e160ae82bb1eda338f93c86c8e7732adb45707',
}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path); p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(); root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists()
    digest=independent.proof.digest
    for name,sha in LOCKS.items(): assert digest(root/name)==sha,name
    independent.initialize_proof(root)
    c,table=independent.proof.C,independent.proof.TABLE
    assert all(abs(v)<1 for values in c.values() for v in values.values())
    assert all(F(1,4)<v<1 for pair in table.values() for v in pair)
    # RN64 magnitude grows by at most 1+2^-64; final directed/nearest64
    # magnitude is at least 1-2^-63 times the exact positive prevalue, while
    # the exponent is unbounded. Deliberately looser fractions simplify proof.
    rho,eta=F(65,64),F(63,64)
    assert rho>1+F(1,1<<64) and eta<1-F(1,1<<63)
    s=F(1,16); f=s*s
    np=rho*(1+f*rho*(1+f))
    assert np<F(9,8)
    correction=(s+f)*np
    sine_correction=rho*correction
    assert correction<F(1,8) and sine_correction<F(1,8)
    cos_lower=eta*(1-correction)
    sin_relative_lower=eta*(1-sine_correction)
    assert cos_lower>F(1,2) and sin_relative_lower>F(1,2)
    polynomial_min=sin_relative_lower*F(1,1<<32)
    assert polynomial_min>F(1,1<<33)
    offset=F(1,16); ts=offset*offset
    horner=rho*(1+ts*rho*(1+ts*rho*(1+ts)))
    assert horner<F(9,8)
    v=rho*offset*(1+ts*horner)
    w=rho*ts*horner  # Direct RN64 product, not RN64(CHOP67(product)).
    delta=v+w
    assert delta<F(1,8)
    table_pre=F(1,4)-delta
    table_final=eta*table_pre
    assert table_pre>F(1,8) and table_final>F(1,16)
    # Direct non-bypass r>=2^-68; reduced r=|D|*2^-65 has integer |D|>=1.
    # pred64(r)>=r/2 even at a binade boundary. Cosine's leading value is1.
    tiny_direct=F(1,1<<69); tiny_reduced=F(1,1<<66)
    min_normal=F(1,1<<16382)
    assert min(polynomial_min,table_final,tiny_direct,tiny_reduced)>min_normal
    # M66's odd 66-bit significand cannot divide a nonzero 64-bit
    # significand times a power of two; exact reduced zero is unreachable.
    m=independent.proof.M66
    assert m&1 and m.bit_length()==66
    out.mkdir(parents=True)
    bounds=dict(rho=rho,eta=eta,polynomial_NP_abs=np,cosine_correction_abs=correction,
        sine_relative_correction_abs=sine_correction,cosine_polynomial_lower=cos_lower,
        sine_polynomial_relative_lower=sin_relative_lower,table_horner_abs=horner,
        table_v_abs=v,table_w_abs=w,table_delta_abs=delta,table_final_lower=table_final,
        direct_tiny_nonbypass_lower=tiny_direct,reduced_tiny_lower=tiny_reduced)
    report=dict(experiment='h1647_underflow_domain_certificate',status='PASS_EXACT_INTERVAL_CERTIFICATE',
        bounds={k:str(v) for k,v in bounds.items()},
        conclusion='For valid nonzero finite in-range inputs, only original true-denormal FSIN can have a subnormal numerical output. Every other arithmetic path is bounded away from zero; normal/pseudo-denormal bypass outputs remain normal. Zero inputs and exceptional/range responses are separate.',
        scope='All inputs of the specified fixed numerical graph, conditional on its already-stated dispatcher/grid/width semantics. This is not an all-input silicon proof, physical flag-generator recovery or unmasked-underflow specification.',
        hardware_execution='none',hardware_labels_read='none',paper_or_default_change='none',
        sha256=dict(script=digest(Path(__file__)),evidence=LOCKS))
    save(out/'report.json',report)
    print(report['status'],flush=True)


if __name__=='__main__': main()

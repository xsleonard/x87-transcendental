#!/usr/bin/env python3
"""Exact interval certificate for the fixed tiny/polynomial numerical join.

The universal part is an analytic enclosure with exact rational endpoints,
not an exhaustive sample of external inputs and not a silicon proof. A
separate finite software replay checks implementation wiring in four existing
isolated builds. The external exponent < -68 bypass is deliberately separate.
No hardware, new selector, production/default change, or paper edit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
import h1636_retained_rz_pc_transfer as independent
import h1637_tiny_closed_form_audit as tiny
import h1638_tiny_c_transfer as transfer
from h1640_remaining_scope_freshness import save

PARENT = 'tmp/ledger33/current/h1638_tiny_c_transfer/'
LOCKS = {
    'src/fsincos_skylake.c': '0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b',
    'src/p5_rom_constants.h': '2189e0063c913ee4004e09c8b80cb17afb16c95715ea579854e152088bbfce97',
    'experiments/h1630_shared_polynomial.h': '5c279565bf3ab5b1a02d92a24fb2e40dc3b12ab23498522768118890cf5c5310',
    'experiments/h1638_tiny_closed_form.h': '910cbb03c7310ad86b77bce4ae64fd611d96374c794df0048922b7dc2f199227',
    'experiments/h1634_independent_table_certificate.py': '41393ef2dd4fc42ff4d047b8fae87af529f9cb51e2ef784a78bf7ddc1a20cefa',
    'experiments/h1636_retained_rz_pc_transfer.py': '9d44c92b5c6267752da7bab906e160ae82bb1eda338f93c86c8e7732adb45707',
    'experiments/h1637_tiny_closed_form_audit.py': 'ea6e22d450dda2d5046d1ed309d971b2d50a8434cc5b934b7413995c81ebf0f2',
    PARENT + 'report.json': 'db6c8cbc1e0e2c9acdb54da5e1e381407a6b8c5f6f62cc7b1c52c4d90f8510e0',
}
proof = independent.proof


def certificate():
    """Check every rational inequality used by the universal proof below."""
    # Normalized unbounded-exponent T67 does not annihilate a nonzero value:
    # eta*|x| <= |T67(x)| <= |x|. RN64 preserves sign and grows magnitude
    # by at most rho. These deliberately loose constants follow from the
    # usual relative-error bounds, including binade transitions.
    rho, eta = F(65, 64), F(63, 64)
    assert rho > 1 + proof.p2(-64) and eta < 1 - proof.p2(-66)
    smax = proof.p2(-64)  # 0 < S=M(r,r) <= r^2 <= 2^-64.
    fmax = smax * smax  # 0 < F=M(S,S) <= S^2, even with Y64 cutting.
    inner_bound = rho * (1 + fmax)
    assert inner_bound < 2
    perturb = 2 * fmax
    fixed = {}
    for kind in ('S6', 'C6'):
        c = proof.C[kind]
        assert all(abs(v) < 1 for v in c.values())
        fixed[kind] = {}
        for k in (1, 2):
            # Inner A(K3,M(F,K5)) or A(K4,M(F,K6)) has magnitude <2.
            # Thus the outer coefficient perturbation is in [-2F,+2F].
            # RN64 is monotone; equal rounded interval endpoints prove a
            # constant result throughout the interval, not only at samples.
            value = proof.rnd(c[k], 64, 'rn')[0]
            assert proof.rnd(c[k] - perturb, 64, 'rn')[0] == value
            assert proof.rnd(c[k] + perturb, 64, 'rn')[0] == value
            fixed[kind][k] = value
    ns, ps = fixed['S6'][1], fixed['S6'][2]
    nc, pc = fixed['C6'][1], fixed['C6'][2]
    assert -F(1, 4) < ns < -F(1, 8) and 0 < ps < 1 and 0 < pc < 1
    assert proof.C['C6'][1] == -F(1, 2) + proof.p2(-67)
    assert nc == -F(1, 2)  # Rounded Horner N, NOT the stored coefficient.
    # Sine: |L|=|T67(S*Ns)| >= eta*S/8 and |L|<S/4;
    # 0<R=T67(F*Ps)<S^2<eta*S/8. Therefore L+R<0.
    assert smax < eta / 8
    # h=RN64(L+R) is negative and |h|<rho*S/4<S/3.
    # delta_s=-M(r,h) is positive and <r^3/3<=r*2^-64/3.
    assert rho / 4 < F(1, 3)
    assert smax / 3 < proof.p2(-65)
    # For any positive exact64 leading r, pred64 spacing is >=r*2^-64
    # (equality at a power of two). Hence delta_s is below HALF that spacing.
    # Cosine: L=M(S,-1/2)=-S/2 exactly (S has at most67 bits).
    # 0<R<S^2<S/2, so 0<delta_c=-T67(L+R)<S/2<=2^-65.
    assert smax < F(1, 2) and smax / 2 == proof.p2(-65)
    # The cosine bound is STRICT even at r=2^-32 because R is positive.
    # Half of the predecessor gap below leading1 is exactly2^-65.
    return dict(
        domain='2^-68 <= r <= 2^-32, positive dyadic r with <=64 significant bits; either result sign and all four final RC modes',
        arithmetic='M(x,y)=T67(T67(x)*T64(y)); A(x,y)=RN64(x+y); unbounded normalized exponent; pinned H1630/H1634 graph',
        exact_bounds={k: str(v) for k, v in dict(rho=rho, eta=eta,
            S_upper=smax, F_upper=fmax, inner_abs_upper=inner_bound,
            outer_coefficient_perturbation_abs=perturb,
            sine_relative_delta_upper=smax / 3,
            leading_half_gap_relative_lower=proof.p2(-65),
            cosine_delta_strict_upper=smax / 2).items()},
        constant_horner_values={kind: {str(k): str(v) for k, v in c.items()}
                               for kind, c in fixed.items()},
        sine='0 < r-pre_s < r^3/3 <= r*2^-64/3 < half the pred64(r) gap',
        cosine='0 < 1-pre_c < S/2 <= 2^-65 = half the pred64(1) gap; strictness uses R>0',
        conclusion='RN or away from zero selects the exact leading value with C1=1; toward zero selects its predecessor with C1=0. The existing tiny rule and counterfactual polynomial agree, including the polynomial-side endpoint r=2^-32.',
        interface='Direct non-bypass tiny inputs have r>=2^-68 and <=64 bits. Reduced nonzero tiny r=|D|*2^-65 has >=2^-65 and <=33 bits. Exact sign/quadrant routing supplies the result sign. Zero and external exponent<-68 bypass are NOT replaced.',
        proof_boundary='Exact rational interval/rounding argument for the fixed numerical graph. Not a proof of physical coefficients, all-input silicon equivalence, finite-limb C semantics, flags, or full architectural state.')


def leading_rule(r, cosine, negative, mode):
    leading = F(1) if cosine else r
    e = proof.top(leading)
    sig = int(leading / proof.p2(e - 63))
    assert leading == sig * proof.p2(e - 63) and 1 << 63 <= sig < 1 << 64
    toward = mode == 'rz' or (mode == 'rd' and not negative) or (mode == 'ru' and negative)
    if toward:
        if sig > 1 << 63:
            sig -= 1
        else:
            sig, e = (1 << 64) - 1, e - 1
    return tiny.normal(negative, e, sig), int(not toward)


def software_bank():
    # Every normalization exponent in the active overlap, significand edges,
    # single-bit runs and deterministic interior points. No hardware labels.
    sigs = {1 << 63, (1 << 63) + 1, (1 << 64) - 2, (1 << 64) - 1}
    for bit in range(1, 63):
        sigs.update(((1 << 63) | (1 << bit), (1 << 64) - (1 << bit)))
    state = 0x1686C105ED
    for _ in range(64):
        state = (state * 6364136223846793005 + 1442695040888963407) % (1 << 64)
        sigs.add(state | (1 << 63))
    magnitudes = {sig * proof.p2(e - 63) for e in range(-68, -32) for sig in sigs}
    magnitudes.add(proof.p2(-32))
    return sorted(magnitudes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.output_dir.resolve()
    assert not out.exists()
    evidence = dict(LOCKS)
    evidence['experiments/h1638_tiny_c_transfer.py'] = proof.digest(root / 'experiments/h1638_tiny_c_transfer.py')
    for name, expected in evidence.items():
        assert proof.digest(root / name) == expected, name
    independent.initialize_proof(root)
    theorem = certificate()
    magnitudes = software_bank()
    counts = Counter()
    cases, checksum = [], hashlib.sha256()
    for r in magnitudes:
        assert proof.p2(-68) <= r <= proof.p2(-32) and proof.precision(r) <= 64
        for cosine in (0, 1):
            pre = proof.polynomial_graph(r, cosine)
            lead = F(1) if cosine else r
            gap = proof.p2(proof.top(lead) - (64 if proof.precision(lead) == 1 else 63))
            assert 0 < lead - pre < gap / 2
            counts['sampled_graph_prevalue_enclosures'] += 1
            for negative in (0, 1):
                for mode in ('rn', 'rd', 'ru', 'rz'):
                    got = proof.final(pre, negative, mode)
                    expected = leading_rule(r, cosine, negative, mode)
                    assert got == expected
                    counts['sampled_graph_output_C1_checks'] += 1
                    checksum.update(f'{r} {cosine} {negative} {mode} {got}\n'.encode())
        e = proof.top(r)
        sig = int(r / proof.p2(e - 63))
        for sign in (0, 1):
            cases.append((tiny.normal(sign, e, sig).replace(':', ' '), r, sign))
    print('INTERVAL AND GRAPH PASS', dict(counts), flush=True)
    # These are the already-built isolated candidate programs. No original
    # source is edited and no new binary or capture is dispatched remotely.
    parent = json.loads((root / PARENT / 'report.json').read_text())
    binaries = {}
    for label in ('candidate_O0', 'candidate_O2', 'candidate_O3', 'candidate_ubsan'):
        path = root / PARENT / label
        assert proof.digest(path) == parent['sha256']['binaries'][label]
        binaries[label] = path
    operands = [row[0] for row in cases]
    for instruction in ('fsin', 'fcos'):
        cosine = int(instruction == 'fcos')
        for mode in ('rn', 'rd', 'ru', 'rz'):
            for label, binary in binaries.items():
                values, metadata, _ = transfer.run(binary, instruction, mode, operands)
                assert len(metadata) == len(cases)
                for i, (operand, r, sign) in enumerate(cases):
                    meta = metadata[i]
                    negative = 0 if cosine else sign
                    assert (values[i], meta['C1']) == leading_rule(r, cosine, negative, mode)
                    assert meta['lane'] == ('polynomial' if r == proof.p2(-32) else 'tiny')
                    assert not meta.get('bypass', 0)
                    counts['four_build_active_dispatch_output_C1_checks'] += 1
            print(instruction, mode, 'FOUR BUILDS PASS', flush=True)
    # Negative control: extending the polynomial through the external bypass
    # would change C1 or directed results. Those differences are expected,
    # not new candidate misses or permission to remove the bypass.
    controls = []
    for instruction in ('fsin', 'fcos'):
        for sign in (0, 1):
            op = tiny.normal(sign, -69, 1 << 63).replace(':', ' ')
            for mode in ('rn', 'rd', 'ru', 'rz'):
                bypass = tiny.evaluate(op, instruction, mode)
                assert 'bypass' in bypass['path']
                extended = leading_rule(proof.p2(-69), int(instruction == 'fcos'),
                                        sign if instruction == 'fsin' else 0, mode)
                assert extended != (bypass['output'], bypass['C1'])
                controls.append(dict(operand=op, instruction=instruction, mode=mode,
                    existing_bypass=[bypass['output'], bypass['C1']],
                    rejected_universal_extension=list(extended)))
    counts['bypass_extension_negative_controls'] = len(controls)
    out.mkdir(parents=True)
    save(out / 'software_operands.json', operands)
    save(out / 'bypass_negative_controls.json', controls)
    report = dict(experiment='h1686_tiny_polynomial_join',
        status='PASS_EXACT_MODEL_JOIN_AND_FINITE_C_REPLAY', certificate=theorem,
        counts=dict(counts), distinct_magnitudes=len(magnitudes),
        software_external_operands=len(operands), graph_replay_sha256=checksum.hexdigest(),
        sampling_role='Implementation/regression check only; the interval argument, not the sample size, establishes the model join.',
        C_replay_scope='Existing default-off C builds execute their actual tiny dispatcher below2^-32 and actual polynomial at2^-32. Counterfactual polynomial below the threshold is evaluated only by the pinned rational graph, not forced into C.',
        hardware_execution='none', hardware_labels_read='none', private_ledger_access='none',
        new_candidate_misses=0, paper_or_default_change='none',
        sha256=dict(script=proof.digest(Path(__file__)), evidence=evidence,
            binaries={k: proof.digest(v) for k, v in binaries.items()},
            artifacts={p.name: proof.digest(p) for p in sorted(out.iterdir())}))
    save(out / 'report.json', report)
    print(report['status'], dict(counts), flush=True)


if __name__ == '__main__':
    main()

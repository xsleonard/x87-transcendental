#!/usr/bin/env python3
"""Analysis-only FSIN/FCOS exception staging; no emulator default is changed.

The optional condition write mask is retrospective H1649 evidence, not a
universal silicon law. Unmasked rules are manual-derived hypotheses awaiting
prospective capture. Underflow's wrapped endpoint is deliberately unresolved:
scaling an already rounded masked answer is not generally a valid derivation.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
import h1645_masked_status_model as base


@dataclass(frozen=True)
class Transition:
    encoding_class: str
    output: str | None
    response: str
    delivery: str
    new_exception_flags: int
    C1: int | None
    C2: int | None
    status_bits: int
    status_known_mask: int
    physical_abridged_tag: int
    top: int

    def agrees_with_status(self, sw: int) -> bool:
        return ((sw ^ self.status_bits) & self.status_known_mask) == 0


def masked(se, sig, instruction, *, experimental_condition_mask=False, **kwargs):
    result = base.masked(se, sig, instruction, **kwargs)
    # Zero and infinity had no H1649 observation. Do not silently broaden the
    # empirical write-mask coverage to them just because their paths look alike.
    if not experimental_condition_mask or result.encoding_class in ('zero', 'infinity'):
        return result
    before = kwargs.get('before_status', 0x3800)
    return replace(result, C1=0 if result.C1 is None else result.C1,
                   C2=0 if result.C2 is None else result.C2,
                   status_bits=result.status_bits | (before & 0x4100),
                   status_known_mask=0xffff)


def wrapped_underflow_alternatives(se, sig, instruction, mode):
    """Discriminator endpoints only: do not select one from observed labels."""
    assert instruction == 'fsin' and mode in ('rn', 'rd', 'ru', 'rz')
    assert base.classify(se, sig) == 'denormal'
    shift = 64 - sig.bit_length()
    significand, exponent = sig << shift, 1 - shift + 24576
    assert base.B63 <= significand < 1 << 64 and 0 < exponent < 0x7fff
    biased = f'{(se & 0x8000) | exponent:04x}:{significand:016x}'
    if significand == base.B63:
        predecessor_sig, predecessor_exp = (1 << 64) - 1, exponent - 1
    else:
        predecessor_sig, predecessor_exp = significand - 1, exponent
    predecessor = f'{(se & 0x8000) | predecessor_exp:04x}:{predecessor_sig:016x}'
    toward_zero = mode == 'rz' or (mode == 'rd' and not se & 0x8000) or (mode == 'ru' and se & 0x8000)
    return dict(retain_masked_input=f'{se:04x}:{sig:016x}', scale_input=biased,
                scale_then_leading_or_predecessor=predecessor if toward_zero else biased)


def transition(se, sig, instruction, *, finite_output=None, finite_C1=None,
               before_status=0x3800, before_tag=0x80, control_word=0x037f,
               experimental_condition_mask=False):
    assert instruction in ('fsin', 'fcos')
    assert 0 <= se < 1 << 16 and 0 <= sig < 1 << 64
    assert 0 <= before_status < 1 << 16 and 0 <= before_tag < 1 << 8
    assert 0 <= control_word < 1 << 16
    if control_word & 0x300 == 0x100:
        raise NotImplementedError('Reserved precision control is not recovered')
    masks = control_word & 0x3f
    pending = bool(before_status & ~masks & 0x3f)
    summary = 0x8080 if pending else 0
    if before_status & 0x8080 != summary:
        raise NotImplementedError('Incoherent ES/B/flags/masks need a separate FXRSTOR discriminator')
    top = (before_status >> 11) & 7
    cls = base.classify(se, sig) if before_tag & (1 << top) else 'empty_stack'
    encoded = f'{se:04x}:{sig:016x}'
    if pending:
        # Waiting-instruction check precedes all operand classification effects.
        # No arithmetic is attempted and no prior instruction is re-executed.
        return Transition(cls, encoded, 'MF_BEFORE', 'at_instruction', 0,
                          (before_status >> 9) & 1, (before_status >> 10) & 1,
                          before_status, 0xffff, before_tag, top)
    invalid = cls in ('empty_stack', 'unsupported', 'infinity', 'signaling_nan')
    denormal = cls in ('denormal', 'pseudo_denormal')
    early = 1 if invalid and not masks & 1 else 2 if denormal and not masks & 2 else 0
    if early:
        # A pre-computation fault never commits the masked QNaN/normalization.
        # Only stack underflow has a predeclared C1=0 here; other CC are unknown.
        sf = (before_status & 0x40) | (0x40 if cls == 'empty_stack' else 0)
        bits = (top << 11) | (before_status & 0x3f) | sf | early | 0x8080
        known = 0xffff ^ 0x4700
        c1 = None
        if cls == 'empty_stack':
            known |= 0x200
            c1 = 0
        return Transition(cls, encoded, 'MF_AFTER', 'at_next_wait', early,
                          c1, None, bits, known, before_tag, top)
    normal = masked(se, sig, instruction, finite_output=finite_output,
                    finite_C1=finite_C1, before_status=before_status,
                    before_tag=before_tag, control_word=control_word | 0x3f,
                    experimental_condition_mask=experimental_condition_mask)
    triggered = normal.new_exception_flags & ~masks & 0x3f
    assert not triggered & 0x0f
    if triggered & 0x10:
        # H1647 confines this branch in the fixed graph to true-denormal FSIN.
        # The manual prescribes exponent wrapping before final storage, but the
        # transcendental's internal unmasked prevalue has not been recovered.
        assert cls == 'denormal' and instruction == 'fsin'
        bits = (normal.status_bits & ~0x4700) | 0x8080
        return Transition(cls, None, 'MF_AFTER', 'at_next_wait', normal.new_exception_flags,
                          None, None, bits, 0xffff ^ 0x4700,
                          normal.physical_abridged_tag, top)
    return Transition(cls, normal.output, 'MF_AFTER' if triggered else normal.response,
                      'at_next_wait' if triggered else 'none', normal.new_exception_flags,
                      normal.C1, normal.C2, normal.status_bits | (0x8080 if triggered else 0),
                      normal.status_known_mask, normal.physical_abridged_tag, top)

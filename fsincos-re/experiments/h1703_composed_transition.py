#!/usr/bin/env python3
"""Default-off composition of the numerical candidate and partial state model.

No hardware, input-output fitting or implicit completion of unknown state.
The backend computes the existing numerical graph; its C2 return and masked
endpoint must not be confused with architectural writeback or wrapped output.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import h1645_masked_status_model as raw
import h1660_scalar_state_completion as state

MODES = ('rn', 'rd', 'ru', 'rz')


@dataclass(frozen=True)
class Number:
    response: str
    output: str | None
    C1: int | None


@dataclass(frozen=True)
class Composed:
    transition: state.prior.Transition
    numerical_requested: bool
    number: Number | None
    writeback: bool
    commit_kind: str


def plan(se, sig, instruction, *, before_status, before_tag, control_word):
    assert instruction in ('fsin', 'fcos')
    assert 0 <= se < 1 << 16 and 0 <= sig < 1 << 64
    assert 0 <= before_status < 1 << 16 and 0 <= before_tag < 1 << 8 and 0 <= control_word < 1 << 16
    if control_word & 0x300 == 0x100:
        raise NotImplementedError('Reserved precision control remains unresolved')
    masks = control_word & 63
    pending = bool(before_status & ~masks & 63)
    if before_status & 0x8080 != (0x8080 if pending else 0):
        raise NotImplementedError('Incoherent ES/B/flags/masks remain outside the state contract')
    top = (before_status >> 11) & 7
    cls = raw.classify(se, sig) if before_tag & (1 << top) else 'empty_stack'
    if pending:
        return 'pending'
    invalid = cls in ('empty_stack', 'unsupported', 'infinity', 'signaling_nan')
    denormal = cls in ('denormal', 'pseudo_denormal')
    if (invalid and not masks & 1) or (denormal and not masks & 2):
        return 'early'
    if cls == 'empty_stack':
        return 'masked_empty'
    return 'number'


def compose(se, sig, instruction, backend: Callable[[int, int, str, str], Number], *,
            before_status=0x3800, before_tag=0x80, control_word=0x037f, enabled=False):
    if not enabled:
        raise NotImplementedError('H1703 is an explicitly enabled analysis-only composition')
    context = dict(before_status=before_status, before_tag=before_tag, control_word=control_word)
    stage = plan(se, sig, instruction, **context)
    encoded = f'{se:04x}:{sig:016x}'
    number = None
    if stage == 'number':
        number = backend(se, sig, instruction, MODES[(control_word >> 10) & 3])
        assert isinstance(number, Number) and number.response in ('OK', 'C2')
        assert number.C1 in (None, 0, 1)
        assert (number.output is None) == (number.response == 'C2')
    result = state.transition(se, sig, instruction, enabled=True,
        finite_output=number.output if number else None, finite_C1=number.C1 if number else None, **context)
    if stage in ('pending', 'early'):
        assert result.output == encoded and result.physical_abridged_tag == before_tag
        assert result.delivery == ('at_instruction' if stage == 'pending' else 'at_next_wait')
        return Composed(result, False, None, False, 'none')
    if stage == 'masked_empty':
        assert result.output == raw.INDEFINITE
        return Composed(result, False, None, True, 'masked_empty')
    assert number is not None
    if number.response == 'C2':
        assert result.encoding_class == 'normal_out_of_range'
        assert result.response == 'C2' and result.output == encoded and not result.new_exception_flags
        return Composed(result, True, number, False, 'none')
    assert result.response != 'C2'
    wrapped = result.delivery == 'at_next_wait' and bool(result.new_exception_flags & ~control_word & 0x10)
    if wrapped:
        # H1659 supplies a separate input-scaled endpoint. This is NOT a
        # generic derivation from rounding/scaling the masked C result.
        assert result.encoding_class == 'denormal' and instruction == 'fsin'
        assert number.output == encoded and number.C1 == 0
        assert result.output == state.underflow.scaled_denormal(se, sig)
        return Composed(result, True, number, True, 'wrapped_underflow')
    assert result.output == number.output
    return Composed(result, True, number, True, 'ordinary')

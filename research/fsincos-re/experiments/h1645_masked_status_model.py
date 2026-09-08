#!/usr/bin/env python3
"""Analysis-only, encoding-class masked-status algebra for FSIN/FCOS.

This is NOT a complete physical-state emulator. Unknown condition bits are
explicit masks, never guessed zero/preserved. Unmasked/pending exception and
reserved-PC paths reject the call. Normal arithmetic is supplied by the fixed
H1638 numerical graph, not an operand ledger. No default or paper change.
"""
from __future__ import annotations
from dataclasses import dataclass

B63=1<<63
Q=1<<62
INDEFINITE='ffff:c000000000000000'
ONE='3fff:8000000000000000'


def classify(se:int,sig:int)->str:
    assert 0<=se<1<<16 and 0<=sig<1<<64
    e=se&0x7fff
    if e==0:
        if sig==0: return 'zero'
        return 'pseudo_denormal' if sig&B63 else 'denormal'
    if not sig&B63: return 'unsupported'
    if e==0x7fff:
        if sig==B63: return 'infinity'
        return 'quiet_nan' if sig&Q else 'signaling_nan'
    return 'normal_in_range' if e<0x403e else 'normal_out_of_range'


def partition_counts():
    # Factor the 2^80 raw encodings by sign, exponent, explicit integer bit,
    # quiet bit, and zero/nonzero payload. No representative-count shortcut.
    return dict(zero=2,denormal=2*(B63-1),pseudo_denormal=2*B63,
        unsupported=2*0x7fff*B63,infinity=2,quiet_nan=2*Q,signaling_nan=2*(Q-1),
        normal_in_range=2*0x403d*B63,normal_out_of_range=2*(0x7ffe-0x403d)*B63)


@dataclass(frozen=True)
class Result:
    encoding_class:str
    output:str
    response:str
    new_exception_flags:int
    C1:int|None
    C2:int|None
    status_bits:int
    status_known_mask:int
    physical_abridged_tag:int
    top:int

    def agrees_with_status(self,sw:int)->bool:
        return ((sw^self.status_bits)&self.status_known_mask)==0


def masked(se:int,sig:int,instruction:str,*,finite_output:str|None=None,finite_C1:int|None=None,
           before_status:int=0x3800,before_tag:int=0x80,control_word:int=0x037f)->Result:
    assert instruction in ('fsin','fcos')
    assert 0<=before_status<1<<16 and 0<=before_tag<1<<8 and 0<=control_word<1<<16
    if control_word&0x3f!=0x3f:
        raise NotImplementedError('Unmasked exceptions require separate pre/post-computation handling')
    if control_word&0x0300==0x0100:
        raise NotImplementedError('Reserved precision control has not been recovered')
    if before_status&0x8080:
        raise NotImplementedError('Pending/error-summary or busy state is not silently normalized')
    top=(before_status>>11)&7; tag=before_tag; cls=classify(se,sig)
    encoded=f'{se:04x}:{sig:016x}'
    c1,c2=0,0; response='OK'
    if not tag&(1<<top):
        cls='empty_stack'; output=INDEFINITE; flags=1; tag|=1<<top; c2=None
    elif cls in ('unsupported','infinity'):
        output=INDEFINITE; flags=1; c2=None
    elif cls in ('quiet_nan','signaling_nan'):
        output=f'{se:04x}:{sig|Q:016x}'; flags=int(cls=='signaling_nan'); c2=None
    elif cls=='zero':
        output=ONE if instruction=='fcos' else encoded; flags=0
    elif cls=='normal_out_of_range':
        output=encoded; flags=0; response='C2'; c1=None; c2=1
    elif cls in ('denormal','pseudo_denormal'):
        output=ONE if instruction=='fcos' else f'{(se&0x8000)|(1 if sig&B63 else 0):04x}:{sig:016x}'
        # Numerical normalization must not discard original exponent==0.
        # True-denormal FSIN stays tiny; pseudo-denormals normalize to e=1.
        flags=0x22|(0x10 if cls=='denormal' and instruction=='fsin' else 0)
    else:
        assert cls=='normal_in_range'
        flags=0x20
        if (se&0x7fff)<16383-68:
            output=ONE if instruction=='fcos' else encoded
        else:
            assert finite_output is not None and finite_C1 in (0,1)
            output,c1=finite_output,finite_C1
    sf=(before_status&0x40)|(0x40 if cls=='empty_stack' else 0)
    bits=(top<<11)|(before_status&0x3f)|flags|sf
    known=0xbeff  # Do not claim physical C0/C3, including preservation.
    if c1 is None: known&=~0x0200
    else: bits|=c1<<9
    if c2 is None: known&=~0x0400
    else: bits|=c2<<10
    return Result(cls,output,response,flags,c1,c2,bits,known,tag,top)

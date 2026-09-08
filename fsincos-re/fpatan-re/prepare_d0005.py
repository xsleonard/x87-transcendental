"""Fresh architectural classes, randomized NaN payloads and invalid encodings.

Canonical both-special pairs are generated but remain subject to conservative
private/public holds. Held cases are not counted as tested. All accepted pairs
run every RC and PC once. The generic capture records before/after status.
"""
import random
from architecture import POLICY,predict
from freeze_bank import freeze

SEED='fpatan-d0005-20260905-architecture'


def generate():
    rng=random.Random(SEED)
    def pair(y,x,kind):
        for sy in (0,32768):
            for sx in (0,32768):
                yield (y[0]|sy,y[1],x[0]|sx,x[1]),kind
                yield (x[0]|sx,x[1],y[0]|sy,y[1]),kind+'-swapped'
    for _ in range(12):
        payload=rng.getrandbits(62) or 1;payload2=rng.getrandbits(62) or 1
        values={
            'zero':(0,0),'infinity':(32767,1<<63),
            'normal':(rng.randrange(1,32767),rng.getrandbits(63)|(1<<63)),
            'denormal':(0,rng.getrandbits(63) or 1),
            'pseudo':(0,rng.getrandbits(63)|(1<<63)),
            'qnan':(32767,(3<<62)|payload),'snan':(32767,(1<<63)|payload),
            'unnormal':(rng.randrange(1,32767),rng.getrandbits(63) or 1),
            'pseudo-nan':(32767,rng.getrandbits(63) or 1),
            'qnan2':(32767,(3<<62)|payload2),'snan2':(32767,(1<<63)|payload2)}
        names=list(values)
        for i,a in enumerate(names):
            for b in names[i:]:yield from pair(values[a],values[b],a+'-'+b)


if __name__=='__main__':
    freeze('d0005',SEED,generate,None,POLICY,
        ('architecture.py','graph_v3.py','graph_v4.py','prepare_d0005.py'),
        encoding_predictor=predict,mathematical_oracle=False,all_pc=True)

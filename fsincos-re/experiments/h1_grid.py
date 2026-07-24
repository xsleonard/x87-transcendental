#!/usr/bin/env python3
import subprocess, sys
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
inputs=[l.split() for l in open(f"{SCR}/sweep_inputs.txt")]
hw=[l.strip() for l in open(f"{SCR}/skylake_fsincos_out.txt")]
def path_of(se,sig):
    e=(se&0x7FFF)-16383
    if sig==0: return "zero"
    if e>=63: return "c2"
    if e>=24: return "large"
    if e>=0: return "moderate"
    if e==-1 and sig>=0xC90FDAA22168C234: return "moderate"
    if e>=-3: return "qn"
    return "qs"
qn=[(i,inp) for i,inp in enumerate(inputs) if path_of(int(inp[0],16),int(inp[1],16))=="qn"]
sub="\n".join(" ".join(inp) for _,inp in qn)+"\n"
print(f"quick-normal subset: {len(qn)}")
for mode in [0]+list(range(8,17))+[-x for x in range(8,17)]:
    out=subprocess.run(["./fsincos_ref","--batch",f"--rhi={mode}"],input=sub,capture_output=True,text=True,check=True).stdout.splitlines()
    mm=sum(1 for (i,_),o in zip(qn,out) if o.strip()!=hw[i])
    print(f"rhi={mode:4d}: mismatches {mm}/{len(qn)}")

#!/usr/bin/env python3
# Re-dump pool VIS rows with real A/B/hw values in census format.
import subprocess, collections
rows=[]
for i,l in enumerate(open("act_vis.tsv")):
    t=l.rstrip("\n").split("\t")
    if i==0 or t[5]!="VIS": continue
    rows.append(t)  # cls insn mode se sig vis match
groups=collections.defaultdict(list)
for r in rows: groups[(r[1],r[2])].append(r)
def n3(line):
    f=line.split()
    return " ".join(f[:3]) if f and f[0]=="OK" else (f[0] if f else "")
out=open("act_pool_hits.tsv","w")
for (insn,mode),g in groups.items():
    RC={"rn":[],"rd":["--rc=rd"],"ru":["--rc=ru"],"rz":["--rc=rz"]}[mode]
    FL=["--fsin-standalone"] if insn=="sin" else ["--fcos-standalone"]
    inp="".join(r[3]+" "+r[4]+"\n" for r in g)
    A=subprocess.run(["./model_payA","--batch"]+RC+FL,input=inp,capture_output=True,text=True).stdout.splitlines()
    B=subprocess.run(["./model_payB","--batch"]+RC+FL,input=inp,capture_output=True,text=True).stdout.splitlines()
    HW=subprocess.run(["/root/x87_capture_x86_64",mode,insn],input=inp,capture_output=True,text=True).stdout.splitlines()
    for r,a,b,h in zip(g,A,B,HW):
        lab={"A":"PAYLOAD","B":"NOPAYLOAD"}.get(r[6],"OTHER")
        out.write("\t".join((lab,"pool",insn,mode,"0",r[3]+" "+r[4],n3(a),n3(b),n3(h)))+"\n")
out.close()
print("wrote act_pool_hits.tsv with values")

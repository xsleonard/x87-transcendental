"""Execute raw x87 state witnesses as real guest instructions in adapted Bochs.

Builds a 64 KiB test ROM with Clang's i386 assembler, boots it, observes FXSAVE
and #MF inside the guest, and checks results against supplied evidence. It does
not execute native host x87 instructions or use Bochs as a numerical oracle.
"""
import argparse
import gzip
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile

OPS=('fsin','fcos','fsincos','fptan','f2xm1','fpatan','fyl2x','fyl2xp1')


def rom(cases,directory,clang):
    dispatch='\n'.join(f'cmpb ${i}, %al\nje op_{op}' for i,op in enumerate(OPS))
    operations='\n'.join(f'op_{op}:\n{op}\nret' for op in OPS)
    records=[]
    for case in cases:
        data=bytes.fromhex(case['before'])
        assert len(data)==512
        # MXCSR is unrelated to the x87 witness, but FXRSTOR needs a valid one.
        data=bytearray(data);data[24:28]=struct.pack('<I',0x1f80)
        records.append('.byte '+','.join(map(str,[OPS.index(case['op']),*([0]*15),*data])))
    source=r'''.code16
.text
start:
cli
cld
movw $0x2000,%ax
movw %ax,%ss
movw $0xfff0,%sp
xorw %ax,%ax
movw %ax,%ds
movw $(handler-start),0x40
movw $0xf000,0x42
movl %cr0,%eax
andl $0xfffffff3,%eax
orl $0x22,%eax
movl %eax,%cr0
movl %cr4,%eax
orl $0x200,%eax
movl %eax,%cr4
movw $(records-start),%bp
xorw %bx,%bx
next_case:
movw $0xf000,%ax
movw %ax,%ds
movw $0x1000,%ax
movw %ax,%es
movw %bp,%si
addw $16,%si
xorw %di,%di
movw $256,%cx
rep movsw
movw %ax,%ds
movw $0,0x800
movw $1,0x802
fxrstor 0
movb %cs:(%bp),%al
call dispatch
fxsave 0x200
movw $2,0x802
fwait
fnclex
movw $0xe9,%dx
movb $64,%al
outb %al,%dx
movb %bh,%al
call hexbyte
movb %bl,%al
call hexbyte
movb $32,%al
outb %al,%dx
movw $0x200,%di
cmpw $1,0x800
jne print_after
movw $0x400,%di
print_after:
call print_state
movb $32,%al
outb %al,%dx
movb 0x800,%al
addb $48,%al
outb %al,%dx
movb $32,%al
outb %al,%dx
cmpw $0,0x800
je no_fault
movw $0x400,%di
call print_state
jmp end_line
no_fault:
movb $45,%al
outb %al,%dx
end_line:
movb $10,%al
outb %al,%dx
addw $528,%bp
incw %bx
cmpw $CASE_COUNT,%bx
jb next_case
xchgw %bx,%bx
halt:
hlt
jmp halt
dispatch:
DISPATCH
hlt
OPERATIONS
handler:
pushw %bp
movw %sp,%bp
pushal
fxsave 0x400
movw 0x802,%ax
movw %ax,0x800
cmpw $1,%ax
jne wait_fault
addw $2,2(%bp)
jmp repair
wait_fault:
addw $1,2(%bp)
repair:
fnclex
popal
popw %bp
iret
print_state:
movw $160,%cx
print_loop:
movb (%di),%al
call hexbyte
incw %di
loop print_loop
ret
hexbyte:
pushw %ax
shrb $4,%al
call nibble
popw %ax
andb $15,%al
nibble:
cmpb $9,%al
jbe decimal
addb $87,%al
jmp emit
decimal:
addb $48,%al
emit:
outb %al,%dx
ret
.p2align 4
records:
RECORDS
.org 0xfff0
ljmp $0xf000,$0
.org 0x10000
'''.replace('CASE_COUNT',str(len(cases))).replace('DISPATCH',dispatch).replace('OPERATIONS',operations).replace('RECORDS','\n'.join(records))
    asm=directory/'guest.S';obj=directory/'guest.o';output=directory/'guest.rom'
    asm.write_text(source)
    subprocess.run([clang,'--target=i386-unknown-linux-gnu','-c',str(asm),'-o',str(obj)],check=True)
    elf=obj.read_bytes();assert elf[:5]==b'\x7fELF\x01'
    offset=struct.unpack_from('<I',elf,32)[0]
    size,count=struct.unpack_from('<HH',elf,46)
    sections=[struct.unpack_from('<10I',elf,offset+i*size) for i in range(count)]
    assert not any(s[1] in (4,9) and s[5] for s in sections),'unresolved guest relocations'
    text=[s for s in sections if s[1]==1 and s[5]==65536];assert len(text)==1
    output.write_bytes(elf[text[0][4]:text[0][4]+65536])
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bochs',type=Path)
    parser.add_argument('witnesses',type=Path,nargs='+')
    parser.add_argument('--clang',default='clang')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    directory=args.output or Path(tempfile.mkdtemp(prefix='x87trans-bochs-guests-'))
    directory.mkdir(parents=True,exist_ok=True)
    cases=[]
    for path in args.witnesses:
        raw=gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes()
        cases.extend(json.loads(raw)['cases'])
    checked=0
    for batch_at in range(0,len(cases),96):
        batch=cases[batch_at:batch_at+96]
        work=directory/f'batch-{batch_at:05d}';work.mkdir()
        image=rom(batch,work,args.clang)
        config=work/'bochsrc'
        config.write_text(f'''megs: 16
romimage: file="{image}"
vgaromimage: file="{args.bochs.resolve().parent/'bios/VGABIOS-lgpl/VGABIOS-lgpl-latest.bin'}"
display_library: nogui
cpu: model=corei7_skylake_x, ips=10000000
port_e9_hack: enabled=1
magic_break: enabled=1
log: {work/'bochs.log'}
panic: action=fatal
error: action=report
info: action=ignore
debug: action=ignore
''')
        commands=work/'commands';commands.write_text('c\nquit\n')
        process=subprocess.run([str(args.bochs.resolve()),'-q','-debugger','-f',str(config),'-rc',str(commands)],
                               capture_output=True,timeout=60)
        (work/'stdout.txt').write_bytes(process.stdout);(work/'stderr.txt').write_bytes(process.stderr)
        assert process.returncode==0,(process.returncode,str(work))
        observed=re.findall(rb'@([0-9a-f]{4}) ([0-9a-f]{320}) ([012]) ([0-9a-f]{320}|-)',process.stdout)
        assert len(observed)==len(batch),(len(observed),len(batch),str(work))
        for index,((ident,after,where,fault),case) in enumerate(zip(observed,batch)):
            assert int(ident,16)==index
            actual=bytes.fromhex(after.decode());expected=bytes.fromhex(case['after'])
            def u16(data,at):return int.from_bytes(data[at:at+2],'little')
            mask=0xB8ff|case['cc_mask']
            assert u16(actual,0)==u16(expected,0),(case['id'],'CW')
            assert (u16(actual,2)^u16(expected,2))&mask==0,(case['id'],'SW',hex(u16(actual,2)),hex(u16(expected,2)))
            assert actual[4]==expected[4],(case['id'],'FTW',actual[4],expected[4])
            for reg in range(8):
                offset=32+16*reg
                assert actual[offset:offset+10]==expected[offset:offset+10],(case['id'],'ST',reg,actual[offset:offset+10].hex(),expected[offset:offset+10].hex())
            assert int(where)==case['fault_at'],(case['id'],'delivery',where,case['fault_at'])
            if int(where):
                fault_state=bytes.fromhex(fault.decode())
                assert (u16(fault_state,2)^u16(expected,2))&mask==0,(case['id'],'fault SW')
                assert u16(fault_state,0)==u16(expected,0),(case['id'],'fault CW')
                assert fault_state[4]==expected[4],(case['id'],'fault FTW')
                for reg in range(8):
                    offset=32+16*reg
                    assert fault_state[offset:offset+10]==expected[offset:offset+10],(case['id'],'fault ST',reg)
            checked+=1
    report=dict(status='PASS',guest_instructions=checked,directory=str(directory),
                checked=['raw registers','TOP','abridged tags','flags','C1/C2','pending #MF delivery'],
                native_hardware_executed=False)
    (directory/'RESULT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()

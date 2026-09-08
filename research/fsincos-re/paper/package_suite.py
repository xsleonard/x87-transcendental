"""Stage and seal the local programmer review package from an explicit allowlist.

Original implementation files and canonical specifications are copied byte for
byte. Small release-specific entry documents and Makefiles are generated here.
Nothing is uploaded, licensed, deleted or taken from ignored model directories.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import zipfile
from suite_support import HERE, PROJECT, digest, write_json

ROOT = PROJECT.parent
DEST = ROOT / "output/release/x87-suite-review-v6"
ALLOWLIST = """
src/fsincos_skylake.c
src/fsincos_itanium.c
src/ia64_sf.h
src/p5_rom_constants.h
src/f2xm1_constants.h
src/general/standalone_polynomial.h
src/general/standalone_table.h
src/general/standalone_tiny.h
src/general/paired.h
src/test_general_paired.py
src/test_f2xm1.py
src/test_f2xm1_driver.c
src/f2xm1_regressions.json
src/test_fma_oracle.py
src/test_endtoend.py
data/frcpa-recip-table.h
data/pentium-rom/rom-constants.tsv
data/glibc-ia64-fpu/PROVENANCE.md
data/glibc-ia64-fpu/s_cosl.S
data/glibc-ia64-fpu/libm_sincosl.S
data/glibc-ia64-fpu/libm_reduce.S
fpatan-re/fpatan_candidate.c
fpatan-re/fpatan_library.c
fpatan-re/fpatan_library.h
fpatan-re/example_batch.c
fpatan-re/test_library.c
fpatan-re/Makefile
fpatan-re/PSEUDOCODE.md
fpatan-re/ALGORITHM.md
fpatan-re/DELIVERY.md
fpatan-re/ACCEPTANCE.md
fpatan-re/paper/skylake-fpatan.tex
fyl2x-re/log_model.c
fyl2x-re/log_library.c
fyl2x-re/log_library.h
fyl2x-re/model.py
fyl2x-re/protocol.py
fyl2x-re/source_audit.py
fyl2x-re/verify_archive.py
fyl2x-re/example_batch.c
fyl2x-re/example-inputs.txt
fyl2x-re/test_api.c
fyl2x-re/check_witnesses.py
fyl2x-re/witnesses.txt
fyl2x-re/witnesses.json
fyl2x-re/Makefile
fyl2x-re/README.md
fyl2x-re/ALGORITHM.md
fyl2x-re/ACCEPTANCE.md
docs/PROGRAMMER-GUIDE.md
docs/ALGORITHMS.md
docs/TRIG-PSEUDOCODE.md
docs/SIBLING-PSEUDOCODE.md
docs/sibling_reference.py
docs/sibling-constants.json
docs/verification-expansion/f2xm1-integration.md
docs/verification-expansion/rounding-boundary-audit.md
examples/unary-raw80.txt
examples/fpatan-raw80.txt
examples/fpatan_client.c
paper/x87-suite.tex
paper/suite-references.bib
paper/build_suite.py
paper/audit_trig_history.py
paper/suite_support.py
paper/verify_siblings.py
paper/verify_f2xm1_integration.py
paper/verify_fpatan_catalog.py
paper/make_smoke_witnesses.py
paper/check_witnesses.py
paper/package_suite.py
paper/EVIDENCE.md
paper/TRIG-FINDINGS.md
paper/SOURCES.md
""".split()

README = r"""# x87 transcendental models — programmer review package

The main research reconstructs **FSIN, FCOS and FSINCOS**: their distinct
standalone and paired polynomial schedules, operand widths and intermediate
rounding. The programs reproduce the tested processor's results, including
rounding that can differ from a math library. Ken Shirriff's published
Pentium ROM analysis supplies the main constants and approximation methods.[^ken]

The paper and reference are organized as three separate families:

1. **FSIN, FCOS and FSINCOS:** the main reconstruction and its evidence.
2. **FPTAN and FPATAN:** tangent and arctangent, with their own explanation.
3. **F2XM1, FYL2X and FYL2XP1:** the shorter exponential/logarithm material.

Each family keeps its algorithms, constants and validation together. The
paper explains the final calculations and how the sine/cosine rules were
derived. Development history remains in the research records. The reference
appendices follow the same order, covering all eight instructions.

## Build and run

Prerequisites: a C11 compiler with `unsigned __int128`, Make, Python 3.10+
and GMP headers/library. `pkg-config` helps locate GMP. No native x87 or
network hardware capture is used by these commands.

```sh
make
make check
fsincos-re/src/fsincos_skylake --batch --rc=rn < fsincos-re/examples/unary-raw80.txt
fsincos-re/fpatan-re/build/fpatan < fsincos-re/examples/fpatan-raw80.txt
fsincos-re/fyl2x-re/build/x87-log < fsincos-re/fyl2x-re/example-inputs.txt
```

`make check` runs the numerical self-tests, saved paired regression cases,
FPATAN/logarithm API checks and 1,578 hardware witnesses across all eight
instructions. It also evaluates 1,290 of those witnesses with independent
rational code.
An additional 216-case F2XM1 regression checks subnormal storage, direct
versus double rounding, signs, C1 and the normal/subnormal boundaries.
The separate `make check-itanium` runs the historical reference's arithmetic
and end-to-end checks. These small tests do not repeat the large archive
replays reported in the paper.

The unary example evaluates FSINCOS at +0, +0.5 and +1. Each input is a
hexadecimal sign/exponent word and explicit 64-bit significand. For normal
values,

$$x=(-1)^s S\,2^{E-16383-63}.$$

Outputs are raw80 words. After `--batch`, select `--fsin-standalone`,
`--fcos-standalone`, `--fptan` or `--f2xm1` to change the unary instruction.
`--rc=rn/rd/ru/rz` selects final rounding. FPATAN consumes ordered y,x pairs.
See [the programmer guide](fsincos-re/docs/PROGRAMMER-GUIDE.md) for exact
formats, pushed values, range returns and a complete C embedding example.

## Algorithms and paper

| Instruction | Read first |
| --- | --- |
| FSIN / FCOS | [Trig pseudocode](fsincos-re/docs/TRIG-PSEUDOCODE.md), standalone schedule |
| FSINCOS | [Trig pseudocode](fsincos-re/docs/TRIG-PSEUDOCODE.md), paired schedule |
| FPTAN | [Exact executable specification](fsincos-re/docs/SIBLING-PSEUDOCODE.md) |
| FPATAN | [Executable pseudocode](fsincos-re/fpatan-re/PSEUDOCODE.md), [C API](fsincos-re/fpatan-re/fpatan_library.h) |
| F2XM1 | [Exact executable specification](fsincos-re/docs/SIBLING-PSEUDOCODE.md) |
| FYL2X / FYL2XP1 | [Full algorithm](fsincos-re/fyl2x-re/ALGORITHM.md), [C API](fsincos-re/fyl2x-re/log_library.h) |

The [algorithm guide](fsincos-re/docs/ALGORITHMS.md) explains shared data
and instruction-specific rounding. Keep every rounding point and the order of operands when implementing them.
Using host `double` arithmetic can change the answer.

The unified [paper PDF](output/pdf/x87-suite.pdf) and
[LaTeX source](fsincos-re/paper/x87-suite.tex) include all eight
instructions, complete listings, 239 literal entries and primary references.
The sine/cosine reconstruction comes first and occupies the main discussion.
Tangent/arctangent and exponential/logarithm material have separate sections
and evidence tables, followed by reference appendices in the same order.
[Evidence](fsincos-re/paper/EVIDENCE.md) records the input sets, fields checked
and CPU used for each test. Build the paper with
`make paper` after installing Tectonic; its first run may download TeX assets.

## Scope and provenance

The package keeps the original implementation files and code comments. The
unary program has a command-line interface and uses global configuration, so
it is not ready for concurrent library calls. FPATAN and the logarithms have
separate GMP-based C APIs. Each instruction's supported inputs and status
fields are described in the guides.

The full hardware captures and research scratch directories are not included.
References to files outside this package are shown as research-archive paths.
The numerical source and full commented references are copied from the
current project. The older FPATAN paper
is kept as a historical record; use the unified paper for current results.

Licensing of original work is **undecided** at the author's request.
See [LICENSING.md](LICENSING.md) and [third-party notices](THIRD_PARTY_NOTICES.md).
This is a local review copy. It has not been published or independently
peer reviewed, and no DOI has been assigned. [CITATION.md](CITATION.md) records the
current title; attribution remains withheld pending explicit approval.

[^ken]: Ken Shirriff, [Pi in the Pentium: reverse-engineering the constants in its floating-point unit](https://www.righto.com/2025/01/pentium-floating-point-ROM.html), January 2025. See the [source register](fsincos-re/paper/SOURCES.md) for other primary material and the seven explicitly recorded literal corrections.
"""

MAKEFILE = """# Local programmer build. No capture or network execution targets.
PYTHON ?= python3
.PHONY: all check check-itanium paper
all:
	$(MAKE) -C fsincos-re/src all
	$(MAKE) -C fsincos-re/fpatan-re all
	$(MAKE) -C fsincos-re/fyl2x-re all

check: all
	fsincos-re/src/fsincos_skylake --selftest
	$(MAKE) -C fsincos-re/src check-paired-regressions
	$(MAKE) -C fsincos-re/src check-f2xm1-regressions PYTHON=$(PYTHON)
	$(MAKE) -C fsincos-re/fpatan-re check
	$(MAKE) -C fsincos-re/fyl2x-re check PYTHON=$(PYTHON)
	$(PYTHON) fsincos-re/paper/check_witnesses.py

check-itanium: all
	$(MAKE) -C fsincos-re/src test

paper:
	$(PYTHON) fsincos-re/paper/build_suite.py
"""

SOURCE_MAKEFILE = """# Curated build entry point; numerical sources are unchanged.
CC ?= cc
PYTHON ?= python3
CFLAGS ?= -O2 -Wall -Wextra -std=c11
LDLIBS ?= -lm
.PHONY: all check-paired-regressions check-f2xm1-regressions test
all: fsincos_skylake fsincos_itanium

fsincos_skylake: fsincos_skylake.c ia64_sf.h p5_rom_constants.h f2xm1_constants.h ../data/frcpa-recip-table.h general/standalone_polynomial.h general/standalone_table.h general/standalone_tiny.h general/paired.h
	$(CC) $(CFLAGS) -Wno-unused-const-variable fsincos_skylake.c $(LDLIBS) -o $@

fsincos_itanium: fsincos_itanium.c ia64_sf.h ../data/frcpa-recip-table.h
	$(CC) $(CFLAGS) fsincos_itanium.c $(LDLIBS) -o $@

# Saved hardware cases that distinguished earlier paired schedules.
check-paired-regressions: fsincos_skylake
	$(PYTHON) test_general_paired.py ./fsincos_skylake

# F2XM1 saved raw80 results exercise the integrated storage-rounding fix.
test_f2xm1_driver: test_f2xm1_driver.c fsincos_skylake.c ia64_sf.h f2xm1_constants.h p5_rom_constants.h ../data/frcpa-recip-table.h general/standalone_polynomial.h general/standalone_table.h general/standalone_tiny.h general/paired.h
	$(CC) $(CFLAGS) -Wno-unused-const-variable test_f2xm1_driver.c $(LDLIBS) -o $@

check-f2xm1-regressions: test_f2xm1_driver
	$(PYTHON) test_f2xm1.py ./test_f2xm1_driver

test: fsincos_itanium
	./fsincos_itanium --selftest
	$(PYTHON) test_fma_oracle.py ./fsincos_itanium
	$(PYTHON) test_endtoend.py ./fsincos_itanium
"""


def stage():
    if DEST.exists():
        raise SystemExit("Staging directory already exists; preserve it and choose a new destination in the script")
    files = [PROJECT / p for p in ALLOWLIST]
    files += sorted((HERE / "generated-suite").glob("*.tex")) + sorted((HERE / "generated-suite").glob("*.py"))
    files += sorted((HERE / "evidence").glob("*.json"))
    files += sorted((PROJECT / "fpatan-re/paper/generated").glob("*.tex"))
    files += [ROOT / "output/pdf/x87-suite.pdf"]
    copied = {}
    for src in files:
        assert src.is_file(),src
        relative = src.relative_to(ROOT)
        target = DEST / relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,target)
        copied[str(relative)] = digest(src)

    generated = {"README.md":README,"Makefile":MAKEFILE,"fsincos-re/src/Makefile":SOURCE_MAKEFILE,
        "LICENSING.md":"""# Licensing status

The author has chosen to leave licensing undecided for the original code,
documentation and manuscript. No project-wide license is assigned by this
local review package. This document does not grant a new license.

Existing third-party notices remain in their source files and are also
identified in THIRD_PARTY_NOTICES.md. Those notices are not replaced by a
license for the author's original work. Public distribution is a later
author decision.
""",
        "CITATION.md":'''# Citation status

Title: Reconstructing FSIN, FCOS and FSINCOS from Public Constants and Processor Tests.

Author attribution and contact details are withheld pending explicit approval.
No public identifier has been assigned. Licensing remains undecided.
''',
        "fsincos-re/paper/README.md":"""# Unified article

Read [x87-suite.tex](x87-suite.tex) or the [compiled PDF](../../output/pdf/x87-suite.pdf).
Run `make paper` from the package root to regenerate numbers, listings and PDF.
Python 3.10+ and Tectonic are required; its first build may download TeX assets.
The [evidence register](EVIDENCE.md)
and [source register](SOURCES.md) describe this local technical report.
""",
        "fsincos-re/fpatan-re/paper/README.md":"""# Earlier FPATAN manuscript

[skylake-fpatan.tex](skylake-fpatan.tex) is preserved historical source.
Its 14-campaign evidence is an earlier snapshot. Read the
[unified article](../../paper/x87-suite.tex) for the current 23-pack replay.
The [canonical specification](../PSEUDOCODE.md) is unchanged.
"""}
    original = (PROJECT / "data/glibc-ia64-fpu/s_cosl.S").read_text()
    notice = original[original.index("// Copyright"):original.index("//*********************************************************************")]
    generated["THIRD_PARTY_NOTICES.md"] = """# Third-party source material and notices

Ken Shirriff's published Pentium ROM decode is the source of the ROM rows
and algorithm explanations used here: https://www.righto.com/2025/01/pentium-floating-point-ROM.html.
The article is cited, not republished. The literal transcription preserves
row identities; the seven corrections are documented in the unified paper.

The separate Itanium model transcribes Intel's IA-64 implementation preserved
in glibc-2.38. Original assembly files, comments and notices are included under
`fsincos-re/data/glibc-ia64-fpu/`, with their pinned provenance. The Intel notice
below is reproduced verbatim from `s_cosl.S` and also applies to the included
source transcription where applicable.

```text
""" + notice + """```

The architectural reciprocal table is attributed in its source header to
Intel's IA-64 instruction reference. John Harrison's papers and public
Goldmont tools are cited as research sources; no Goldmont dump is bundled.
GMP is an external build dependency and is not redistributed in this package.
No license for the author's original work has been selected.
"""
    for name,value in generated.items():
        path=DEST / name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(value)

    # Keep canonical Markdown byte-identical; only export narrative links.
    canonical = {"fsincos-re/docs/TRIG-PSEUDOCODE.md","fsincos-re/fpatan-re/PSEUDOCODE.md"}
    changes=[]
    pattern=re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    for path in sorted(DEST.rglob("*.md")):
        relative=str(path.relative_to(DEST))
        def replace(match):
            label,target=match.groups()
            local=target.split("#",1)[0]
            if not local or re.match(r"[a-zA-Z]+:",local) or (path.parent / local).exists():
                return match.group(0)
            assert relative not in canonical,(relative,target)
            changes.append(dict(file=relative,target=target))
            return f"{label} (research archive: `{target}`)"
        text=pattern.sub(replace,path.read_text())
        if text!=path.read_text():path.write_text(text)
    for relative in canonical:
        assert digest(DEST / relative)==copied[relative]
    names=sorted(str(p.relative_to(DEST)) for p in DEST.rglob("*") if p.is_file())
    write_json(DEST / "PACKAGE-MANIFEST.json",dict(format="x87-curated-local-review-v1",
        status="STAGED_FOR_CLEAN_BUILD", licensing="undecided", source_copies=copied,
        narrative_link_exports=changes,files={p:digest(DEST / p) for p in names}))
    print("Staged",len(names),"files at",DEST)


def seal():
    manifest=DEST / "PACKAGE-MANIFEST.json"
    data=json.loads(manifest.read_text())
    report=json.loads((DEST / "RELEASE-VERIFICATION.json").read_text())
    assert report["status"]=="PASS"
    # Only the allowlisted files enter the archive; build outputs stay local.
    names=sorted(set(data["files"])|{"RELEASE-VERIFICATION.json"})
    data["files"]={name:digest(DEST / name) for name in names}
    data["status"]="LOCAL_REVIEW_PACKAGE_VERIFIED"
    data["verification"]="RELEASE-VERIFICATION.json"
    write_json(manifest,data)
    archive=DEST.with_suffix(".zip")
    if archive.exists():raise SystemExit("Archive already exists; keep the previous review snapshot")
    with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED) as z:
        for name in [*names,"PACKAGE-MANIFEST.json"]:
            z.write(DEST / name,arcname=f"{DEST.name}/{name}")
    print("Sealed",archive,"SHA256",digest(archive))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("stage","seal"))
    args=parser.parse_args()
    stage() if args.action=="stage" else seal()

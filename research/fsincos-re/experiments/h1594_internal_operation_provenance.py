#!/usr/bin/env python3
"""Freeze the inputs of a read-only primary-source operation-semantics audit.

This is a documentary consistency check, not a micro-op emulator, selector
search, PDF OCR validator, or hardware test. Diagram conclusions were reviewed
visually; text anchors below only ensure the expected pages were consulted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PDF_SHA256 = "65a461af7650a0945acfa72e362f39de8a93f34d9f480d850f14b3629d3a9f02"
PRIOR_FILES = (
    "notes/h1499-public-topology-provenance.md",
    "notes/h1457-public-p6-patch-surface.md",
    "notes/h1458-historical-p6-patch-surface.md",
    "notes/h1459-unsupported-p6-patch-recovery.md",
    "notes/h1460-exact-ppro-patch-recovery.md",
    "notes/h1467-pentium-pro-sibling-patch-recovery.md",
    "notes/h1555-ppro-public-layout-correction.md",
    "notes/h1556-h1558-ppro-public-near-decoder.md",
    "notes/h1559-h1560-ppro-near-decoder-adversarial.md",
    "notes/h1561-h1562-ppro-nop-crib.md",
    "notes/h1563-ppro-rail-affine-nop-crib.md",
    "notes/h1583-h1589-both-equality-taps.md",
    "tmp/ledger33/current/h1425_p5_public_mux_signals.txt",
    "tmp/ledger33/current/h1427_p5_fadd_rounder_signals.txt",
)
PAGE_ANCHORS = {
    48: ("Formally Verifying IEEE Compliance", "Pentium"),
    49: ("Technology Overview", "unbounded precision"),
    50: ("Figure 1: Mantissa representation", "rounding modes"),
    51: ("Figure 2: Floating point multiplier", "sticky bit"),
    52: ("Figure 3: Reference model for FPSHR", "five stages"),
    53: ("Verifying FSQRT and FDIV", "only very minor"),
    54: ("those used only by microcode", "stalls, for example"),
    55: ("microarchitectural changes", "be modified"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    pdf = root / "tmp/pdfs/intel-technology-journal-1999-q1.pdf"
    extracted = root / "tmp/pdfs/intel-technology-journal-1999-q1.txt"
    if digest(pdf) != PDF_SHA256:
        raise ValueError("primary PDF differs from the inspected source")
    pages = extracted.read_text().split("\f")
    checked = []
    for physical_page, anchors in PAGE_ANCHORS.items():
        page = pages[physical_page - 1]
        flat = " ".join(page.split())
        for anchor in anchors:
            if anchor not in flat:
                raise ValueError(f"missing page {physical_page} anchor: {anchor}")
        checked.append({
            "physical_pdf_page_one_based": physical_page,
            "article_page": physical_page - 47,
            "extracted_page_sha256": hashlib.sha256(page.encode()).hexdigest(),
            "anchors_passed": len(anchors),
        })
    report = {
        "audit": "H1594",
        "status": "NO_NEW_FSIN_FCOS_CONTROL_OR_ARITHMETIC_CONTRACT",
        "primary_source_url": "https://www.intel.com/content/dam/www/public/us/en/documents/research/1999-vol03-iss-1-intel-technology-journal.pdf",
        "primary_pdf_sha256": PDF_SHA256,
        "extracted_text_sha256": digest(extracted),
        "page_checks": checked,
        "prior_artifact_sha256": {name: digest(root / name) for name in PRIOR_FILES},
        "new_exact_documentary_detail": "Figure 3 supplies a parameterized FPSHR reference example, not a final-add or multiplier variant implementation.",
        "missing": ["variant opcode/control identifiers", "per-variant input/output widths", "rounding-mode encoding", "FSIN/FCOS site-to-variant mapping", "Skylake applicability"],
        "executable_silicon_hypotheses_justified": [],
        "hardware_executed": False,
        "labels_opened": False,
        "emulator_modified": False,
        "paper_or_pdf_modified": False,
        "validation_boundary": "Text-anchor and input-identity checks; visual source interpretation remains documentary evidence, not a circuit proof.",
    }
    with args.output.open("x") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")
    print(f"{len(checked)} page checks; no new FSIN/FCOS variant contract")


if __name__ == "__main__":
    main()

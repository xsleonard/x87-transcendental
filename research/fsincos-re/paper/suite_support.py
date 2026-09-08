"""Public data and hashing helpers shared by suite publication tools."""
from fractions import Fraction
import ast
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def pseudocode_program_digest(path):
    """Bind replay evidence to executable Python blocks independently of prose."""
    blocks = re.findall(r"^```python\n(.*?)^```", Path(path).read_text(), re.M | re.S)
    assert len(blocks) == 5
    return hashlib.sha256("\n".join(blocks).encode()).hexdigest()


def before_f2xm1_correction_digest(path):
    """Hash a historical view in memory; never rewrite the archived source.

    The only omitted text is the newly added F2XM1 helper and dispatch line.
    Matching an old whole-file digest proves every other byte is preserved.
    """
    code = Path(path).read_text()
    function = code.index("static sf_t f2xm1_tiny_raw80(")
    start = code.rfind("/*", 0, function)
    end = code.index("/* reconstructed six-coefficient table polynomial. */", function)
    branch = "    if (x.exp <= -16382) return f2xm1_tiny_raw80(x, rc);\n"
    assert start >= 0 and code.count(branch) == 1
    historical = (code[:start] + code[end:]).replace(branch, "", 1)
    return hashlib.sha256(historical.encode()).hexdigest()


def reference_ast_digest(path, before_f2xm1_correction=False):
    """Compare reference operations independently of added source comments."""
    tree = ast.parse(Path(path).read_text())
    if before_f2xm1_correction:
        added = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == "finish_raw80"]
        assert len(added) == 1
        tree.body = [n for n in tree.body if n is not added[0]]
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "finish_raw80"]
        assert len(calls) == 1
        calls[0].func.id = "finish"
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


def literal(record):
    sign, scale, sig = record["sign"], record["scale"], int(record["significand"], 16)
    value = Fraction(sig << scale) if scale >= 0 else Fraction(sig, 1 << -scale)
    return -value if sign else value


def sibling_constants(path=None):
    document = json.loads(Path(path or PROJECT / "docs/sibling-constants.json").read_text())
    return {key: (literal(value) if key == "F2_LN2" else
                  {int(b): tuple(literal(v) for v in pair) for b, pair in value.items()}
                  if key == "TABLE" else [literal(v) for v in value])
            for key, value in document["constants"].items()}


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

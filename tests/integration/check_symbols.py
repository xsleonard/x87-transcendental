"""Check the link namespace of every defined library symbol, including static builds."""
import re
import subprocess
import sys

options=['-gU'] if sys.platform=='darwin' else ['-g','--defined-only']
output=subprocess.check_output([sys.argv[1],*options,sys.argv[2]],text=True)
symbols=re.findall(r'^\s*[0-9a-fA-F]+\s+[A-Za-z]\s+(\S+)\s*$',output,re.M)
assert symbols, 'no defined symbols inspected'
if sys.platform=='darwin':symbols=[s.removeprefix('_') for s in symbols]
# Clang emits this coalesced registration marker when ASan instruments globals.
# Permit the exact compiler marker, while still rejecting ordinary helper names.
compiler_symbols={'__asan_globals_registered','___asan_globals_registered'}
unexpected=[s for s in symbols if not s.startswith('x87t_') and s not in compiler_symbols]
assert not unexpected,unexpected
print('PASS library symbol namespace:',len(symbols),'symbols')

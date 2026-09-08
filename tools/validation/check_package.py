"""Build an isolated source package and exercise installed/vendored consumers.

Keeps its temporary directory for inspection. Uses no research tree or network.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('--cmake',default='cmake')
    parser.add_argument('--libdir',default='lib')
    args=parser.parse_args()
    cmake=str(Path(args.cmake).resolve()) if '/' in args.cmake else args.cmake
    directory=Path(tempfile.mkdtemp(prefix='x87trans-package-'))
    log=directory/'verification.log'
    def run(command,**kwargs):
        p=subprocess.run(list(map(str,command)),text=True,capture_output=True,**kwargs)
        with log.open('a') as stream:
            stream.write(str(command)+'\n'+p.stdout+p.stderr+'\n')
        if p.returncode:raise RuntimeError(f'Command failed; inspect {log}: {command}')
        return p.stdout
    with tarfile.open(args.archive) as archive:
        archive.extractall(directory,filter='data')
    source=directory/'x87trans-0.2.0'
    manifest=json.loads((source/'SOURCE-MANIFEST.json').read_text())
    for name,digest in manifest.items():
        assert hashlib.sha256((source/name).read_bytes()).hexdigest()==digest,name
    assert not (source/'research').exists() and not (source/'fsincos-re').exists()
    assert not (source/'cmake/FindGMP.cmake').exists()
    assert not (source/'src/arithmetic/rational.c').exists()
    assert not (source/'src/internal/rational.h').exists()
    build=directory/'build';install=directory/'installed'
    run([cmake,'-S',source,'-B',build,'-DCMAKE_BUILD_TYPE=Release',
         '-DX87TRANS_BUILD_TESTS=ON','-DX87TRANS_BUILD_TOOLS=ON',
         '-DCMAKE_DISABLE_FIND_PACKAGE_GMP=ON',
         '-DCMAKE_INSTALL_LIBDIR='+args.libdir])
    run([cmake,'--build',build,'-j','4'])
    run([cmake,'-E','env','CTEST_OUTPUT_ON_FAILURE=1',cmake,'--build',build,'--target','test'])
    run([cmake,'--install',build,'--prefix',install])
    relocated=directory/'relocated';install.rename(relocated)
    consumer=directory/'consumer';consumer.mkdir()
    (consumer/'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.20)
project(external_consumer LANGUAGES C CXX)
if(X87TRANS_SOURCE)
  add_subdirectory(${X87TRANS_SOURCE} numerical_library)
else()
  find_package(x87trans 0.2 CONFIG REQUIRED)
endif()
add_executable(client_c main.c)
add_executable(client_cpp main.cpp)
target_link_libraries(client_c PRIVATE x87trans::x87trans)
target_link_libraries(client_cpp PRIVATE x87trans::x87trans)
''')
    code='''#include <x87trans/x87trans.h>
/* A consumer owns these names; library internals must not claim them. */
void decode(void) {}
void rounded(void) {}
void scale2(void) {}
const int ONE = 1, ZERO = 0;
int main(void) {
    x87t_context *ctx=x87t_create(); if (!ctx) return 1;
    x87t_control c=X87T_CONTROL_INIT;
    x87t_raw80 x={0x3ffe,UINT64_C(0x8000000000000000)};
    x87t_result r;
    x87t_error e=x87t_fsincos(ctx,x,&c,&r);
    x87t_destroy(ctx);
    return e!=X87T_OK || r.values!=(X87T_PRIMARY|X87T_PUSHED);
}
'''
    (consumer/'main.c').write_text(code);(consumer/'main.cpp').write_text(code)
    for label,option in [('installed','-DCMAKE_PREFIX_PATH='+str(relocated)),
                         ('vendored','-DX87TRANS_SOURCE='+str(source))]:
        target=directory/('consumer-'+label)
        # Arbitrary nested libdirs are not CMake's platform search convention.
        # Locate their package explicitly; its imported paths must still relocate.
        extra=['-Dx87trans_DIR='+str(relocated/args.libdir/'cmake/x87trans')] if label=='installed' and args.libdir!='lib' else []
        run([cmake,'-S',consumer,'-B',target,option,'-DCMAKE_DISABLE_FIND_PACKAGE_GMP=ON',*extra])
        run([cmake,'--build',target,'-j','4'])
        run([target/'client_c']);run([target/'client_cpp'])
    env=dict(os.environ)
    env['PKG_CONFIG_PATH']=str(relocated/args.libdir/'pkgconfig')+os.pathsep+env.get('PKG_CONFIG_PATH','')
    flags=shlex.split(run(['pkg-config','--cflags','--libs','--static','x87trans'],env=env))
    assert [f for f in flags if f.startswith('-l')]==['-lx87trans'],flags
    run(['cc',consumer/'main.c',*flags,'-o',directory/'pkg-client'])
    run([directory/'pkg-client'])
    print(json.dumps(dict(status='PASS',directory=str(directory),source_files=len(manifest),
        source_hashes_verified=True,package_tests=True,relocated_install=True,
        c_consumer=True,cpp_consumer=True,vendored_consumer=True,pkg_config=True,
        research_required=False,gmp_discovery_disabled=True,external_arithmetic_libraries=False,
        libdir=args.libdir),sort_keys=True))

if __name__=='__main__':main()

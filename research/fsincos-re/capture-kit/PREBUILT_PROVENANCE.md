# Prebuilt binary provenance

The static binaries were introduced in commit `e86a1d446` and described as
Debian 12 VPS builds, but that commit did not preserve the exact commands.
The recipe below was reconstructed and verified on 2026-07-19: it reproduces
both committed files byte-for-byte, including their GNU build IDs.

## Verified build host

- Debian `12.15`, x86-64
- `gcc` `4:12.2.0-3`
- `gcc-12` and `gcc-12-multilib` `12.2.0-14+deb12u1`
- `binutils` `2.40-2`
- `libc6-dev:amd64`, `libc6-dev:i386`, and `libc6-dev-i386`
  `2.36-9+deb12u14`
- `gcc-multilib` `4:12.2.0-3`

Source:

```text
603d62af72945de1cd64920e25cf8be397cb2599c59bb4e31087393b22e1cd61  x87_capture.c
```

## Exact recipe

```sh
gcc -O2 -static -o bin/x87_capture_x86_64 x87_capture.c
strip bin/x87_capture_x86_64
gcc -m32 -O2 -static -o bin/x87_capture_i686 x87_capture.c
strip bin/x87_capture_i686
```

The separate `strip` step matters.  Using `gcc ... -s` produces identical
code and file sizes with this toolchain, but different ELF OSABI/build-ID
metadata and therefore different hashes.

Run `sh ./build_prebuilt_debian.sh` from the kit directory to execute this
recipe and verify the outputs against `bin/SHA256SUMS`.

## Committed outputs

```text
4a9b96aabb44bf3b62e65d54308b8a676a4d871dd98dd8266a62f51be75379ec  x87_capture_i686
e47b482b0354be3075204c59aa68a740f4ddf890799580ecbecc0e506ceab5c6  x87_capture_x86_64
```

- i686: ELF32 Intel 80386, static, stripped, GNU/Linux ABI 3.2.0,
  build ID `bdcf95e06a2a10e57f5bf588aac1714115306e65`
- x86-64: ELF64 x86-64-baseline, static, stripped, GNU/Linux ABI 3.2.0,
  build ID `884cbdaebfc73fed904bf307dc12613a4f27248f`

The i686 and x86-64 executables were previously verified to produce
bit-identical capture output on the full 240,000-input dense set.  The
x86-64 executable was also revalidated on the h59 RN/RD/RU discriminator
and the 19-input h62 RN/RD/RU m-width discriminator when the targeted
capture runner was updated.

On 2026-07-19 both committed executables were replayed on the Debian
Skylake host against the h65 polynomial, h67 wide-producer, and new h71/h74
polynomial-product inputs under RN/RD/RU.  The i686 and x86-64 hashes were
identical to each other and to the live Skylake reference hashes recorded by
`h61_ingest_capture.py`.  The expanded 18,441-execution
`run_constraints_prebuilt.sh` also completed end-to-end; its archive
manifest verified all 19 files and the ingester recognized h59, h62, h65,
h71, h74, and h67 as byte-identical to the Skylake references.

The later h78 paired-table addition changes only input data and runner
commands; it does not change `x87_capture.c` or either prebuilt executable.
The same static i686 binary is therefore ready for the TinyLinux/Pentium-II
replay without compilation.  The expanded 29,193-execution runner completed
on the Debian Skylake host on 2026-07-19; its manifest verified all 22 output
files, and the ingester recognized h59, h62, h65, h71, h74, h67, and h78 as
byte-identical to their Skylake references.

The h83/h85/h87/h89 small-path, h93/h95 tomography, h97 coefficient, and
h107 RN67-parameter additions likewise change only versioned input data and
runner commands.  `x87_capture.c` and both prebuilt hashes remain unchanged.
The focused runner now performs 54,327 executions; TinyLinux 11.1 must use
this prebuilt path and does not need a compiler.

The final focused runner was replayed end-to-end on the Debian Skylake host
on 2026-07-20.  Its SHA-256 manifest verified all 46 payload files (45
RN/RD/RU outputs plus `cpu_info.txt`), and `h61_ingest_capture.py` recognized
all 15 target sets as byte-identical to their archived Skylake references.
The bundled static i686 executable was also run separately over all 15 input
sets under RN/RD/RU; all 45 outputs were byte-identical to the x86-64
executable.  This directly validates the prebuilt that TinyLinux/Pentium-II
will select, not only the x86-64 runner path.

h108 adds 1,024 reduced-table inputs, bringing the focused runner to 57,399
executions and 48 RN/RD/RU output files.  It again changes no capture source
or binary.  Both committed executables produced byte-identical h108 outputs
in all three modes on the Debian Skylake host.  A final end-to-end prebuilt
run verified all 49 manifest payloads (48 outputs plus `cpu_info.txt`), and
the returned archive contained the expected 51 members.

## Standalone status/timing update

The 2026-07-19 standalone-FSIN campaign changes the harness and therefore
supersedes the earlier committed hashes above in the historical paragraphs.
The default output remains byte-compatible.  `--status` now clears sticky
exception state for each input and appends the instruction-local status word;
`--timing[=N]` appends the minimum of N serialized RDTSC measurements.

Both final static binaries were rebuilt with the same verified Debian 12
recipe.  On the h65 polynomial set, i686 and x86-64 produced byte-identical
default and status-extended FSIN output under RN/RD/RU.  Stripping each
extended line back to its original three fields reproduced the default output
exactly.  The x86-64 binary then completed 1,440,000 dense standalone
FSIN/FCOS status captures and 16,752 timing captures without malformed or
missing lines.

Skylake standalone FSIN RN output from the updated binary is byte-identical
to the existing Pentium II capture on all 240,000 dense inputs.  C1 also
agreed with the independently known directed-rounding increment direction in
478,278/478,278 FSIN cases where RD and RU differed.

The distributable archive is created with `tar --no-xattrs` so macOS
provenance metadata does not produce warnings on old Linux systems.

The final standalone runner adds standalone and paired FSINCOS RN/RD/RU
outputs over both the 240,000-input dense set and 50,038-input structured
sweep, plus three FSIN outputs over the 360-input h117 tiny-boundary set.  It
therefore records 2,628,174 result lines across dense, sweep, tiny, and timing
files.  The distributable archive was replayed end-to-end on the Debian
Skylake host on 2026-07-20 using only the bundled x86-64 prebuilt.
`h115_ingest_standalone_capture.py` verified all 28 manifest payloads, all
dense/sweep/tiny/timing formats, 478,278/478,278 FSIN and
478,692/478,692 FCOS directed C1 checks, and the 0/240,000 Pentium-II FSIN
RN relationship.  On the sweep, standalone/paired FSIN output differences
were 26 RN, 44 RD, and 37 RU; standalone/paired FCOS differences were 53,
58, and 48.  The returned archive contained 30 members: the 28 payloads,
`SHA256SUMS`, and the `standalone-out/` directory entry.

## Focused FSIN runner extension

The 2026-07-20 h130/h135 extension changes only committed input files and
`run_standalone_prebuilt.sh`; `x87_capture.c` and both verified static
executables are unchanged.  It adds six RN/RD/RU standalone-FSIN status
files: 512 reduced-polynomial coefficient separators and 80 terminal-table
coefficient separators.  The h135 x86-64 Skylake replay selected the
path-aware terminal rule documented in `notes/fsin-reconstruction.md`.
The extended standalone run contains 2,629,950 result lines in 34 manifest
payloads; its tar archive contains 36 members including `SHA256SUMS` and the
directory entry.
The h135 RN/RD/RU output SHA-256 values are respectively
`aba65ded75a50dbf5fee30e46a2678be5089ab255191638f071bb7253f173ac4`,
`7c96e39b8e085827bad3c7aa0bce1e0803c959edb698ff019470d2a305c30b5e`,
and `c5746d7306eea3e10d65aa424fe42fc58924aa72d6550315482b439d0aa5cd2a`.

h140 adds five asymmetric-FMUL separators and three RN/RD/RU output files.
It changes no capture source or executable.  The committed x86-64 prebuilt
produced the Skylake reference in a fresh compiler-free run; its binary hash
remained
`e47b482b0354be3075204c59aa68a740f4ddf890799580ecbecc0e506ceab5c6`.
The extended standalone runner now records 2,629,965 result lines in 37
manifest payloads.

h147 adds 128 internal-cosine guard-bit separators and three RN/RD/RU output
files without changing the harness or either prebuilt.  The runner now
records 2,630,349 result lines in 40 manifest payloads.

h148 adds 441 balanced separators for twelve remaining internal-cosine
Boolean rules and another three RN/RD/RU output files.  The runner now
records 2,631,672 result lines in 43 manifest payloads.

Both focused sets were replayed on the Debian Skylake host with the committed
x86-64 binary.  h147 RN/RD/RU output hashes are
`9ff0c7b327885aea3e1ce55ba0b3b5facd05644787c5b134cee88714b9b19f23`,
`985e1c44c1403129a92309b3b4cceeb9f71952820e480950af506e27d760e083`,
and
`970b137a85d04e02a52c7491bb707031385f7a8b47958629e3d03d111e0de85c`.
h148 RN/RD/RU output hashes are
`473b3f3952f2b4f621650108357d01dc45e0daa536afc93195280e31e28042d2`,
`3559ba1dfba8688fe75e00e33550b19edded212a92b89d794e3cbd86ea248d5b`,
and
`30b1fe6caa78a9b1c07129de11efc90073aa4b5c5865144d7d8d1166af3a49f5`.

h151 adds 538 balanced separators for six final internal-cosine product
rules.  It changes no capture source or executable.  The runner now records
2,633,286 result lines in 46 manifest payloads.  The committed x86-64
prebuilt captured all three modes compiler-free on the Debian Skylake host;
RN/RD/RU hashes are respectively
`4a8ac8cd32bb1930245dd4fe82dad75701609a9aaa5330b2774cdcc6c98fa5f6`,
`8d9b6b7628f6c4ae61e84bdc9a0e1a88f5e0b818b03a2fccb5b452412b0793c0`,
and
`21e32ce40cd94c03f5691a084a6baf6311f25d75f2d66b3c5bf149eaf68aa4f7`.

h158 adds 634 balanced separators for six two-predicate fifth-Horner rules.
It changes no capture source or executable.  The standalone runner now
records 2,635,188 result lines in 49 manifest payloads.  The committed
x86-64 prebuilt captured all three modes compiler-free on the Debian
Skylake host; RN/RD/RU hashes are respectively
`5bc6c08a62589d77d63ebb5bbc9ebb2198b2ef4138b30e61272ca2c5454a8103`,
`e9ac42cadca85c2cc3dc317c3963b9cd87f78851f135bb19b203daf9bef47933`,
and
`83e4c1256465601d10707c8f8f58e39273cee01b3c131997efe8d486e5fed174`.

h161 adds 256 separators for Round 32 versus the proposed second fifth-sum
selector.  The standalone runner records 2,635,956 result lines in 52
manifest payloads.  The committed x86-64 prebuilt captured all three modes
compiler-free on the Debian Skylake host; RN/RD/RU hashes are respectively
`62e540d1aaeaa27127a5d6cb8cea3f2628beb1f7f144938c2549468328b69c24`,
`18a3afb6a5150638c73e34223c48eace1a57d8ff9b0fcd642eb4a7cb814cae86`,
and
`83c83e1798949d433e343c4b3c9498f6aa0be1f8bab92ed31f97ae04937ed03f`.

h163 adds 33 constructed-quotient separators for 39 product/coefficient
grids.  It changes no capture source or executable.  The standalone runner
now records 2,636,055 result lines in 55 manifest payloads.  The committed
x86-64 prebuilt captured all three modes compiler-free on the Debian
Skylake host; RN/RD/RU hashes are respectively
`5b813be7aeb136ef21637b54b3a8d6883ebebef54bb11e13f6d834b7ae2c70bb`,
`2051b6634bef892851bbf74dbecb8b0f3ebad55b885134b744478a73581a1331`,
and
`ae65f10235bf12de610da33a2af601a79daab2207a9f03ff28d4ce614b18c49a`.

h165 adds the sole architectural separator found in 30,000,000 constructed
scans of ten Round-33-equivalent product widths.  The standalone runner now
records 2,636,058 result lines in 58 manifest payloads.  The committed
x86-64 prebuilt captured all three modes compiler-free on the Debian
Skylake host; RN/RD/RU hashes are respectively
`abf33cf3bc1259217b4842b5e3fd0d25f209e4ef51accb870ced493fd07f81e3`,
`abf33cf3bc1259217b4842b5e3fd0d25f209e4ef51accb870ced493fd07f81e3`,
and
`e962fb2478785535d512ef051960d93a53b1bc89ac86fabb91d4bb0b546345be`.

h168 adds 363 balanced separators for six adjacent post-Round-33 operation
rules.  The standalone runner now records 2,637,147 result lines in 61
manifest payloads.  The committed x86-64 prebuilt captured all three modes
compiler-free on the Debian Skylake host; RN/RD/RU hashes are respectively
`acc4fa8355f8d2cb01fcec22c4302f504e5b37a4577b83ed3a97230212dcd9ae`,
`7358783ad3261a32e66087bd56bafc2dd8fd1ac92d690599c7b5782f8e24c5c4`,
and
`49ee93167ac801949bb187ffd17d630827d667294c32a45ae8c654ddb2796c44`.

h171 adds 283 balanced separators for six conditional table-correction
rules.  It changes no capture source or executable.  The standalone runner
now records 2,637,996 result lines in 64 manifest payloads.  The committed
x86-64 prebuilt captured all three modes compiler-free on the Debian
Skylake host; RN/RD/RU hashes are respectively
`a75f6cd702a761c84ac3a3244e77839d612db735af69d665091dd0e2e925629b`,
`b16745e1405df5b811880d5db2d21d3b07554b573982065b77bee59fea679cd7`,
and
`4dff92c9cd1a04826f9bec859f8eeacb16226324e986eef50ac9b1c418427b9f`.

## Precision-control update

The h172 update adds order-independent `pc24`, `pc53`, and `pc64` arguments.
It changes the capture source and supersedes the earlier standalone binary
hashes.  Both static executables were rebuilt with Debian GCC
12.2.0-14+deb12u1 using `build_prebuilt_debian.sh`:

```text
8e77811ec38f393dce6b6298a7701a30af7f3df916e9ffc703fa3d0851d3a98e  x87_capture.c
c100f20607fa44f194461161ad27a945f49f1557bf6e53c71ad1b6b75587de88  x87_capture_i686
c8dc08d1192bb886dcd962608fe2590c4a812bd6bafdcddbc390daa5f97f726c  x87_capture_x86_64
```

The i686 build ID is `154663c9a7b4edab3251642ef80d396c53bcbec7`;
the x86-64 build ID is `d395f6faab0bf05c7b5eb0c372875adf4f18a4b9`.
Both binaries produced byte-identical results for h171 under RN/RD/RU and
FSIN/FCOS/FSINCOS (nine complete instruction-mode sets).

The runner now records 2,738,638 result lines in 68 manifest payloads.
On Skylake, PC24/PC53/PC64 produce byte-identical RN outputs and status words
for the 50,038-input sweep (SHA-256
`bca77942c9bce6423695121f4121c4f9b19fc93413bdaac2b30caaf8069b6157`)
and 283 h171 inputs (SHA-256
`a75f6cd702a761c84ac3a3244e77839d612db735af69d665091dd0e2e925629b`).

h175 adds 243 balanced separators for six structural table FADD rules.  It
changes no capture source or executable.  The standalone runner now records
2,739,367 result lines in 71 manifest payloads.  The committed x86-64
prebuilt captured all three modes compiler-free on the Debian Skylake host;
RN/RD/RU hashes are respectively
`2dc00233089fdfd4d02a082484bc1289d67a74eb1a97da9eff094c7b1e79315d`,
`accdfb0f79c60e99ae4e47472c381e0b7bc12618d6b603da8159c93d63fb83e3`,
and
`b9a70f66d46cf213d4b97bb9fb1913a2522a7f48054384880a1168e2787ec756`.

h183 adds 43 two-lane separators for six rare wide `p*square` carriers.  It
changes no capture source or executable.  The standalone runner now records
2,739,625 result lines in 77 manifest payloads.  The committed x86-64
prebuilt captured standalone FSIN and paired FSINCOS under all three modes.
The six result hashes are recorded in `README.md`; all carrier
representatives fail componentwise.

h185 adds 38 two-lane separators for four FIRC lookup-constant routes.  It
changes no capture source or executable.  The standalone runner now records
2,739,853 result lines in 83 manifest payloads.  The committed x86-64
prebuilt captured standalone FSIN and paired FSINCOS under all three modes
on the Debian Skylake host.  The six result hashes are recorded in
`README.md`; RN64 passes every complete gate, away/odd fail fresh data, and
chop fails the complete old partitions.

h189 adds 37 two-lane separators for h188's three latent terminal-P
profiles.  It changes no capture source or executable.  The standalone
runner now records 2,740,075 result lines in 89 manifest payloads.  The
committed x86-64 prebuilt captured standalone FSIN and paired FSINCOS under
all three modes on the Debian Skylake host.  The six result hashes are
recorded in `README.md`; coefficient away64 plus terminal-sum chop65 is the
only complete survivor and is ported as Round 35.

## Conditional FIRC input-only extensions

h216/h221/h223/h224 add 31/49/43/98 two-lane status inputs.  They change only
input data and shell runners; `x87_capture.c` and the verified static
executables remain unchanged.  All four were captured compiler-free on the
configured Debian Skylake host with x86-64 prebuilt SHA-256
`c8dc08d1192bb886dcd962608fe2590c4a812bd6bafdcddbc390daa5f97f726c`.
The complete standalone runner now records 2,741,401 result lines in 113
manifest payloads.

h216 standalone-FSIN RN/RD/RU hashes are
`0c0669018ed85535e69d8dfe394215694ca4db28bce9bf019c9699442a920fac`,
`ef01e8a852df71ff6fc2e955c1fef3eb0006274432ab93697983486ab06753f1`,
and `5c61aaaddc4bd7fdcf20a2c5968ea461da6d27894424cbb7e9870f38e8b96b5f`.
Paired-FSINCOS RN/RD/RU hashes are
`d6d97172d7efcebe6f62120eece113e0b81b56fc48b5a6bab6945d672f3bd370`,
`1fd737a0a9e2a46fa944cc0c95ea59d4cbe27cc9f34ea5611364ef87c006c76d`,
and `dc19d37c987a0b7b0b8fc1cc39c14ecbff6a827366ec72794e47979eed9bffde`.

h221 standalone RN/RD/RU hashes are
`23cd8a57dc99d798ed9b384e3192e88fb485a07733ef418a16c6e5c3dc21094e`,
`476cbadac930dccdc253a3276104192e6e260396c6083a516e78d43d7511caae`,
and `06bc550431c56eb66bcf459d12dca1208b50cb1ab47ce67011ecf321a6113c2d`;
paired hashes are
`014cdbf42b0b1a6e909eab7f5c9c86de672332156b25b680ae8c1590e6e45ead`,
`eb264599cefea744ee6bf7b07e5f4902ab526bc4e2a9fad47620b56990817647`,
and `4fac86d9126085da8cf112f917d2384ae9c9b3738591a65bb40320aeafcc8085`.

h223 standalone RN/RD/RU hashes are
`dbde9a39d01990167b6005d18c1a2c7d198e0c23fbd28af6a952b0e6a7a5629f`,
`c5d70d1417c60ad704fdda6598b0fb5c342ab76b4471fb49689984db0d73fe9a`,
and `94d331edc2d94b0a85cf443f3e5f645dedb2c9f33a658a120d0f402036a152a9`;
paired hashes are
`a64c46c0e437f299a5234ad9859276d063579a0a963e5e6491b40eabe01d04a3`,
`8dc3c34b3015ea53990269b63ea1e961f18e7d6f36c85f9e00faaf1ed32adcfb`,
and `f636d6c9036eaaafc16f78c9221ef0485fa88eb80a885feeb3655d1364c5097b`.

h224 standalone RN/RD/RU hashes are
`7bf9561c11d1728a69d9cd9175b16cc1a8084f53ada2cbab6dbf22987d39ac00`,
`40bc38fc8de1c4c49379d0cf8849475932ecbcf235903bb03d7857eacfcca445`,
and `174e0eb6f144c0d29ff2edaf86c3afb8d76aa7df27eece7955049ab672b837f4`;
paired hashes are
`bc85fc12fcbb37df6e0b64e8248374d525a6063c76427c1b3aa74b479e59f4d8`,
`ff86bc983e1b6ea9e3e46ff7aadce5edd730eb325d9aa7d2d579d17632d1e210`,
and `929d69c54833803b539855dc4ce369ecfdff1686713ead625584f9a980ecc582`.

## FPTAN/F2XM1 sibling update

The 2026-07-22 sibling update adds FPTAN pair capture and F2XM1 single-result
capture.  It therefore supersedes the h172 executable hashes.  The source and
both static binaries were rebuilt in the fresh Debian directory
`/home/coduoserver/fsincos-capture-kit-20260722004008` with the verified GCC
12 recipe above:

```text
3da7680227e83aece60c42909889d38cbfd3535cff42704733eafe9b5cf98132  x87_capture.c
2bfdbb49efe051b837551086268ac4e1d663b53016a2f09a47b9bddf6c8c4d40  x87_capture_i686
3d5827676c3f4c47b99fc5836864d3cf4092c5501fb71ceea9149255d6dc5670  x87_capture_x86_64
```

The i686 build ID is `b6d78d3b29ef8fb0abc5b8588ebdf00ded74c0ed`;
the x86-64 build ID is `a0350d68925a08d05d05a9565f75b5ff622563de`.
Both executables produced byte-identical output on all 38,796 compact
instruction/mode runs.  A complete compiler-free x86-64 Skylake replay of
`run_siblings_prebuilt.sh` finished with 27 verified manifest payloads.

The hardware-blind sibling input and metadata hashes are:

```text
4ac60935c5551165712a5bd828669e72edeadf1701784fb92339753bc55781ee  sibling_fptan_f2xm1_h245.txt
1af99ce9965ed8e7a01d349395a29a888a46f363a6fc94644fb85034f37caa0b  sibling_fptan_f2xm1_h245.meta.txt
```

On Skylake, FPTAN pushed exact `1.0` on every successful row and both sibling
instructions ignored PC24/PC53/PC64 on all 6,466 compact inputs.  The static
i686 binary is therefore ready for the same compiler-free sibling capture on
TinyLinux 11.1.

## F2XM1 h257 input-only validation

h257 adds a focused F2XM1 runner and 8,550 hardware-blind operands without
changing `x87_capture.c` or either prebuilt.  Input and metadata hashes are:

```text
dd5ac3cf3ca1f07112077f496876074121545b13047574b4ad18c501b1cf0225  f2xm1_validation_h257.txt
e2123f07eb595747ed2a2307950277cfa94643e9a90d48e0b66efceb84caaff7  f2xm1_validation_h257.meta.txt
```

The compiler-free x86-64 Skylake capture hashes are:

```text
86d8df2906b414d5a81d79d2db2dde12d7d5532b75e5017f530bfc71e3ca195a  f2xm1_validation_h257_rn_status.txt
c4bddff31b768f7b049f32029d3cf63c417f3a326a7ae041f6b8b8fbb5aa3c49  f2xm1_validation_h257_rd_status.txt
b15510f672ca9a9ac3025c6b3acb6a4dec0ec5cbfc9b04028ad4b635e9a78a86  f2xm1_validation_h257_ru_status.txt
```

The reconstructed model matches every result and C1 observation.  Both
neighboring linear/long cutoffs and all eight class alternatives fail.  A
fresh Debian GCC build of the C port also produced byte-identical RN/RD/RU
value files and passed selftest.

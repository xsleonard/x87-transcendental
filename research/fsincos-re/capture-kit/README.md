# x87 FSINCOS capture kit

This kit records how your CPU's x87 `FSINCOS` instruction rounds its
results, for a reverse-engineering project mapping how Intel/AMD
implemented the instruction across CPU generations.

**What it does:** compiles one small C program, performs 1,307,437
predetermined instruction executions (including 57,399 targeted
constraint executions), and saves the raw outputs plus your CPU's
identification strings (`/proc/cpuinfo` first entry). Nothing is installed;
nothing outside this folder is written; no personal data is collected beyond
the CPU model.

**Requirements:** x86 CPU (Intel or AMD — both interesting!), Linux with
gcc (WSL works; for native Windows use MinGW: `gcc -O2 -o x87_capture.exe
x87_capture.c` and run the same input files through it in the same order,
modes rn/rd/ru).

**No compiler on the target?** Old machine, live-CD session, minimal
environment: use `sh ./run_capture_prebuilt.sh` instead — it uses the bundled
static binaries in `bin/` (x86-64 and i686, auto-selected). See
`RETRO.md` for per-machine boot instructions (Pentium II / P4 / Core 2 era).
The exact Debian toolchain, compiler commands, source hash, build IDs, and
output hashes are preserved in `PREBUILT_PROVENANCE.md`; the verified recipe
is automated by `build_prebuilt_debian.sh`.

**Already supplied a full capture?** To collect only the 57,399 targeted
executions—h59/h62/h65/h67/h71/h74/h78 plus the small-path, residual-table,
coefficient, RN67, and reduced-path parameter sets
h83/h85/h87/h89/h93/h95/h97/h107/h108—run:

```sh
sh ./run_constraints_prebuilt.sh
```

This produces a small `constraint-capture-*.tar.gz` and normally takes only
seconds, including on old CPUs.

**Standalone FSIN/FCOS reconstruction capture:** the updated binaries can
also record per-instruction status and timing without changing the historical
capture format.  Run:

```sh
sh ./run_standalone_prebuilt.sh
```

This captures standalone FSIN and FCOS plus paired FSINCOS under RN/RD/RU
over the 240,000-input dense set, appending the full x87 status word after
clearing sticky exception state before every instruction.  It repeats all
three instructions on the 50,038-input structured full-range sweep and runs a
360-input FSIN probe around the newly identified exponents -68/-69 tiny-result
threshold.  The paired files distinguish identical visible results whose C1
rounding direction differs between instruction paths; on Skylake the
FSINCOS C1 observation is empirically associated with the cosine result.  It
also times FSIN, FCOS, and FSINCOS over the existing polynomial and paired-table
discriminators.  The timing field is the minimum of nine serialized
measurements; use it as algorithm evidence only on bare metal, because KVM
scheduling and frequency changes can produce non-reproducible latency
classes.

**FPTAN/F2XM1 shared-arithmetic capture:** the same compiler-free binaries
also capture the two sibling instructions used to constrain the multiply,
add/subtract, and final-writeback datapaths shared with FSINCOS.  Run:

```sh
sh ./run_siblings_prebuilt.sh
```

The runner records FPTAN and F2XM1 under RN/RD/RU over the dense, structured,
and 6,466-input hardware-blind sibling sets.  It also repeats the compact set
under PC24/PC53/PC64 and records timing.  FPTAN output is written in
mathematical-result-first order: tangent followed by the architecturally
pushed exact `1.0`.  TinyLinux and other compiler-free targets use the bundled
i686 executable automatically.

After an initial sibling capture, the solved F2XM1 boundary and operation
classes can be retested without a compiler with:

```sh
sh ./run_f2xm1_validation_prebuilt.sh
```

The h257 runner executes 8,550 fresh hardware-blind operands under RN/RD/RU.
It densifies exponents -73 through -62, covers every `k/128` anchor and
neighboring x87 values, and contains 128 separators for each of eight
competing arithmetic-class schedules.

The final FPTAN shared-multiplier correction can be checked on any compiler-
free x86 target with:

```sh
sh ./run_fptan_fmul_validation_prebuilt.sh
```

This compact runner executes the seven complete residual operands from the
million-input h269 scan under RN/RD/RU.  It records FPTAN plus standalone
FSIN/FCOS and paired FSINCOS status so a cross-revision result can distinguish
the older empirical state schedule from the shared ordinary-FMUL chop67 rule.

The Round-43 shared-sine carrier discriminator is also compiler-free:

```sh
sh ./run_trig_sine_bias_prebuilt.sh
```

Its 192 hardware-blind reduced entries cover all three wide table cells, all
four quadrants, and both signs under RN/RD/RU.  The runner records standalone
FSIN, standalone FCOS, paired FSINCOS, and status.  The input SHA-256 is
`1115284a5e916e37b3cb93c498ac7d8ce4f7e80783590d6556faa437c060b879`.

The direct-entry and next-coordinate extension is compiler-free as well:

```sh
sh ./run_trig_sine_coordinates_prebuilt.sh
```

Its 256 inputs split evenly between direct Round-43 entries and the next wide
carrier coordinate.  The input SHA-256 is
`1619e0e0845f2c93ae12f7ad819ba81805061d3f1d69467341dd56a146fe9c4b`.

Four finer carrier-boundary runners exercise the 1/256-ulp values selected in
Rounds 45--48:

```sh
sh ./run_trig_sine_fraction_prebuilt.sh
sh ./run_trig_narrow_sine_fraction_prebuilt.sh
sh ./run_trig_narrow_sine_fraction2_prebuilt.sh
sh ./run_trig_narrow_sine_fraction3_prebuilt.sh
```

They contain 32 wide, 64 first-narrow, 24 second-narrow, and 24 third-narrow
hardware-blind separators, respectively.  Each records FSIN, FCOS, FSINCOS,
and status under RN/RD/RU.  Their input SHA-256 values are, in runner order:

- `8fd6edb66a5e679aa6551dbf6bc534097b4ebfe5b118efd1e2c6f01c31cedfa2`
- `ea88dba174e6706e8b9a2be6c00753057201ccebdc180250e29ace14846fb86d`
- `c133b2a022eb289e50c9f414b4cc1620e20ffde4776767a08c9bc79e87cfdc8e`
- `06b5a114e6eefe8cc2b5d5ca5ef5527944360a40c1f2998ed3bfca4fc9209f48`

Two larger runners test the post-Round-49 residue without requiring a target
compiler:

```sh
sh ./run_round49_residual_neighbors_prebuilt.sh
sh ./run_round49_broad_scan_prebuilt.sh
```

The first executes 197,044 inputs: +/-4096-neighbor windows around the 13
structured paired residual seeds, with sign mirrors. It records standalone
FSIN/FCOS and paired FSINCOS under RN/RD/RU so shared-state changes can be
checked across entry points. Its input and metadata SHA-256 values are
`64ac96cad6aa83e24a8364017447e3733349a434033e62aad6688a6414229dcc`
and `6e8d1e40cf29fedf53eb1b74f6d392e47846b39673f3ec8ce377e6e4ca1ad4d4`.

The second executes one million balanced paired-FSINCOS inputs across direct
and reduced narrow/wide table families. It records RN/RD/RU plus local status
and is intended as a regression and rare-residual census, not as a replacement
for the focused neighborhoods. Its input and metadata SHA-256 values are
`dc8f95e3ba641531d5c7d8d40a55523c026bf7abe0d4096b068198363124af64`
and `4ed6b4859fa34c2fadff8bf6414611ecc00bc942e50055be3cb0d7b99e4e4f1c`.

The frozen h377 runner recaptures the 12 standalone-FSIN residual seeds found
by the deterministic `2^24` binary64-space comparison:

```sh
sh ./run_fsin_binary64_misses_h377_prebuilt.sh
```

It records only standalone FSIN under RN/RD/RU. The input SHA-256 is
`90beb327ff4eb7c59a626a223c6ce28f6489182f2947a7bb1b94eee89ad39175`.
The fixture is deliberately not appended to a historical corpus, and
diagnostic neighborhoods must use a different input file.

The standalone runner also records three focused FSIN status sets.  h130
independently rejects a sweep-selected reduced-polynomial coefficient
correction.  h135 separates the direct and M66-reduced terminal table
coefficient materializations selected by the standalone reconstruction.
h140 separates the asymmetric X67/Y64 multiplier route and its direct versus
reduced internal product modes.  h147 independently tests a guard-bit
conditional in FSIN's odd-quadrant internal-cosine producer; h148 batches
the remaining square-normalization and tail-sticky predicate families.  h151
balances six final-product low-bit/trailing-zero rules and independently
validates the Round 31 tail selector.  h158 balances six two-predicate
fifth-Horner rules and validates Round 32.  h161 rejects a second fifth-sum
selector; h163 uses constructed range-reduction quotients to distinguish its
product/coefficient alternatives and validates Round 33.  h165 supplies the
sole width separator found in 30 million further constructed inputs and
rejects a 72-bit RN representative.  All focused sets
use the committed prebuilts; no compiler is needed.  The current runner also
repeats the RN structured sweep and h171 table separators under PC24 and
PC53; their ordinary PC64 results are already present in the main run.

The five h140 operands have SHA-256
`1595654e466fe1bcc784af59730739098da339caf9da39aa08177da699896abb`.
The Skylake RN/RD/RU result hashes are
`d85d9e65ea7e1b96a35642adec2c9b7ad4c91abd8a0609da9a3c93520b104de`,
`20bca5d6d2fd16059873e43b31486b28ca301bf315208331027c345e82ce586a`,
and `5557a0a12f4ba526494dadd04266a2ebeb50f60809558c2864e40db899c41831`.

h147 input/metadata SHA-256 values are
`a4108e3ccf1fd5c9ab832420736b8849611d994b682e09079680c47706b875fc`
and
`f3f6d853369e23be29a377b4e2b984b3c69be9084d8755ea5975cd32fe4b689d`.
h148 input/metadata SHA-256 values are
`ffea3c2f447b10de178c32c984c24bb11b945a4d668b126778824adecb0fff24`
and
`a28d72b1c7b743817efef4a27ed9dae54aa0c428bd63000bb9fb3d49b0bddeae`.
Both sets were captured compiler-free on Skylake with the committed x86-64
prebuilt.

h151 input/metadata SHA-256 values are
`3137aaf924722c4e10b3616989c3ad5cf5b2083ab5c8e3d457d5b02e25bb7cf2`
and
`ffe8b7e97b19e8e7f255f4847a11eef11accd1cb35d73e20696c9b340a038add`.
Its Skylake RN/RD/RU result hashes are
`4a8ac8cd32bb1930245dd4fe82dad75701609a9aaa5330b2774cdcc6c98fa5f6`,
`8d9b6b7628f6c4ae61e84bdc9a0e1a88f5e0b818b03a2fccb5b452412b0793c0`,
and
`21e32ce40cd94c03f5691a084a6baf6311f25d75f2d66b3c5bf149eaf68aa4f7`.
It was captured compiler-free on Skylake with the same committed x86-64
prebuilt.

h158 input/metadata SHA-256 values are
`d76f162a23f85806b58f3ad3f148b665f2a957f395e8b4e805ace57980ebe838`
and
`3c325394ac27d0feb856316ed5ea7653b85aeb0bed09dcdced9ab611f1782e7b`.
Its Skylake RN/RD/RU result hashes are
`5bc6c08a62589d77d63ebb5bbc9ebb2198b2ef4138b30e61272ca2c5454a8103`,
`e9ac42cadca85c2cc3dc317c3963b9cd87f78851f135bb19b203daf9bef47933`,
and
`83e4c1256465601d10707c8f8f58e39273cee01b3c131997efe8d486e5fed174`.
It was captured compiler-free on Skylake with the unchanged committed
x86-64 prebuilt.

h161 input/metadata SHA-256 values are
`9d93fd3613619afc0b73ea3c5d67bf7273069ee0b51a512a8b2f95551908bd2b`
and
`d3d334d76b083edc8216aa2265d0abfb17eaf0b472e8841870c0c31ad4d51703`.
Its Skylake RN/RD/RU result hashes are
`62e540d1aaeaa27127a5d6cb8cea3f2628beb1f7f144938c2549468328b69c24`,
`18a3afb6a5150638c73e34223c48eace1a57d8ff9b0fcd642eb4a7cb814cae86`,
and
`83c83e1798949d433e343c4b3c9498f6aa0be1f8bab92ed31f97ae04937ed03f`.

h163 input/metadata SHA-256 values are
`2f6e01827e468903cc878bbc4bce0b42b166360374fb1356918be0a7ddee369c`
and
`783d44c4eb99dbf495a7f97ba76d9f4b33fe32c9fa1a18329ac32d8a8acce748`.
Its Skylake RN/RD/RU result hashes are
`5b813be7aeb136ef21637b54b3a8d6883ebebef54bb11e13f6d834b7ae2c70bb`,
`2051b6634bef892851bbf74dbecb8b0f3ebad55b885134b744478a73581a1331`,
and
`ae65f10235bf12de610da33a2af601a79daab2207a9f03ff28d4ce614b18c49a`.
Both sets were captured compiler-free on Skylake with the unchanged
committed x86-64 prebuilt.

h165 input/metadata SHA-256 values are
`28c93c3e6e988d3b673b95482bc1c55a338e70f8a0e194997b979221e5b1a3df`
and
`529965a8bc104490740090fded2ce7f045c1ca19ba16a16d89a5770514a047d7`.
Its Skylake RN/RD/RU result hashes are
`abf33cf3bc1259217b4842b5e3fd0d25f209e4ef51accb870ced493fd07f81e3`,
`abf33cf3bc1259217b4842b5e3fd0d25f209e4ef51accb870ced493fd07f81e3`,
and
`e962fb2478785535d512ef051960d93a53b1bc89ac86fabb91d4bb0b546345be`.

h168 input/metadata SHA-256 values are
`6bd09b63d0ea8e95675de21ef8b3ac3b6fb7f9ad1978a1d5bdedcf53af0defc7`
and
`d5a24126e4fcb588bfafa3e392faf5fabcccc55debdb74cd76ac0023c249290c`.
Its Skylake RN/RD/RU result hashes are
`acc4fa8355f8d2cb01fcec22c4302f504e5b37a4577b83ed3a97230212dcd9ae`,
`7358783ad3261a32e66087bd56bafc2dd8fd1ac92d690599c7b5782f8e24c5c4`,
and
`49ee93167ac801949bb187ffd17d630827d667294c32a45ae8c654ddb2796c44`.
It was captured compiler-free on Skylake with the unchanged x86-64
prebuilt and rejects all six post-Round-33 operation rules componentwise.

h171 input/metadata SHA-256 values are
`8d22dea4af748d4a359b5d603aae3cd6249200de69b56b4fc34a98a97a3b6219`
and
`c2278a72c63f372d1cef54226f653b2cbf29e6d138357eaed5a3ec4ae4936620`.
Its Skylake RN/RD/RU result hashes are
`a75f6cd702a761c84ac3a3244e77839d612db735af69d665091dd0e2e925629b`,
`b16745e1405df5b811880d5db2d21d3b07554b573982065b77bee59fea679cd7`,
and
`4dff92c9cd1a04826f9bec859f8eeacb16226324e986eef50ac9b1c418427b9f`.
The 283-input compiler-free Skylake capture rejects all six conditional
table-correction rules componentwise.

h172's PC24/PC53/PC64 sweep files are all byte-identical with SHA-256
`bca77942c9bce6423695121f4121c4f9b19fc93413bdaac2b30caaf8069b6157`;
its three h171 files are byte-identical with SHA-256
`a75f6cd702a761c84ac3a3244e77839d612db735af69d665091dd0e2e925629b`.
Across 150,963 RN result/status lines, standalone FSIN ignores the x87
precision-control field.

h175 input/metadata SHA-256 values are
`3bd1f2457e46d34c8106b0dc271740ba21582e617b423e550ab81723c1e5da43`
and
`898857cb21181b885b20d74f1c03246198efe940a9f6a2fca934f3747dbe34df`.
Its Skylake RN/RD/RU result hashes are
`2dc00233089fdfd4d02a082484bc1289d67a74eb1a97da9eff094c7b1e79315d`,
`accdfb0f79c60e99ae4e47472c381e0b7bc12618d6b603da8159c93d63fb83e3`,
and
`b9a70f66d46cf213d4b97bb9fb1913a2522a7f48054384880a1168e2787ec756`.
The 243-input capture supplies 64 separators per structural table FADD rule;
complete cross-validation rejects all six.

h183 input/metadata SHA-256 values are
`7b4336c78cc369b9e625a10a82579ea9db9db37b46fd4c15a95c0ed6ea81e1df`
and
`7eef6aa4c78ab78d2d837432f5207c1788f02393f1d7bd39f7ebe312a96ef324`.
The 43-input set supplies 16 two-lane separators per rare wide `p*square`
carrier.  Its standalone-FSIN RN/RD/RU hashes are
`77be851af37ef6aafd3337ce6a7e0ec2cc56f2dfd25ca6669b9c14022a9b8861`,
`0bdf9afd5f7d59ffe344e58931f733e6f8f859b7a89a901ed297253b69b041df`,
and
`eb878b6fc9d8090c76c6afc95792de45bfd29c1b78d636a40c35b304645ab3ae`.
Paired-FSINCOS RN/RD/RU hashes are
`196a02473bb9a4c9e53676a37d3c2ec3584c3ebad5a952fbd7ca18702c09f48a`,
`3dbbf0899598bd4525e6ad97482a6b6756b6f651b5166c04a51f2e610a13d82f`,
and
`84baa0053ece63d25ebaec887e3e7e666c48e96cdb795c91cca4d988158cec7b`.
All six carrier representatives fail componentwise.

h185 input/metadata SHA-256 values are
`742be191825b89969adc4a0cd23cd2c020b316edebfc97f55cde06b213c9afd1`
and
`78e7b1ff2e2740fe448a93bed6017b7082139282df84d1c2bb33d0d60adc7901`.
The 38-input set supplies 16 two-lane separators per RN/chop/away/odd
64-bit lookup-constant route.  Its standalone-FSIN RN/RD/RU hashes are
`e034aa151285ce8114dfc9108ae9adb7c6f7bdb50ba5c352c7506758872b5c5b`,
`6f5ede23c3f9ba165c31d407d6d7e1cea369013f2209d8cc4bd5dd47d25e5fad`,
and
`577e35017bc6e8abed9d8ebf887995dfb5133139c85e998e2993abc472cdcae7`.
Paired-FSINCOS RN/RD/RU hashes are
`4409132a3820d3307d2758ebcf971329372b00cfdb890ab8d09c11a57d3d4266`,
`6dea55ad6801fe694071bbf66a049e79aa86d45d433d6ad98471db75778c3d7b`,
and
`f51635fae0a4c56315b119dff3e474225a4bf5d59f58c40790941d33cd0700ca`.
RN64 passes every old and fresh gate; away and odd fail the fresh capture.
Chop passes fresh data but fails the complete old partitions.

h189 input/metadata SHA-256 values are
`a14016cf82b0ecdc3520925039bec92778c79521233e7edad3fc29fffd99860a`
and
`aea881b1e869d6ef6ab2b5b151ffb61407eba7c4623a4642736365a60ff5d785`.
The 37-input set contains 16 direct and 21 constructed-reduction states and
supplies 16 separators for every pair among Round 34 and h188's three
terminal-P survivors.  Standalone-FSIN RN/RD/RU hashes are
`e44373e949c0c53d9c236b09690f742ed6eef1682c19f1c4c5179015ff2f4aaa`,
`048c4ffd9e01bb2d51fcdd241ab2cf642490d2d4e3b07fac44e2168361ebfe0a`,
and `70d9b2fca031af15a4f78d7d822377663916467b7efac2267660f78814e226bd`.
Paired-FSINCOS RN/RD/RU hashes are
`2309956f276d173b45c40edd490ab2b6a40521f9cc16782cf1fd2820d21af7e9`,
`2410d5be5bda3f7057f1f1ef79d875bcf5cc6830a9a28cfee745f53213c973c5`,
and `9a6443d2f369d22ff0a6f021cdfed54441d1a8dd4b1af65140728898ee990d50`.
The data selects terminal P coefficient away64 plus terminal sum chop65.

**Run:**

```sh
./run_capture.sh
```

Takes under a minute. Send back the produced `capture-*.tar.gz` (~15-20 MB
is normal — the hex significands don't compress much).

**Output format** (per input line `se_hex sig_hex` = x87 80-bit operand):
`OK <sin_se> <sin_sig> <cos_se> <cos_sig>` or `C2` (operand out of range).
One output line per input line, order preserved.  The `dense_fsin`/
`dense_fcos` files use the single-output form `OK <se> <sig>` (they run the
FSIN / FCOS instructions instead of FSINCOS — on Intel these take
different microcode paths; whether AMD's do too is one of the questions).
`--status` preserves those fields and appends `SW <status_hex>`.
`--timing` or `--timing=N` additionally appends `CYC <minimum_cycles>`.
The optional `pc24`, `pc53`, or `pc64` argument selects the x87
precision-control field independently of `rn`, `rd`, `ru`, or `rz`.
For example:

```text
OK 3ffb ff5577743771ae50 SW 3a20 CYC 268
```

The status is sampled after the transcendental instruction and before its
result is popped.  `fnclex` runs for every input, so PE and the other
exception bits are local to that instruction rather than sticky from an
earlier line.  C1 (`SW & 0x0200`) identifies a final significand increment;
on the Skylake validation capture it agreed with all 478,278 independently
checkable FSIN RD/RU cases.

Verify a returned standalone archive, its manifest, formats, C1 consistency,
and Pentium-II RN relationship with:

```sh
python3 experiments/h115_ingest_standalone_capture.py \
  standalone-capture-*.tar.gz
```

The `constraint_narrow_rn/rd/ru` files use FSINCOS on inputs selected because
the old baseline and the surviving narrow-kernel schedule predict different
bits.  The `constraint_mwidth_rn/rd/ru` files distinguish `m=RN69(P*a²)` from
the formerly equivalent `m=RN68` and `m=chop69` schedules.  The
`constraint_poly_rn/rd/ru` files test the Round-18 polynomial schedule on
fresh inputs where it differs from the historical model.  The
`constraint_poly_round75_rn/rd/ru` files distinguish the direct fused
cosine-Horner chain from the intermediate 75-bit hypothesis and the
supported product-before-add mechanism.  The
`constraint_poly_product_rn/rd/ru` files independently retest the supported
`RN64(chop67(q*a²)+C1)` mechanism with a new seed.  The
`constraint_wide_producer_rn/rd/ru` files test whether that six-term producer
also belongs in the wide table cosine chain.  The
`constraint_paired_table_rn/rd/ru` files project the same residual through
every cell in its four-term or six-term family, allowing exact inequalities
for the shared `(1+t, S)` state.  The h83/h85/h87/h89 files distinguish the
Itanium small kernel from the Pentium six-term path down through exponent
-32.  The h93/h95 files replay and densify the remaining master table states.
The h97 files test the narrow row-169 coefficient direction.  The h107 files
separate the surviving row-169 and shared-S parameters after the RN67
correction accumulator was introduced.  The h108 files test whether the
exact 65-bit M66 residual path needs a different shared-S state from direct
64-bit operands.  These are much more informative for the remaining gap
than another generic random sweep.

Notes for the analyst (not the volunteer): input sets are byte-identical
to the project's Skylake baseline captures (`gen_sweep.py` seed 0xF51C05,
`gen_dense_qn.py` seed 0xD15E — including the known >pi/4 leak in the
dense set, kept deliberately for comparability).  The h59 constraint input
has SHA-256
`81b00c667c50b2dd3cd2829f2a12154f5faa85381c5d8a0837f494ed60fdb936`.
The h62 input has SHA-256
`6dbd09f05e42f4508e859028942e130a6f3f16fbad254df24472f146eb9985c1`.
The h65 input has SHA-256
`3cf18140fe46ee9e734bc4e1483fa5202af7d88fe1b41cc5bc58b67b09ff0c86`.
The h71 input has SHA-256
`d232c6436655ab6fa35275ab89b6be92d1b29e6976e8958bf69bb93b7931227f`.
The h74 input has SHA-256
`cb9e8abce04af3c751f07e4127d445bb6b8167ac51a31cfa89599f16d7b3a676`.
The h67 input has SHA-256
`2d9886d1519106731d645a642e78577ac6074408e0064d261be3d215c7150859`.
The h78 input has SHA-256
`d8b085c2c44ffc535aa6efeb8a47a62cf84498da2f5cedac8270defbf62096de`;
its generation metadata has SHA-256
`c3a859685d4642d4ed5396258e5bd097a7372a520da64cc65fbb9b2ed7a9b24d`.
The later input hashes are:

- h83 `3ead36ba59e32e65766eadad4eef5bb27f5b39a8cae9f4c2f05c0f8cc8be2946`
- h85 `ba45fe1dcca12bad9ec28a704aef254e6346484c995e87e01e65a91d6f201912`
- h87 `409b837da55fe05d8ca8f3ed8805ae1e34fd2c5c29b467d5c779507d1d2c7c53`
- h89 `0ccd9b91f7f681079dc6b510a6c1952dca2a21fb423e085c065bd3cb7aff8c88`
- h93 `3fae3d684a150b074843f9a0de594fe7bd99eedee6e71ccf7ac09972cd48ac2d`
- h95 `b5dbf5be8f4015d658a978ad16c3206bba1d7b9f0dfb09fd016b3db1d4f393b9`
- h97 `9ce2e1045ca94db59a56f6832ca3d04f3899a347cc100e435d6d58b20f86841d`
- h107 `d82493f33d3729ef5728971bf633b5601772e438e4366dbc2a9f9676a7a123dc`
- h108 `d48d3427601aaece690b3eb7ab04f2c250818600983f052128b04b9b12f13a21`
- h130 `a5b399e67048e1f98ab6c9438e26f19c8e1d6ee3d1ef16678a4b89d55c29ac43`
- h135 `8a5a48812c2f400c7b84c8567cf58c1998b30f176c0ae63cc437499447b28bf2`

h130 metadata is
`fc1406909dae4542e69c5e435544a40906a20ee098d4e76a86e07f153aa7273b`;
h135 metadata is
`a7ef51a82342c1fab3e30367cf65aaa7163cd61a673873ffdd2e447d39f97877`.

## Conditional FIRC microcontrol captures

The unchanged compiler-free prebuilts also support four focused runners:

```sh
sh ./run_fadd_microcontrol_prebuilt.sh
sh ./run_fadd_tree_prebuilt.sh
sh ./run_fadd_tree_refined_prebuilt.sh
sh ./run_fadd_tree_final_prebuilt.sh
```

h216's 31 inputs select the Round-36 first-FADD FAMUBUS-bit rule.  h221,
h223, and h224 contain respectively 49, 43, and 98 hardware-blind inputs
that synthesize, refine, and finally reject every tested second decision-tree
leaf.  Each runner records standalone FSIN and paired FSINCOS under RN/RD/RU
with instruction-local status; no target compiler is needed.

Input/metadata SHA-256 pairs are:

- h216 `b7ad1c015c7d1bd26e1a167425e54284291d84fd64324be9766402731f137d1b` /
  `9fef739ba55eeb69ea08a76193a3139b769273f23e4920309f5c31e93b873c4d`
- h221 `a9aaf6f3945c2fee51e2cca9b5176ffb75da686c4c5de687187ee16240990411` /
  `173b56fb141b95ad7c9245f6eb27d289959d21fddfb48ab8404c50c94fb044a6`
- h223 `5e92223a64b2109cead23d735930456fdd313eeeb6b6f66f1b7573e925c39820` /
  `fe253c3b00d3660193837b24bf1b930e2d6e9c6497e7254ac082cde076c88493`
- h224 `7a99f053ac537fbac5cf9aa3b1c30aa9ce6b51694463c4f778ea9e3a27f59522` /
  `2102eb368331ad232eec294aa806b93ada7368941162806b38639e22e8615d82`

Compare directly against the dense baselines and experiments
h59-h108. Verify and score either a returned tarball or output directory with:

```sh
python3 experiments/h61_ingest_capture.py RETURNED_CAPTURE
```

Verify the checked-in h257 F2XM1 return with:

```sh
python3 experiments/h258_f2xm1_validation.py
```

## FCOS terminal-carrier captures

Run the complete compiler-free FCOS terminal-alignment suite with:

```sh
sh ./run_fcos_terminal_carrier_prebuilt.sh
```

The runner records FCOS under RN/RD/RU with instruction-local status for the
h363, h372, h380, h384, h388, h389, and h391--h395/h397 discriminator sets.
h388 independently validates the retained d=8/y=7 left-product-prefix rule.
The later sets are deliberate negative controls for right-product tails,
literal multiplier sum/carry vectors, earlier-square tails, and a d=7 aligned
lane.  Keeping them together is useful when comparing the terminal datapath
between processor generations; no compiler is required on the target system.

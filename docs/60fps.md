# 60 FPS / FPS livre (issue #5)

Local EU build support (2026-10-19): `CUSA03745`, metadata `APP_VER=01.00`, SELF SHA-256
`ae82724c387a055462ab1089180a13c2a20ac02abb87c8249bf718bb5a71c7b1`
(reconstructed ELF `580ba4bc7f9b785bfde0948be20ec67a30ca8c9318606ba5cbf28a1a01d54565`).
This profile is selected only by those hashes, then validates every expected byte. It maps
`flip_rate_60` to Ghidra `0x1b8be7c` (image `0xb8be7c`) and `dt_snap_60` to
`0x24d9920`, `0x24d9924`, `0x24d9928`. The flip call at image `0xb8be81` targets
PLT `0x14b06d8`, whose GOT relocation `0x16d8490` resolves NID `CBiu4mCE1DA`
(`sceVideoOutSetFlipRate`). `SmoothDeltaTime` at image `0xc51940` reads these snap
constants at `0xc51a80`, `0xc51a89`, `0xc51a9d`. This is an independent mapping of the
user's executable, not EU 1.03 support. Existing US 1.03 support is retained.

### Experimental EU timing corrections v2 (Windows, 2026-10-19)

Opt-in: `TLG_TIMING_60=1` in addition to **actual 60 FPS mode**. The older
`TLG_INPUT_TIMING_60=1` enables only the button/stick correction. The loader
checks CUSA03745/01.00 metadata, the exact code signatures below, and all four
applied 60 FPS writes (flip and three dt constants). It does nothing in 30 FPS,
unlocked mode, other versions, or without the opt-in. No game assets are edited.

Offline analysis found `CharacterSensorExt::update` at image `+0x6d62b0` incrementing
17 button-held counters once per update (`+0x6d7a70..+0x6d7ad8`), while adjacent
interval timers add dt. The boy animation graph consumes the remapped counts in
long-press/cancel/reach conditions, including Cross >4, Circle/R2 >6 and R1 >10.
At 60 updates/second those frame-counted thresholds have shorter real-time windows.
This is a concrete timing discrepancy, not proof that it explains every climbing
or Trico interaction problem. The grab-input action itself is a boolean; stamina
already multiplies its change by dt and must not be doubled.

`port/src/input_timing_60.[ch]` preserves native working counters and all input
bits/timers. An entry wrapper captures the original dt with the System V ABI;
the original snapshot memcpy call at image `+0x6d87b4` publishes elapsed-time-based
30 Hz-equivalent raw/remapped hold counts, before the original sensor unlock.
The snapshots are at object `+0x38c8` / `+0x39f0`; working counts remain at
`+0xd38` / `+0xe60`. A new press is immediately 1; at 60 Hz the sequence is
1,1,2,2,3,3 rather than 1,2,3,4,5,6. Release resets the history; a temporarily
invalid remapped button stays zero and regains the same hold age when re-enabled.
The six analog continuous-hold snapshots (`+0x2be0 + i*0x1f0 + 0x1e0`) are now
normalized through the same lock-held hook. The native analog increment/store,
common copy helper and all six original copy source/destination/callee tuples
are signature-checked. Axes, velocities, direction bits and working ages stay
native. Seconds-based input timers, stamina and game speed are unchanged.
Both input detours validate and prepare successfully before either is
written. The hook sites do not overlap the retained Windows ISA/red-zone table.

Validation: `input-timing-60-test` checks the real EU ELF signatures, rejection of
30/unlocked modes and modified bytes, 30/45/60/120 Hz and variable-dt replays,
pause/release/repress/invalid dt/saturation, and executes the real native counter
loop through production entry/copy detours and trampoline on synthetic state
(25,353 updates, all 17 buttons, six analog ages, remap masking, nonzero stick
data, pause/direction resets and nested update contexts). The live
30 FPS game was not accessed, restarted or reconfigured. **Gameplay A/B testing
of climbing, grabbing and calming Trico remains pending.**

`script_timing_60.[ch]` additionally detours the verified five-argument SysV
`hksi_hksL_loadbuffer` at image `+0xdd4dd0` (caller `+0xc898fe`). Nine original
EU Lua sources are recognized by exact length and SHA-256; optional terminating
NULs are accepted. Only generated, non-overlapping edits are made in a temporary
compiler-input copy. No archives or loose game assets are written. Unknown or
modified sources retain their original bytes and known-name mismatches warn in
the log. The original VM/options/chunk name/compiler status are preserved.

The source-guarded corrections cover normal-mode petting-to-sleep duration,
barrel-interest and async movement wait budgets, selected hard-coded 1/30-second
mission timers, First Flight bridge-shake delays, mirror angle steps and
balancer controller cadence, elevator stationary-sound detection, and the
skin-wind update cadence. AI paths
use `currentInfo.dt`; mission/mechanism paths use `GetGameDeltaTime()`. Fractional
30 Hz-equivalent ages preserve strict whole-update thresholds. Cadence uses
interval-boundary crossings, not modulo on fractional ages. Existing next-update
deferrals, request state indices, native excitement/stroke cooldowns and authored
animation markers are not rescaled.

`tlg_script_timing_60.py` regenerates the checked-in edit table from the user's
unmodified extracted assets. Ten offline Lua 5.1 tests cover syntax of all nine
original/changed scripts, actual petting/space-check/mirror functions, targeted
mission/barrel/head-check fragments, variable cadence and pause/invalid dt.
The production C transformer matches the Python result for all nine sources;
612 other extracted scripts remain unchanged. Its native detour and all five
arguments/return status are replayed with a compiler stub. Real ELF gates reject
30 FPS/unlocked/other versions/mutated signatures. The retained 1,810 ISA sites
and 2,214 red-zone groups do not overlap any timing hook.

This is not full live HavokScript VM / controller / AI / physics validation.
The candidate is separate, not installed or launched; gameplay A/B validation
is pending. These targeted fixes do not certify every subsystem at 60 FPS.

### Vegetation cadence correction

The verified EU executable initializes each `GrassType` with `slowFrame=4` and
`skipFrame=4` at image `+0x14e8bc0`. The main state script also sets
`skinWindMaxFrameSkip=1`, and Falling Bridge explicitly restores `skipFrame=4`
for four ivy instances. At 60 FPS those frame-counted skips can expose a visible
sub-cadence even when the camera and geometry render smoothly.

The 60 FPS profile changes only
`GrassType.skipFrame` from 4 to 8 and `skinWindMaxFrameSkip` from 1 to 2. Exact
bytes and exact Lua source hashes gate the edits. Authored wind speed,
acceleration, damping, `slowFrame`, the inactive `slipFrame` typo, saves and
archives are untouched. The 30 FPS mode still emits an empty built-in patch
file and receives no script transform.

Local 2560x1440/60 FPS gameplay testing in vegetation-heavy areas showed a
clearer, more comfortable leaf/ivy cadence, and the user confirmed that the
vegetation fix worked. This validates the targeted visual improvement on the
tested EU 01.00 build; it does not claim that every vegetation system or scene
has completed full-game validation.

Estado em 13/10/2026: **experimental, desligado por padrão.** O modo 30 FPS é o jogo como no PS4,
sem nenhum patch.

## Como ligar

| Onde | Valor |
|---|---|
| Launcher → Vídeo → "Taxa de quadros (experimental)" | `30 FPS (como no PS4)`, `60 FPS`, `Livre (até a taxa do monitor)` |
| Terminal | `TLG_FPS=30\|60\|unlocked ./run_tlg.sh` (o `TLG_FPS` vence o launcher) |

- Os patches só são aplicados no **eboot 1.03** (sha256 `91dce685…5feb3c`). Antes de escrever, cada
  endereço é comparado com os bytes esperados no `eboot.bin`. Se o sha256 ou um byte não bater, o
  jogo roda a 30 FPS sem patch, e o log diz por quê.
- O log da sessão começa com `Frame rate patch …` (um por escrita) e `Frame rate: <modo> FPS mode, N patch writes`;
  o loader confirma com `Patches: N writes, … bytes applied`.
- **Livre:** vblank de 480 Hz (`TLG_VBLANK_HZ=0`), e o quadro sai assim que fica pronto. O teto é o
  "Limite de FPS" do overlay; em "Sem limite", vale a taxa do monitor, até 120 FPS. Com o VSync da
  janela ligado, o monitor (60 Hz aqui) limita a 60.
- `TLG_FPS_PATCHES=a,b` (só para medições) troca a lista de patches do modo.

Código: `port/scripts/tlg_patches.py` (tabela e verificação), `port/launcher/tlg_run.py` (opção,
`--patches`, `TLG_ENGINE_FPS`), `driver.cpp` (limitador), `tlg_overlay.cpp` (texto do limite).

## Como o motor decide o tempo do quadro

Endereços do Ghidra (base `0x1000000`). Offset na imagem = endereço − `0x1000000`; no arquivo,
some `0x4000`.

1. **Flip rate.** Em `JsDevice/JsSwapChain` init (`0x1c4f9f0`), a chamada em `0x1c5151a`
   (`mov esi,1; call sceVideoOutSetFlipRate`, PLT `0x24bdd78`, NID `CBiu4mCE1DA`) pede 1 quadro a
   cada 2 vblanks: 30 Hz sobre o vblank de 60 Hz. No port, o present thread (`driver.cpp`) faz
   `vblank_count % (flip_rate+1)`. **É a única trava de 30 FPS:** só esse patch já dá 60 no menu,
   na intro e no gameplay.
2. **Ritmo.** Não há sleep no loop principal. O ritmo vem do flip com VSYNC, do `Present` (`0x1c4dfa0`)
   esperando a GPU terminar o quadro anterior e da task de render (ver `analysis/01_main_loop_threads.md` §3).
3. **Delta time: tempo real, não passo fixo.** `UpdateTime` (`0x1dd45c0`) mede o TSC.
   `SmoothDeltaTime` (`0x1d16480`):
   - correção por acumulador de erro (`app+0x1a4`, ±1 s) quando `app+0x1b8 > 0.5`, limitada a 0,8–1,25×;
   - `dt = min(dt, app+0x188)` × velocidade do jogo (`app+0x1b0`). `app+0x188` é o `trico minfps N`
     do console (1/N; padrão 0,05 = 20 FPS mínimo);
   - com o objeto da física (`app+0xb0`, o módulo havok): **snap** de 0,031667 < dt < 0,035 para
     exatamente 1/30, depois um filtro de 2ª ordem (0,8333 / 0,02449 / 0,7347) e arredondamento para
     múltiplos de **1/360 s** (`round(dt*360+0.1)/360`). O resultado volta para `app+0x19c`, o dt do jogo.
   - 1/60 = 6/360 e 1/120 = 3/360, então 60 e 120 são exatos. O acumulador corrige taxas que não
     dividem 360 (144 Hz, por exemplo).
   - Diferença 1.00 × 1.03: no 1.00 (`0x1c51940`) a correção pelo acumulador é sempre aplicada; o
     1.03 só aplica com `app+0x1b8 > 0.5`. O snap e o filtro são iguais.
4. **Lua `SetMaxFps(fps)`** (binding `0x12091a0`, ajuda "SetMaxFps( fps ) : 0 = no limitation"):
   grava `1.0/fps` em `game+0x180` (singleton `0x6832568`). Os scripts chamam `SetMaxFps(30)`
   (`game/scripts/states/main.lua:412`, `common/gamesetuptbl.lua:43`). Testado: **não limita o
   FPS** (60 e 240 FPS com e sem o patch). Não achei quem lê `game+0x180`. Os patches
   `max_fps_double` (0,5/fps) e `max_fps_off` (0) existem, mas não fazem parte dos modos.
5. **Constantes de 30 Hz.** No rodata há 56 cópias de 1/30f (95 referências), 153 de 30.0f (128 referências)
   e 67 de 1/60f. A string `"operate value to the frames(30fps) of the animation"` indica que a
   animação é autorada em quadros de 30 FPS e convertida para tempo, o que independe do FPS. As três
   constantes do snap (`0x24f17f8`, `0x24f17fc`, `0x24f1800`) só são lidas pelo `SmoothDeltaTime`.
   Não auditei cada uma das outras: a validação foi empírica.
6. **Lua:** 620 scripts do `trico_boot` mais 170 do `bootp`. As lógicas de tempo usam `dt` (`TickSoldiers(deltaTime)`,
   `LT_SumDeltaTime + dt`, `GetGameDeltaTime()`). Há contadores por tick, como `autorun_campause_countdown`
   (só no autorun de debug) e `animWaitFrame` (s13_firstflight), que podem rodar 2× mais rápido a 60. **A verificar.**

## Patches (eboot 1.03)

| Nome | Endereço | Esperado → novo | Modo |
|---|---|---|---|
| `flip_rate_60` | `0x1c5151a` | `be01000000` → `be00000000` (`SetFlipRate(h,0)`) | 60, livre |
| `dt_snap_60` | `0x24f17f8` / `0x24f17fc` / `0x24f1800` | 0,035 / 1/30 / 0,031667 → 0,0175 / 1/60 / 0,015833 | 60 |
| `max_fps_double` | `0x12091db` | `vmovss xmm1,[1.0]` → `[0.5]` (`0x24f17e8`) | nenhum (teste) |
| `max_fps_off` | `0x12091e3` | `vdivss` → `vxorps xmm1,xmm1,xmm1` | nenhum (teste) |

O `TLG_ENGINE_FPS` (30/60/240) fica sendo o teto do "Limite de FPS" do overlay. Assim, o menu nunca
promete mais do que o modo entrega.

## Validação (RTX 2060, Ryzen 5700X3D, `uptime` < 4, janela 1265×712)

| Cena | 30 | 60 | Livre (VSync desligado, limite 240) |
|---|---|---|---|
| Boot/logo | 30,0 | 60,0 | 240 |
| Menu inicial | 30,0 | 59,6–60,2 (pior quadro 16,7–33,3 ms) | ~104 |
| Intro do New Game | 30,0 | 44–49 | — |
| Gameplay (Continue, caverna perto do Trico) | 30,0 | 40–50 | 38–45 (limite de desempenho, não de trava) |

- **Velocidade da intro:** com screenshots a cada 10 s depois do New Game, nos modos 30 e 60, as
  cenas batem nos mesmos instantes de relógio do +40 s ao +120 s. A diferença é de ~1 s, por causa
  do carregamento; o jogo não ficou 2× mais rápido. Os quadros variaram entre 44 e 49 FPS, então o
  dt variável também foi exercitado.
- **Gameplay:** Continue, 4 s andando para frente (`ly=0`), giro de câmera de 2 s (`rx=255`) e um
  pulo. A distância percorrida e o ângulo da câmera ficaram iguais nos modos 30 e 60. As legendas
  da narração aparecem no mesmo ponto.
- **Observação do usuário** (assistindo à janela): a 240 FPS no boot, ~100 no menu e ~50 depois,
  música e animações pareciam estar na velocidade normal, sem aceleração visível.
- **Piores quadros de 33 ms a 60:** é a quantização do vblank de 60 Hz. Um quadro atrasado espera
  o vblank seguinte, e abaixo de 60 FPS os quadros alternam 16,7/33,3 ms (judder). O modo livre
  apresenta assim que o quadro fica pronto (vblank de 480 Hz) e evita isso, mas o monitor de 60 Hz
  com VSync volta a quantizar.
- **Crash corrigido no caminho:** `Host fault … libnvidia-glcore … address 0x130` na
  `Scheduler::RecorderThread`, logo depois de `scheduler used on the GPU command thread … Runtime::CopyBuffer`,
  no começo da intro. Aconteceu 3 de 3 vezes a 60 e 1 de 2 vezes a 30. Causa: o `EndRendering()` lia `is_rendering` (estado do
  stage B) antes do owner hook drenar o draw pipe. Um "não está renderizando" velho deixava o
  `vkCmdCopyBuffer` ser gravado dentro do render pass que o stage B abriu. Correção: `CheckOwner`
  no início do `EndRendering` (`vk_scheduler.cpp`). Depois dela, a intro e o gameplay a 60 rodaram
  sem crash (2 sessões de ~3 min).

## O que falta (testar à mão)

1. **Física e Trico:** pulos, escaladas no pelo do Trico, o Trico pulando entre plataformas, barris,
   correntes e tecidos (Havok). O dt chega ao Havok pelo objeto em `app+0xb0`. Não confirmei se o
   passo interno é fixo.
2. **Cutscenes longas e sincronia de áudio:** fala, música e lábios, por exemplo na lança e na
   primeira comida do Trico.
3. **Contadores por quadro nos scripts** (`animWaitFrame`, contadores `RegisterTick` sem `dt`): pontes que
   caem no s13_firstflight, timers de puzzle.
4. **Câmera e input:** sensibilidade e inércia da câmera em 30 × 60 × livre.
5. **Desempenho:** o gameplay a 60 fica em 40–50 FPS nesta GPU. Pode valer usar o limite de 30
   no overlay, ou o modo livre com VRR.
6. **Livre acima de 120 FPS:** não testado no gameplay. O GoW3 quebrava acima de ~120; aqui o
   limite padrão também é 120.
7. Achar quem lê `game+0x180` (`SetMaxFps`). Se for um dt mínimo em algum sistema, este é o primeiro
   suspeito para qualquer aceleração.

## Isolated EU 01.00 v6 slow-motion precision test (2026-10-20)

Read-only inspection of a frozen 60-FPS catch found game speed 0.15, positive
~2.02-ms filtered time, and exactly zero published game delta. Rendering and the
application frame counter continued. The native smoother at image +0xc51940
still used `floor(dt*360+0.1)/360`; feedback/jitter could push a slow step below
its 2.5-ms first-tick threshold and leave animation/mission completion stalled.

`port/scripts/tlg_slowmotion_60.py` is an opt-in private-v6 patch, NOT a change to
the general 30-FPS/default launcher. It requires the exact EU ELF hash, verified
clock/scale/zero-gate instructions, and the exact five 60-FPS writes plus native
1440p. It changes only the two clock-grid constants to 36000000 and its reciprocal.
The filter, bias, game-speed curves, native near-zero epsilon, zero-speed/overlay
pauses, instructions and original 30-FPS profile remain unchanged. Two extra
4-byte writes make eight private profile writes / 45 bytes total with the
vegetation-cadence correction enabled. Unknown,
30-FPS, unlocked and malformed/duplicate profiles fail closed without writing.

`tests/test_slowmotion_clock_win.cpp` executes the real original EU leaf routine
in isolated fixtures. It reproduces the recorded freeze, tests the corrected
clock over authored/stress speeds, jitter, frame-rate variation and pause/resume,
and compares the unchanged 30-FPS path bit-for-bit. No running game is attached,
suspended, stopped, patched, or supplied inputs by these tests. A static audit of
620 extracted Lua files additionally found the Pit catch's 0.10x slowdown; the
shared clock correction covers that mechanism too. Full gameplay progression
and every dynamically authored sequence still need manual testing.

## Isolated EU 01.00 v7 shared animation/physics clock (2026-10-20)

The v6 catch no longer froze, but the user reported the boy and Trico's tail
missing one another. Native physics at image +0xe99dd6 independently floors
frame-rate-object +0x39c onto 1/360-second ticks. The v6 fine output could stay
positive while physics discarded almost all of it. Executing the actual native
quantizer on the recorded fixture gives 2.905417 seconds of animation time but
0.133333 seconds of physics time over the same 1200 updates.

`clock_sync_60.[ch]` is a separate opt-in native loader hook, requiring
`TLG_CLOCK_SYNC_60=1`, the complete exact EU smoother, native physics signatures,
actual 60-FPS patches and v6's fine grid. It retains the native filter/feedback,
then publishes one common 360-Hz-grid timestep to animation/AI and physics,
carrying fractional seconds across frames. Intentional pauses clear residual
time. No minimum-speed clamp, extra solver work, mission/catch-volume edit or
automatic successful grab is introduced. Default/30-FPS launchers remain off.

`test_clock_sync_60_win.cpp` executes the real smoother through the production
SysV direct-call relay/both vtable hooks and actual physics quantizer. The original
smoother code and its Windows red-zone protection groups remain untouched.
The recorded clocks
now both advance 2.905556 seconds. It covers 291600 native updates at 24-120 Hz,
slow/ramp/fast speeds and pauses, 909 rejected byte/pointer mutations, and 30000
bit-identical original 30-FPS updates. These offline fixtures establish the
clock mismatch and its correction; the real tail catch/full playthrough still
require user testing in the separate v7 package. No game process is launched,
attached, suspended, stopped or patched by the fixture.

## Isolated v8 climbing diagnostics (2026-10-20; NOT a new gameplay fix)

The user reports the v7 tail catch succeeds. Remaining symptoms are repeated
rocking during Trico shakes and occasional climbing without upward progress.
The original graph contains separate movement-blocked climb-stop transitions
(`Hang_Moveable == 0`) and acceleration-gated shake reactions. Existing frame
statistics do not reveal which predicates were present during the symptom.
No shake threshold, grip/stamina strength, timer or collision rule is changed.

`climb_diagnostics.[ch]` adds an explicitly opt-in `TLG_CLIMB_DIAG=1` sampler
after the existing exact-EU/60-FPS input wrapper. Nine native property-offset
registrations must match first. It reports the latest published input, contact,
movement availability, acceleration and impulse values once per second per
active input sensor. It adds no guest hook and does not identify animation
events merely from a threshold crossing. Sensor values can be one world update
old; pointer-labelled sensors need correlation with user observations. The
disabled path reads no sensor data, and the original 30-FPS profile remains off.

The native fixture rejects 90 schema mutations and verifies 10000 samples
without any synthetic sensor-byte changes. Retained input/shared-clock tests
pass. The separate v8 package uses an independent latest v7 save, English,
native 1440p, 60 FPS and no timer. It is diagnostic, not a verified climbing fix,
and requires a user-authorized run before a correction can be selected safely.

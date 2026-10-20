<p align="center"><img src="port/packaging/icon/tlg-icon-1024.png" width="160" alt="The Last Guardian PC port project icon, inherited from upstream"></p>

<h1 align="center">The Last Guardian — community PC port</h1>

<p align="center">
  <a href="https://github.com/b3ndoi/tlg_pc/actions/workflows/build.yml"><img src="https://github.com/b3ndoi/tlg_pc/actions/workflows/build.yml/badge.svg" alt="Fork Windows and Linux builds"></a>
</p>

A community-maintained fork of **[HayatoG/tlg_pc](https://github.com/HayatoG/tlg_pc)**,
maintained here by **[b3ndoi](https://github.com/b3ndoi)**. Our focus is Windows
stability, carefully guarded 60 FPS timing corrections, native 2560×1440
experiments, and clearer testing and release documentation.

The original PS4 game's CPU code runs natively on an x86-64 PC. The port
reimplements the PS4 services it needs and translates its GPU commands and
shaders to Vulkan. This is a continuation of existing community work, not a
new game or a claim of ownership over The Last Guardian.

> **Experimental software. 30 FPS remains the default.** Targeted 60 FPS
> playtesting is not full-campaign validation. No game executables, game
> archives, console firmware, saves or extracted trophy assets are included.
> You must supply your own game files.

[What this fork adds](#what-this-fork-adds) ·
[Testing and limitations](docs/TESTING.md) ·
[Builds](#builds-and-release-status) ·
[Getting started](#getting-started) ·
[Credits and license](#credits-and-license)

## What this fork adds

- **Windows stability:** speculative GPU-readback fault recovery, nested recovery
  handling and queued-command ordering to address identified deadlocks.
- **Rendering correctness:** preservation of contents when 3D texture depth
  grows, bounded common-mip copies and display-surface coherence corrections.
- **Checkpoint reload protection:** a narrowly guarded fix for an identified
  NULL-read site in the exact EU 01.00 executable, not blanket fault suppression.
- **Experimental 60 FPS timing:** opt-in input-hold and selected script-timer
  corrections, plus synchronized slow-motion animation and physics clocks.
- **Experimental native 1440p:** a guarded regular-engine 2560×1440 profile,
  distinct from the earlier scene-supersampling path with a 1080p final image.
- **Experimental device prompts:** optional keyboard/mouse, PS5 and Xbox
  tutorial/controller-guide images, automatic switching or a manual override,
  and a display-resolution guide using an optional local controller PNG.
  [Coverage and limitations](docs/BUTTON_PROMPTS.md); original prompts stay default.
- **Testing and release safeguards:** CPU-only regression fixtures, Windows/Linux
  build and package checks, a release checklist and manual draft-only release
  creation.

These changes build on upstream's loader, runtime, Vulkan renderer, controller
and mouse/keyboard support, saves, shader cache, image filters and optional
Mods/Cheats support. Existing authorship and history are retained.

## Compatibility and current limits

| Area | Current position |
|---|---|
| Default mode | 30 FPS retained; experimental timing hooks are opt-in and guarded out of 30 FPS |
| Additional 60 FPS gameplay corrections | Windows, exact CUSA03745 EU 01.00 signatures and applied 60 FPS patch bytes only |
| Native 2560×1440 at 60 FPS | Targeted private playtesting; developer-only profile, not a fully integrated launcher preset |
| Tail-catch slow-motion sequence | Targeted private tests progressed through the catch after the timing corrections |
| Climbing and Trico shaking | Repeated rocking/climbing-in-place reports remain under investigation |
| Windows and Linux packages | Both build and package in CI; a successful build is not gameplay certification |
| Full campaign / other hardware | Not validated by this fork's targeted tests |

**Do not reuse the EU 01.00 offsets on US builds or EU 01.03.** The upstream
US 01.03 FPS profile is separate from this fork's additional EU 01.00 timing
corrections. Supported language selection does not imply that every executable
revision has the same experimental fixes.

The launcher's ordinary **60 FPS** option does **not** automatically enable the
complete experimental timing/native-1440p profile. See the
[developer profile and release gates](docs/FIRST_RELEASE.md) before testing it.
No stamina, aggression, shake-threshold or automatic-grab cheat was added.

## Tested system and evidence

Our targeted Windows playtesting has used:

| Component | Test system |
|---|---|
| CPU | AMD Ryzen 7 9800X3D, 8 cores / 16 threads |
| GPU | AMD Radeon RX 9070 XT, 16 GB VRAM |
| Memory | 32 GB RAM |
| OS | Windows 11 Home, build 26200 |

This is a test configuration, **not a minimum specification**. Private tests
have covered 1080p / 30 FPS and native 1440p / 60 FPS with the exact EU 01.00
build. Reports of steady frame rate and successful catches are useful
observations, not published average-FPS, 1%-low or whole-game guarantees.

[Testing notes](docs/TESTING.md) separate automated checks, player observations
and remaining work. New benchmark captures and screenshots will be labelled
with the build, resolution, settings and tested scene.

### Upstream screenshots

These inherited screenshots demonstrate the upstream port on Linux with an
RTX 2060 at 1920×1080. They are **not** screenshots or benchmarks of this fork's
Windows native-1440p profile.

| | |
|---|---|
| ![Upstream 1080p screenshot: the boy and Trico](docs/screenshots/03-trico.jpg) | ![Upstream 1080p screenshot: ruins](docs/screenshots/04-ruinas.jpg) |

## Builds and release status

This fork is preparing its first release; **no public fork release has been
published yet**.

- [GitHub Actions](https://github.com/b3ndoi/tlg_pc/actions/workflows/build.yml)
  produces `tlg-windows-x86_64.zip` and `tlg-linux-x86_64.tar.gz` as CI artifacts.
- Approved public builds will appear under
  [this fork's Releases](https://github.com/b3ndoi/tlg_pc/releases).
- Pushes and pull requests build artifacts; they do not automatically publish
  a release. Manual release creation produces a draft for inspection.
- Candidate gameplay smoke tests and final source/dependency-license review
  remain release gates. See the [checklist](docs/FIRST_RELEASE.md).

Upstream releases remain available from
[HayatoG/tlg_pc](https://github.com/HayatoG/tlg_pc/releases), but they are separate
builds and must not be described as containing this fork's changes.

## Getting started

You need an x86-64 Windows or Linux PC, a Vulkan 1.3-capable GPU, and your own
matching game files. Linux CI packages target glibc 2.39 or newer. The test
machine above does not establish minimum hardware or performance on other PCs.

1. Extract an appropriate build into its own directory.
2. Supply your own game files and select their folder in the launcher. Keep
   executable, metadata and modules from the same game revision.
3. For native audio, supply `libSceNgs2.sprx` from your own console firmware in
   `system_lib/`. No firmware download is provided by this project.
4. Select the desired game language in the launcher; English is available in
   the relevant US/EU language profiles. Keep 30 FPS for the baseline.
5. Launch normally. **F10** toggles the FPS counter; **Insert** opens the port
   menu. **Esc** releases captured mouse input.

The inherited [player guide](port/packaging/README-player.md) covers controls,
save locations and the upstream US 01.03 setup. For this fork's exact EU 01.00
experimental profile, use [FIRST_RELEASE.md](docs/FIRST_RELEASE.md), not the
guide's US update requirements or another revision's offsets.

Use a physically separate save copy for experimental testing. An extracted
package alone does not isolate everything: launcher settings are shared under
the user's configuration directory. Never edit a running session's files,
saves, cache or settings while preparing a different test.

### Build from source

```bash
git clone --recursive https://github.com/b3ndoi/tlg_pc.git
cd tlg_pc/port
TLG_LTO=OFF bash build.sh
cd ..
./tlg_launcher.sh
```

Windows builds use MSYS2 CLANG64; see the
[Windows build guide](port/packaging/windows/README.md).
The [CI workflow](.github/workflows/build.yml) documents both platforms.
The [runtime overview](port/README.md), [timing notes](docs/60fps.md) and
[changelog](CHANGELOG.md) contain implementation details. Some inherited
technical documentation is in Portuguese and records earlier experiments;
use the current release checklist for this fork's supported boundaries.

## Launcher and local achievements

The tabbed launcher separates Play/setup, Video, Controls, Achievements, Session
log and About. It displays the selected game's title ID/revision rather than a
fixed US revision label, and keeps the baseline/experimental FPS distinction
visible. English and Portuguese interface text lives in data-only translation
catalogs, with English fallback for additional languages.

New trophy-unlock events from games started through this launcher or its
headless `--play` path can be recorded under
`user/achievements/<TITLE_ID>.json`. Repeated events are deduplicated. A
responsive grid reads the owner's local trophy icons and decrypted XML names;
hidden or unknown entries are masked with a question mark by default. An explicit
spoiler opt-in can show unknown icons without inventing names or unlocks. No artwork, keys
or extracted game metadata are bundled. The experimental 60-FPS tracking path
can opt into native per-user/title persistent unlock queries; 30-FPS/default
native semantics stay unchanged. Old save/PSN progress and custom challenges
are **not** guessed or automatically imported.

Optional Windows notifications are off by default. Unlocks still persist if
Windows suppresses a notification. No existing game/log is attached to or
backfilled. See the [launcher and achievement guide](docs/LAUNCHER.md).

## Next steps

1. Publish clear, reproducible test results and prepare an inspected release
   candidate.
2. Expand translations and test the redesigned launcher on more desktop/DPI
   configurations; integrate the complete experimental profile separately.
3. Consider richer local trophy metadata and custom achievements later. No
   custom challenge rules have been added.

These remaining tasks are not advertised as completed features. The default
frame rate and native gameplay/timing code remain unchanged by the launcher work.

## Credits and license

**Original TLG port:** [HayatoG](https://github.com/HayatoG) and
[HayatoG/tlg_pc contributors](https://github.com/HayatoG/tlg_pc/graphs/contributors).
This fork continues that work and does not replace its authorship.

**Code lineage:** [FelipePrado0/gow3_pc](https://github.com/FelipePrado0/gow3_pc),
Supermedo/bloodborne_pc, [deadinside28/bloodborne_pc](https://github.com/deadinside28/bloodborne_pc)
and the [shadPS4](https://github.com/shadps4-emu/shadPS4) Vulkan video core.
ATRAC9 audio uses [LibAtrac9](https://github.com/Thealexbarney/LibAtrac9).
See [UPSTREAM.md](port/UPSTREAM.md) for the retained provenance and
[VENDOR.txt](port/gpu/VENDOR.txt) for third-party notices. The project icon is
original artwork inherited from the upstream project.

The port retains its existing **GNU GPL v2-or-later** licensing as documented
in [UPSTREAM.md](port/UPSTREAM.md) and [LICENSE](port/LICENSE). Third-party
components retain their own licenses and copyright notices. Existing license
files, source notices and Git authorship are unchanged.

Upstream links: [YouTube @hayatog-dev](https://www.youtube.com/@hayatog-dev) ·
[upstream Discord](https://discord.gg/UMkdMYZh9g) ·
[support HayatoG](https://github.com/sponsors/HayatoG).

This project is not affiliated with Sony Interactive Entertainment, SIE Japan
Studio or genDESIGN. The Last Guardian is a trademark of Sony Interactive
Entertainment; rights in the game and its assets remain with their respective
owners. Maintaining this fork does not transfer ownership of their work.

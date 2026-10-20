# Testing, evidence and limitations

Last documented: 2026-10-20. This page describes what has actually been checked,
not a promise that every scene, executable revision or hardware configuration
works. The fork's default remains 30 FPS.

## Reference Windows playtest system

| Component | Verified configuration |
|---|---|
| CPU | AMD Ryzen 7 9800X3D, 8 cores / 16 threads |
| GPU | AMD Radeon RX 9070 XT, 16 GB VRAM |
| Installed memory | 32 GB |
| OS | Windows 11 Home, build 26200 |
| Discrete GPU driver | Windows driver version 32.0.31041.1004 |
| Game used for the additional timing tests | CUSA03745 EU 01.00, exact revision described in [FIRST_RELEASE.md](FIRST_RELEASE.md) |

Hardware and Windows driver fields were checked locally on 2026-10-20. The
driver version is the Windows-reported number, not an inferred Adrenalin
package version. This system is a test reference, not a minimum specification.
No personal machine identifiers, account names or private paths are published.

## Keep three kinds of evidence separate

### Automated build and offline regression results

The first-release preparation was integrated as main commit
[`8184a2c`](https://github.com/b3ndoi/tlg_pc/commit/8184a2cb5d1d1c44ea003229d1d6d6e6f7f3a62d).
Its source tree matches preparation commit `f146738`.

- [Post-merge CI](https://github.com/b3ndoi/tlg_pc/actions/runs/39421826391):
  Windows and Linux compilation, packaging and artifact uploads passed.
- The Windows asset-free CI regression step passed. The full private offline
  suite, using an owner's local ELF for the additional native fixtures, passed
  24 Python tests and 11 native suites.
- Targeted native fixtures exercised 25353 input updates, 291600 shared-clock
  updates, 909 rejected guard mutations and 213180 smoother updates.
- Two separate 30000-update comparisons preserved the tested original 30-FPS
  clock routines bit-for-bit, including pauses and slow motion. This is not a
  claim that the entire game has been proven equivalent.
- Downloaded PR-build archives passed basic content and static dependency
  checks. No game/firmware files, saves, player settings or session logs were
  present. This does not replace a complete source/dependency-license audit.

These checks did not launch, attach to or reconfigure the player's game. CI
success does not demonstrate correct pixels, successful gameplay interactions
or a completed campaign. See the [regression instructions](FIRST_RELEASE.md#regression-commands).

### Private gameplay observations

| Profile | Observations | What remains unproven |
|---|---|---|
| 1920×1080, true 30 FPS | Player reported that 30 FPS worked well and climbing was easier; the baseline session started in 30-FPS mode without FPS patch writes | These observations are from private test copies, not a fresh smoke test of the CI-built candidate |
| Native 2560×1440, 60 FPS, guarded EU timing profile | Player reported a mostly steady frame rate; corrected private v7/v8 tests progressed through the slow-motion tail catch | No controlled public average-FPS / 1%-low benchmark; repeated rocking/climbing-in-place reports remain unresolved; full campaign unvalidated |

The native profile changes the regular engine mode and presentation to
2560×1440. It must not be confused with the older 1440p scene-supersampling
experiment whose final display/HUD stayed at 1080p. A desktop screenshot's
pixel dimensions alone do not establish the game's internal render resolution.

These are targeted observations, not a guarantee of locked 60 FPS or flawless
rendering. Earlier unsuccessful test versions and their screenshots must not
be presented as the current candidate. The regular launcher's 60-FPS selector
does not enable the complete developer-only profile by itself.

### Candidate acceptance tests still needed

- User-authorized smoke tests of the actual CI-built Windows package, with a
  separate user/save directory and no changes to an existing running session.
- Baseline 1080p / 30 FPS checks and native 1440p / 60 FPS checks kept separate.
- Repeatable coverage of the catch sequence, climbing/Trico shaking, checkpoint
  reload, save/load and representative rendering-heavy scenes.
- More hardware and driver coverage; Linux gameplay validation of this fork's
  changes is not established by its successful CI build.
- Explicit review of the remaining [release gates](FIRST_RELEASE.md#release-gates).

## Launcher follow-up checks

Launcher/trophy follow-up: the local Windows suite passed 76 Python tests and
13 native fixtures, including hidden-card privacy, bounded TRP/XML/PNG readers,
save-copy auditing, persistent native flags, per-user/title isolation, native
API queries, and Python/native state migration. The 30-FPS original-routine
comparisons remain bit-identical. These offline tests start no game, map no
launcher window and send no real desktop notification. A separate manually
authorized older UI test run is not evidence that these newer changes have
passed live acceptance. See [LAUNCHER.md](LAUNCHER.md) for the
separate visual/live acceptance steps; the historical CI links above refer to
the initial release-preparation commit, not this later UI change.

## Publishing useful performance results

For each future result, record the commit/build, game revision, CPU/GPU/RAM,
OS/driver, internal and output resolution, FPS mode, VSync, upscaler, timing
switches, renderer budget, warm-up/cache condition and the tested route/duration.
Keep foreground and minimized-window measurements separate.

Report average FPS and frame-time distribution only from a suitable capture.
Use per-frame samples for 1%-low or percentile frame-time results; five-second
FPS summaries alone are not sufficient. Mark loading, shader warm-up and
isolated spikes rather than silently excluding them. Record repeated trials
and distinguish a slowdown from an actual gameplay freeze.

Screenshots should identify their build and scene. Include useful resolution
and performance evidence without exposing personal paths, account details or
spoilers without a label. Link captures to the corresponding test entry; do
not invent missing measurements or distribute extracted game/firmware assets.

Until those captures are collected, no new numerical 1440p60 benchmark is
advertised. The inherited README screenshots are labelled as upstream Linux
1080p examples, not evidence for this fork's Windows 1440p performance.

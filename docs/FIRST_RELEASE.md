# First fork release — Windows candidate

Prepared, not published. Based on HayatoG/tlg_pc PR #69 commit `63ba4f5`;
existing authorship, history, GPL and third-party notices are retained.
Upstream main through `b8d5f41` is integrated in a separate merge commit,
preserving its Mods/Cheats support with nothing enabled by default. Track
later changes through `upstream`. The subsequent tabbed launcher/local trophy
observer is documented separately in [LAUNCHER.md](LAUNCHER.md).

## Commit groups

1. Windows speculative-readback deadlocks, nested recovery and GPU command ordering.
2. 3D texture-depth growth and bounded common-mip copies.
3. Opt-in Windows pacing, minimized-window reporting and native display coherence.
4. Exact EU reload protection and opt-in 60-FPS input/script/shared-clock fixes.
5. Source-only regression runner, release safeguards and documentation.

Related upstream work: #69, #75 and #79. The #75 launcher/artwork redesign is
not imported. FSR-Vulkan's pinned submodule stays unchanged: build.sh applies
the existing tracked patches, not a new private submodule commit.

## Boundaries

- Normal gameplay defaults stay unchanged, including 30 FPS. The 30-FPS patch
  mode writes no FPS patches. Timing hooks require explicit switches, exact EU
  signatures and actual 60-FPS patch bytes.
- Additional input/script/shared-clock hooks are Windows-only and target
  CUSA03745 EU 01.00, ELF SHA256
  `580ba4bc7f9b785bfde0948be20ec67a30ca8c9318606ba5cbf28a1a01d54565`.
  Never reuse these offsets for US/EU 01.03. The upstream US FPS profile remains
  separate; these extra gameplay fixes are not validated there.
- Native 1440p changes the regular engine mode, not the Pro/checkerboard entry
  or the older host scene-proxy supersampling path.
- Private v7/v8 tail catches succeeded. Repeated rocking/climbing stalls remain
  under investigation. No aggression, stamina, shake threshold, catch volume
  or automatic-grab cheat was added. Full 60-FPS campaign not validated.
- Climbing diagnostics are disabled by default and are not a gameplay fix.

## Opt-in tested 1440p / 60 FPS launcher preset

In **Video → Frame rate**, choose **1440p / 60 FPS — tested EU preset**.
This is separate from the ordinary 60-FPS option and is never selected by default.
It reproduces the successful private **batching-OFF control**: native regular-mode
2560×1440, English, fullscreen FIFO VSync, five EU FPS/vegetation writes plus
one native-resolution write and two slow-motion writes (eight / 45 bytes),
input/script/shared-clock hooks, and precise Windows pacing. The existing
Windows deadlock/texture/display/reload fixes remain in the native executable.

Only Windows + CUSA03745 EU 01.00 is accepted. The launcher checks metadata,
the ELF SHA256 above, every existing patch signature, and the complete generated
patch list. Unsupported images fail closed before launching, rather than silently
falling back to a partial profile. Mods or `TLG_FPS_PATCHES` substitutions are
rejected if they change the expected five base writes. Installed game assets
are read-only; only this copy's generated loader patch file is extended.

Readback batching, deferred/stale readback, and climb/input/tail observers are
explicitly off, even if inherited from an experiment's environment. The older
host scene-proxy supersampling path stays off. Preset-specific safety settings
win over conflicting environment/extra overrides. Ordinary modes retain their
existing override behavior; `TLG_FPS=30` also overrides a saved preset selection.

The default launch remains **untimed** (`--timeout 0`). The selected audio,
controls, trophy preferences and VRAM budget are not changed. Choose a budget
appropriate for your hardware: the private test used an RX 9070 XT with 16 GB
and 10500 MB, not a budget safe to force on every GPU. This is not a locked-60
guarantee; Trico-heavy scenes and audio still need further testing.

The preset writes **user/tlg-1440p60.ini**, not the ordinary **user/tlg.ini**.
Returning to 30 FPS uses the original INI and no extra preset patches/hooks;
its defaults, gameplay code and timing are unchanged. Saves/cache remain in
this package's user directory. Opening/selecting the option does not patch,
launch, or edit any running copy. For gameplay A/B tests use a separate package
with a physical copy of your save, never files used by an active session.

### Low-level profile helpers

Prepare a separate package/user directory and physical save copy, never files
used by a running session. Produce the five guarded EU 60-FPS writes using
`tlg_patches.py`. On that private patch-file copy, call
`tlg_native_resolution.apply_private_patch(elf_path, patch_path)` then
`tlg_slowmotion_60.apply_private_patch(elf_path, patch_path)`: eight writes,
45 bytes with the EU vegetation-cadence A/B. Preserve ISA/red-zone preparation
and check for hook overlaps.

Private switches: `TLG_ENGINE_NATIVE_RESOLUTION=2560x1440`,
`TLG_INPUT_TIMING_60=1`, `TLG_TIMING_60=1`, `TLG_CLOCK_SYNC_60=1`,
`TLG_UPSCALER=off`. Keep the older `TLG_NATIVE_OUTPUT` path absent/0.
`TLG_PRECISE_PACING=1` is optional; keep `TLG_CLIMB_DIAG` off except for research.
Set output to 2560x1440, English (`game_language=en`, `TLG_LANGUAGE=1`), an
appropriate VRAM budget and `--timeout 0`. The launcher preset now automates
this sequence with extra guards and video-INI isolation. The ordinary 60-FPS
option still does not enable the complete profile.

## Regression commands

From `port`, with MSYS2 CLANG64 on PATH:

```powershell
python tests/run_release_regressions.py
python tests/run_release_regressions.py --elf C:/private/eboot.elf
```

First command is asset-free CI. Second uses an owner-provided local ELF for
additional offline native fixtures. No game launch/attachment, GPU/controller
access or ELF modification occurs. Exact Lua/archive tests separately need
local extracted assets and Lupa Lua 5.1; never upload those fixtures/scripts.
Full clock-function reference bytes were replaced by SHA256 fingerprints;
optional tests obtain original functions from the owner's ELF at runtime.

## Release gates

- [x] Curated source-only commits with original history/credits/licenses.
- [x] Launcher defaults unchanged and experimental switches opt-in.
- [x] Fresh Windows CPU-only regressions pass: 24 Python tests, 11 native suites;
      909 clock guard mutations rejected, 291600 shared-clock updates, 213180
      native smoother updates, two 30000-update bit-identical 30-FPS comparisons.
- [x] Fork created under b3ndoi and the five curated commits pushed for review.
- [x] Clean Windows/Linux compilation, packaging and artifact uploads pass in
      [post-merge CI for main `8184a2c`](https://github.com/b3ndoi/tlg_pc/actions/runs/39421826391).
- [ ] Packages/source inspected: no game/firmware, dumps, saves, caches, private
      paths, session logs or research data; matching source/licenses included.
- [ ] User-authorized candidate smoke tests at 1080p30/native1440p60.
- [ ] Remaining climbing limitation accepted/documented.
- [ ] Manually create and inspect a draft release; separately approve publication.

Pushes do not publish releases. Manual dispatch can create a draft only.
Build checks and targeted private gameplay observations are recorded separately
in [TESTING.md](TESTING.md); they do not complete the candidate smoke-test gate.
The launcher now has translation catalogs and a first local trophy-observation
pass. The explicit 1440p/60 launcher preset has CPU-only guards/tests; fresh
packaged gameplay acceptance remains separate. Custom achievements are not implemented.

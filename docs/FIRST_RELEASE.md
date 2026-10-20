# First fork release — Windows candidate

Prepared, not published. Based on HayatoG/tlg_pc PR #69 commit `63ba4f5`;
existing authorship, history, GPL and third-party notices are retained.
Upstream main through `b8d5f41` is integrated in a separate merge commit,
preserving its Mods/Cheats support with nothing enabled by default. Track
later changes through `upstream`. The startup redesign remains deferred.

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

- Normal launcher UI/defaults stay unchanged, including 30 FPS. The 30-FPS patch
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

## Developer-only experimental profile

Prepare a separate package/user directory and physical save copy, never files
used by a running session. Produce the four guarded EU 60-FPS writes using
`tlg_patches.py`. On that private patch-file copy, call
`tlg_native_resolution.apply_private_patch(elf_path, patch_path)` then
`tlg_slowmotion_60.apply_private_patch(elf_path, patch_path)`: seven writes,
41 bytes. Preserve ISA/red-zone preparation and check for hook overlaps.

Private switches: `TLG_ENGINE_NATIVE_RESOLUTION=2560x1440`,
`TLG_INPUT_TIMING_60=1`, `TLG_TIMING_60=1`, `TLG_CLOCK_SYNC_60=1`,
`TLG_UPSCALER=off`. Keep the older `TLG_NATIVE_OUTPUT` path absent/0.
`TLG_PRECISE_PACING=1` is optional; keep `TLG_CLIMB_DIAG` off except for research.
Set output to 2560x1440, English (`game_language=en`, `TLG_LANGUAGE=1`), an
appropriate VRAM budget and `--timeout 0`. A polished public UI/profile
integration is deferred; the existing launcher does not automatically enable
this complete profile when its ordinary 60-FPS option is selected.

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
- [ ] Clean Windows/Linux builds pass in GitHub Actions.
- [ ] Packages/source inspected: no game/firmware, dumps, saves, caches, private
      paths, session logs or research data; matching source/licenses included.
- [ ] User-authorized candidate smoke tests at 1080p30/native1440p60.
- [ ] Remaining climbing limitation accepted/documented.
- [ ] Manually create and inspect a draft release; separately approve publication.

Pushes do not publish releases. Manual dispatch can create a draft only.
Next: message catalogs, startup UI, then persistent local achievements.

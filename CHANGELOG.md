# Fork changelog

## Unreleased — first Windows candidate

- Fix speculative GPU readback deadlocks and queued-command ordering.
- Preserve expanding 3D texture contents and bound shared copies.
- Retain display-surface contents and native-output coordinates.
- Protect the exact EU 01.00 checkpoint-reload NULL site.
- Add opt-in EU 01.00/Windows input/script timing corrections and synchronized
  slow-motion animation/physics clocks. Original speed curves/pauses retained.
- Retain guarded native 1440p and optional Windows pacing. Climbing diagnostics
  are optional, not a gameplay fix. Full 60-FPS campaign not validated.
- Keep existing launcher UI and 30-FPS defaults unchanged.
- Replace embedded original clock-function bytes with SHA256 fingerprints.
- Add CPU-only regressions, release checklist and manual draft-only publication.
- No game/firmware files, saves, private logs or research dumps added.

Credits: HayatoG/tlg_pc and contributors; shadPS4, gow3_pc, bloodborne_pc,
LibAtrac9 and dependencies retain their existing notices/licenses. Related
upstream work includes #69, #75 and #79; their revision-specific offsets are not
interchangeable with this fork's EU 01.00 profile.

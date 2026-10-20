# Fork changelog

## Unreleased — first Windows candidate

- Add optional device-aware tutorial/controller-guide prompts with automatic
  selection, sticky manual overrides and original/off defaults. Use host-only,
  exact-fingerprint texture replacement; geometry-based menu symbols stay original.
- Add a full-resolution optional local PS5 image and a scalable in-menu guide
  with button callouts and effective keyboard/mouse bindings. Supplied artwork
  stays private; public fallback icons are independently code-drawn.
- Add a tabbed launcher, detected game/revision labels and extracted interface
  translation catalogs, retaining the original credits and 30-FPS defaults.
- Record existing trophy events locally for newly launched GUI/headless
  sessions, with deduplication, atomic storage and optional Windows notifications.
  Add a responsive trophy grid with owner-supplied names/icons, hidden-entry
  masking and bounded TRP/XML parsing. No game artwork or keys are bundled.
- Offer an explicit spoiler opt-in for icons whose hidden status is unknown;
  names/unlocks are not invented, and known hidden trophies remain masked.
  Exclude extracted trophy assets from Git and reject them during packaging.
- Add opt-in native persistent trophy flags/timestamps for the experimental
  60-FPS tracking path, with deduplication, user/title isolation and atomic
  state bridging. Default/30-FPS behavior and gameplay timing stay unchanged.
- Audit offline save copies without guessing trophy unlocks from progress
  counters. No custom challenges, PSN synchronization or automatic save import.
- Test withdrawn widgets, persistence/error paths and frozen package resources
  without launching a game or sending real desktop notifications.
- Fix speculative GPU readback deadlocks and queued-command ordering.
- Preserve expanding 3D texture contents and bound shared copies.
- Retain display-surface contents and native-output coordinates.
- Protect the exact EU 01.00 checkpoint-reload NULL site.
- Add opt-in EU 01.00/Windows input/script timing corrections and synchronized
  slow-motion animation/physics clocks. Original speed curves/pauses retained.
- Retain guarded native 1440p and optional Windows pacing. Climbing diagnostics
  are optional, not a gameplay fix. Full 60-FPS campaign not validated.
- Keep 30-FPS defaults unchanged; the initial preparation retained the upstream
  UI before the separate launcher redesign.
- Replace embedded original clock-function bytes with SHA256 fingerprints.
- Add CPU-only regressions, release checklist and manual draft-only publication.
- No game/firmware files, saves, private logs or research dumps added.

Credits: HayatoG/tlg_pc and contributors; shadPS4, gow3_pc, bloodborne_pc,
LibAtrac9 and dependencies retain their existing notices/licenses. Related
upstream work includes #69, #75 and #79; their revision-specific offsets are not
interchangeable with this fork's EU 01.00 profile.

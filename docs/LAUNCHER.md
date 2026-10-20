# Launcher and local achievements

The launcher redesign does not change native game code, FPS patch bytes,
renderer settings by default or the existing experimental timing guards.
30 FPS and an untimed launch remain the defaults. Preparing this change does
not install it into any existing game/test copy.

## Interface

- **Play:** local game/module folders, voice/text language, interface language
  and audio. The header detects a supported title ID and metadata revision.
- **Video:** display mode, VSync, FPS overlay, frame-rate selection, renderer
  budget and existing image filters. The ordinary 60-FPS selector still does
  not activate the full EU timing/native-1440p developer profile.
- **Controls:** existing mouse options and keyboard/controller remapping.
- **Achievements:** local unlock records and notification preferences.
- **Session log:** bounded visible history, retained when changing UI language.
- **About:** fork identity, original authorship, project/source and upstream
  support links, and the retained non-affiliation notice.

Opening the interface, changing tabs or refreshing achievements does not create
progress files or save preferences. Game-language fallback is in-memory until a
user action saves settings. Settings are locked during this launcher's own
preparation/game session, and preparation uses a snapshot of the chosen values.
Closing during preparation prevents a delayed game launch. Quit asks before
stopping only the child process this launcher itself started, then waits for
its reader/local writer; it never searches for or stops other game processes.

The existing shared launcher settings location is unchanged. Use separate
save/user directories for experimental copies and never edit a running copy's
settings, saves or cache to test this UI.

## Existing trophy events first

The game's existing `sceNpTrophyUnlockTrophy` implementation already writes
`Runtime: trophy <id> unlocked` to its output. The launcher observes exact
matching lines from a newly launched child's output; it adds no detours,
gameplay triggers, speed changes or trophy-return-value changes.

- Local recording is enabled by default for future launches through the updated
  GUI or CLI/headless path. **Record new trophy events locally** turns it off.
- A supported title's `eboot.bin` and valid `sce_sys/param.sfo` must be present
  before a recording session is associated with it. Metadata parsing is bounded
  and read-only; it is not a claim of executable-hash compatibility.
- IDs 0–127 are stored separately by supported title ID in
  `user/achievements/CUSA03627.json` or `CUSA03745.json`, within this copy's user
  directory. The timestamp is UTC; the UI displays local time.
- Existing records keep their original timestamps and do not notify again.
  Different game IDs/user directories do not share progress.
- Only new events are observed. No old logs/saves are scanned; existing gameplay
  or PSN achievements cannot be reconstructed just by opening the page.
- Names/icons and a complete locked-trophy catalog are not imported in this
  first pass. The UI deliberately shows trophy IDs, not invented titles or totals.
- The guest trophy API still has its previous behavior. These local observations
  are not an implementation of guest unlock-state queries or PSN synchronization.
  Custom achievement rules remain future work.

Storage is atomic and writer-locked across processes. Invalid/corrupt state is
reported and left unchanged, not silently reset. A bounded background queue keeps
storage and optional desktop notifications off the game's output-draining path.
If a disk is inaccessible or a writer cannot finish promptly, a warning is
reported; do not assume that a failed write was saved. Game output continues.

## Optional Windows notifications

**Windows achievement notifications** is off by default. On Windows it uses the
Shell notification area with a private message-only window, no registry edits,
focus changes, PowerShell helper, account or third-party notification service.
Notifications request quiet-time respect and no sound. Windows decides whether
and how to display them; visibility in fullscreen/Focus Assist is not guaranteed.

The launcher also reports new persisted unlocks in its own UI. A desktop
notification failure cannot undo progress already saved locally. Non-Windows
builds still record/display local progress; the Windows option is disabled.
No real notification is sent by the automated tests.

## Translation contributions

Interface catalogs are UTF-8 JSON in `port/launcher/locales/`. Copy `en_US.json`
to a locale filename such as `sr_RS.json`, set `_language_name` to the language's
own display name, and translate values without changing keys or `{placeholders}`.
Do not put code, credentials or game assets in a catalog.

Valid `xx_YY` / `xxx_YY` catalog filenames are discovered at startup; adding a
language does not require editing UI layout code. Missing translations fall back
to English. English and Portuguese currently have matching complete key sets;
new languages can start with a subset. Tests reject unknown keys or mismatched
format fields. Both package scripts collect the entire catalog directory and
verify the baseline catalogs are present.

## Validation and remaining acceptance

`python tests/run_release_regressions.py` includes asset-free persistence,
notification-backend mocks, catalog and withdrawn Tk widget tests. Linux CI uses
Xvfb; Windows CI uses setup-python's Tk interpreter. All fixture files are tiny
synthetic data in temporary directories, not real game/firmware assets. Package
smoke tests exercise frozen modules/catalogs and a synthetic unlock through the
existing `--script` entry without mapping a UI window or launching a game.

Visual review at desktop DPI settings and live notification/trophy validation
in a user-authorized separate copy remain acceptance steps. Automated widget
checks do not prove visual polish or Windows notification delivery. No running
game needs to be interrupted for these offline tests.

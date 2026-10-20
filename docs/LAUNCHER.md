# Launcher and local achievements

The launcher redesign does not change FPS patch bytes, default renderer
settings or the existing experimental timing guards. A separate opt-in native
trophy backend adds persistence without changing gameplay/clock code.
30 FPS and an untimed launch remain the defaults. Preparing this change does
not install it into any existing game/test copy.

## Interface

- **Play:** local game/module folders, voice/text language, interface language
  and audio. The header detects a supported title ID and metadata revision.
- **Video:** display mode, VSync, FPS overlay, frame-rate selection, renderer
  budget and existing image filters. The ordinary 60-FPS selector still does
  not activate the full EU timing/native-1440p developer profile.
- **Controls:** existing mouse options and keyboard/controller remapping.
- **Achievements:** responsive, scrollable trophy cards, local unlock records,
  owner-supplied metadata and notification preferences.
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

## Trophy grid and owner-supplied metadata

The grid lists trophy IDs from the selected game's `sce_sys/trophy/trophy00.trp`
icons, plus any already observed IDs. TRP parsing is bounded and read-only;
images are never extracted into the repository or included in packages.
Use **Choose decrypted trophy XML folder** to select an owner's `TROP.XML`,
language-specific `TROP_01.XML` / `TROP_17.XML`, or a complete `TROPCONF.XML`.
`Xml/` and sibling `Icons/` layouts are supported. The setting stores only the
folder path. XML must provide validated IDs, grades, hidden flags and names.

Non-hidden trophies show their name, description and available icon. Locked
hidden trophies show a generic question mark: their real name, description,
grade and icon do not reach widget text, tooltips or image decoding. They are
revealed after an observed unlock. If metadata is missing/encrypted, entries
remain question-mark cards even when unlocked; unknown flags are not guessed.
The page clearly distinguishes missing metadata from a confirmed hidden flag.
An invalid catalog is reported, not silently treated as a valid full catalog.

ESFM files are encrypted metadata, not decrypted XML. No keys or game assets
are distributed, downloaded or searched for automatically. This first parser
does not decrypt ESFM. Supplying an extracted-but-still-encrypted folder does
not enable names/hidden flags. Missing/malformed icons use a generic fallback.

## Existing trophy events and persistent state

The game's existing `sceNpTrophyUnlockTrophy` implementation already writes
`Runtime: trophy <id> unlocked` to its output. The launcher observes exact
matching lines from a newly launched child's output; it adds no detours,
custom gameplay triggers or speed changes.

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
- Only new events are observed. No old logs/saves are scanned automatically;
  historical gameplay/PSN achievements are not inferred from story progress.
- Custom challenges and PSN synchronization remain out of scope.

For the experimental **applied 60-FPS** profile with tracking enabled, the new
launcher opts into `TLG_TROPHY_STATE=1`. The native backend defaults off, and
the 30-FPS launch environment explicitly leaves it off. Existing 30-FPS copies
and their API behavior are not changed or installed over. No frame-rate patch,
animation/input clock, climbing/catch hook or renderer code is changed here.

The opt-in backend records timestamps before reporting an unlock, deduplicates
already-unlocked trophies, and returns saved flags/counts through
`sceNpTrophyGetTrophyUnlockState`. Trophy-info data includes saved unlock state
and timestamp; game-info data includes the actual unlocked count. Valid
context/handle ownership and per-user/title isolation are checked. Native
metadata totals/grades and automatic platinum computation are not fabricated:
this is not yet a complete implementation of every console trophy API.

Native records live at `user/achievements/user-<id>/<TITLE_ID>.bin`, not inside
`savedata`. The fixed, bounded little-endian format includes an identity header,
128 timestamps and a corruption checksum; Python and native writers share a
per-file lock and atomic replace. Corrupt files are preserved and errors reported.
Previously observed JSON records migrate explicitly at the next opted-in
launch. The grid merges native records with JSON observations using original
timestamps; a freshly native-persisted event still notifies once through the
launcher rather than being swallowed as an observer duplicate.

Storage is atomic and writer-locked across processes. Invalid/corrupt state is
reported and left unchanged, not silently reset. A bounded background queue keeps
storage and optional desktop notifications off the game's output-draining path.
If a disk is inaccessible or a writer cannot finish promptly, a warning is
reported; do not assume that a failed write was saved. Game output continues.

## Save-copy investigation (no guessed imports)

`python scripts/audit_trophy_save.py <offline-copy-of-memory.dat>` produces a
read-only JSON evidence report. It checks bounded input and lists candidate
named progress fields; it never writes a save, imports unlocks or invents an
unlock time. Private snapshots showed named perpetual progress for deaths,
captures, hints, tail rescues, petting and barrels, but no validated mapping
from those serialized fields to trophy IDs was established. Zero historical
unlocks were recovered/imported in this pass. This is **unknown**, not proof
that the player earned no trophies. Recovery requires further format/condition
validation against controlled independent saves.

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
notification-backend mocks, TRP/XML/PNG limits, hidden-card privacy, save-audit
and withdrawn Tk widget tests. Native trophy/service fixtures run on both OSes;
Windows additionally checks Python/native migration and concurrent writers.
Linux CI uses
Xvfb; Windows CI uses setup-python's Tk interpreter. All fixture files are tiny
synthetic data in temporary directories, not real game/firmware assets. Package
smoke tests exercise frozen modules/catalogs and a synthetic unlock through the
existing `--script` entry without mapping a UI window or launching a game.

Visual review at desktop DPI settings and live notification/trophy validation
in a user-authorized separate copy remain acceptance steps. Automated widget
checks do not prove visual polish or Windows notification delivery. No running
game needs to be interrupted for these offline tests.

Format/ABI references: [shadPS4 TRP layout](https://github.com/shadps4-emu/shadPS4/blob/main/src/core/file_format/trp.h),
[trophy structs](https://github.com/shadps4-emu/shadPS4/blob/main/src/core/libraries/np/np_trophy.h)
and [error codes](https://github.com/shadps4-emu/shadPS4/blob/main/src/core/libraries/np/np_error.h).
Existing author/license notices are retained; no extracted trophy assets are committed.

# Experimental photo mode

This is a **draft, opt-in Windows EU 01.00 / 60-FPS implementation**, not a
claim of gameplay validation. It requires a new process; never attach it to an
existing game. Native gameplay validation is deliberately pending. No game
scripts, binaries, saves or images are included in the PR.

Enable **Experimental photo mode** on the launcher's Video page, select the
supported 60-FPS profile, and use a separate test user/save directory. The
launcher default is false. It strips the feature from 30-FPS/unlocked/Linux
launches. Direct native launches can opt in with `TLG_PHOTO_MODE=1`; the native
loader independently requires the exact supported serial/version, loader
signatures and 60-FPS patch bytes before installing anything. A mismatched game
or modified bootstrap is left unchanged.

## Controls

- F8: request entry/exit. Entry requires an ordinary gameplay camera, a player,
  an in-game scene, no pre-existing pause, and an explicit false from the native
  animated-camera query. The player's scripted/demo flag must be explicitly
  clear, and entry during slow-motion/speed ramps is refused. Unknown states
  are refused, not treated as safe.
- WASD: move; Q/E: down/up; mouse: look; Shift: faster; Z/X: field of view.
- F9: save one 2560x1440 SDR PNG. Requests coalesce rather than queue.
- Escape, opening the port menu, focus loss or minimization: request restoration.
- Controller: L3+R3 requests entry/exit; left stick moves; right stick looks;
  shoulders move vertically; right trigger increases speed; B/Circle exits;
  Y/Triangle captures. The port's overlay is hidden after acknowledged entry.
  Gameplay input is neutral while entry is pending as well, preventing the
  activation chord from reaching the game's own camera/debug controls. An
  unacknowledged entry request is cancelled after one second of render time;
  this never ends the game or imposes a session timer.

After exit, gameplay input remains neutral until held keys/buttons/sticks are
released, so a photo movement key does not unexpectedly move the boy on resume.

Photos go into `user/photos`, with exclusive, timestamped names and Unicode path
support. An output that is not exactly 2560x1440 SDR RGBA8/BGRA8 is rejected, not
resized and advertised as native. Upscaling, if separately configured by the
player, is not undone. PNG output captures the game's completed image before
the port overlay, not the desktop; game-owned subtitles/UI remain in that image.
There is one additional 14.1-MiB readback allocation and a one-shot completion /
PNG-encoding wait only when a capture is requested. No perpetual readbacks.
An unavailable readback allocation refuses the capture instead of terminating
the game.

## Safety and boundaries

The original port Lua backend is appended in memory to one size/SHA256-verified
bootstrap. It runs camera operations on the engine's Lua thread. The host UI
communicates through two bounded virtual descriptors; there are no command
files and no writes to game archives, clocks, characters, AI or saves.

Freeze/resume uses the existing `trico pause` / `trico resume` commands, never a
zero game speed, suspended OS threads or blocked Vulkan submissions. Only a
pause acquired by photo mode is released. Camera movement uses unscaled render
time (with an editor-timestep fallback), never paused simulation time. Mouse
look does not depend on either timestep. The default camera is temporarily put
in FPS mode rather than retaining an orbit/Maya pivot, and its transform, FOV
and mode are restored on exit. A
cutscene/scene change cancels the mode; it does not overwrite a camera installed
by a cutscene. Missing services or Lua errors refuse entry / attempt restoration.
The original gameplay camera transform is not edited.

The first local native test exposed repeated `no mount for guest path
/tlg-photo/control` messages: retail stdio probes metadata/reachability before
opening the mailbox. The descriptor-only fixture had not exercised this path.
The virtual namespace now handles stat/access/reachability and bounded snapshot
seek/pread in memory as well as open/read/write/close. Metadata does not consume
mouse deltas. Disabled photo paths fail without touching a host mount or file.
The corrected build still needs a fresh native entry/movement/exit/capture test;
passing these regressions is not a claim that the in-game lock is resolved.

The existing 60-FPS timing transforms stay independently gated; enabling photo
mode alone does not implicitly turn them on. When photo mode is off there is no
photo Lua insertion, pause command, camera change or image allocation. The
30-FPS native image and original clock logic are untouched.

## Tests and required manual validation

- `python tests/test_photo_mode.py --lua-required` (test-only `lupa==2.8`) runs
  the real original backend against a Lua 5.1 engine double: off/default paths,
  pre-existing pauses, cutscenes/unknown states, scene changes, error restoration,
  independent movement rates, FOV bounds and launcher guards.
- `photo-runtime-test` exercises acknowledgement ordering, stale replies,
  finite/clamped input, cancellation and coalesced captures.
- `photo-mailbox-test` exercises the actual guest file-descriptor path, split
  reads/writes, retail path preflight, access modes, seek/pread, bounded messages
  and opt-out, without any host files.
- `photo-controls-test` drives real SDL event handlers with synthetic events,
  without initializing SDL, opening a window or reading any controller. It
  checks pending chord shielding, Escape cancellation, look/capture dispatch,
  dialog/focus cancellation and opt-out.
- `photo-png-test TEMP_DIRECTORY` encodes and independently decodes a synthetic
  2560x1440 image, verifies exact pixels, Unicode paths and refusal to overwrite.
- Existing release regressions must pass on Windows and Linux.

Before removing draft status, test a newly launched isolated copy for: native
Lua I/O availability; callback execution while paused; correct camera transform
units and cutscene exclusion; restoration after repeated entry/exit, Alt-Tab,
menus and scene changes; synchronized RGBA/BGRA GPU readback without validation
errors; and opening a real captured 2560x1440 PNG. Also replay the known tail
catch after exiting, and compare a separate 30-FPS control. Do not use or modify
a user's existing session for these tests. The mock tests do not establish that
all retail engine/editor services are available, or replace this validation.

# Experimental device prompts and controller guide

This is a display-only feature. **Original (off) remains the default**, including
at 30 FPS. It does not change gameplay input, the game clock, climbing, physics,
catch timing, saves, shader caches or game archives. An already-running game
does not receive launcher setting changes.

## Selection

In the launcher's **Controls → Button prompts**, choose:

- **Original (off):** retain the game's own images.
- **Automatic:** use the last deliberately used device. PlayStation controllers
  identified by SDL use the PS5 set; other gamepads use Xbox labels. No controller
  starts with keyboard/mouse prompts. Removal of the selected controller returns
  to keyboard/mouse; removal of another controller does not switch.
- **Keyboard and mouse**, **PS5 / DualSense**, or **Xbox:** fixed visual overrides.

The same selector is in the in-game settings menu, opened with Insert or R3+L2.
The manual choice does not change controller bindings. Auto observes events
without consuming or synthesizing gameplay input. Stick drift, key repeats,
releases, unfocused input and small/uncaptured mouse motion do not switch it.
Cross-device chatter has a 150-ms monotonic-time guard, independent of game FPS.

Native configuration: `button_prompts=original|auto|keyboard|ps5|xbox` in `tlg.ini`.
`TLG_BUTTON_PROMPTS` overrides it at process startup. Invalid values mean off.

## What is replaced

The initial implementation recognizes three exact, locally verified EU 01.00
BC7 payloads: the tutorial controller diagram, tutorial highlight atlas, and
Options controller-guide image. Shape, format, mip/layer restrictions, size and
128-bit payload hashes must match. Other textures remain untouched. Host copies
are generated and uploaded using the existing Vulkan transfer path; guest
texture bytes and archive contents are never changed.

**This is not a complete replacement of every in-game button symbol.** Some TLG
menu symbols are geometry rather than texture artwork. They stay original.
Unknown revisions/content fail closed. Shared stick/push and ambiguous highlight
cells retain neutral rings instead of displaying a potentially wrong key.

Keyboard legends come from the effective runtime key map, including overrides,
rather than parsing a second competing mapping. One representative binding is
shown (mouse preferred when an action has both). Unknown/long key names display
`?`; unbound actions display `---`. Nonstandard controller button remaps fall
back to original controller diagrams rather than mislabeling fixed positions.
This fallback also applies to a manually selected controller set.

Switching off restores the original host texture on its next use. Enabling the
feature also discovers candidate textures already loaded while it was off.
Render/storage resources modified by the GPU are not overwritten because of a
prompt-selection change. Host-generated images are cached; the first use of a
new large guide/set can incur a one-time drawing/encoding cost.

## Optional local PS5 image and high-resolution overlays

The public code contains only independently drawn primitives and a tiny
code-defined keycap alphabet. It does **not** contain an extracted game atlas,
controller screenshot, logo, trophy image or third-party controller drawing.

To use your own controller drawing, select **Local PS5 layout PNG…** in the
launcher. Use a controller-only white-on-black PNG, without another game's
action labels. It is read from its local path, not copied into a release or
uploaded. `TLG_PS5_PROMPT_IMAGE` is an explicit startup override. For private
source-tree testing only, `port/user/prompt-art/ps5-controller.png` is detected
when no file was selected; that whole user directory is ignored by Git and
excluded from packaging. No local file is enabled while the prompt set is off.

The source remains at its full resolution, bounded to 4096×4096 and 64 MiB
encoded. A small area-filtered monochrome copy serves the native tutorial. The
large guide is drawn separately at **swapchain/display resolution**, after the
game's image filters; it is not an enlarged 256×128 thumbnail.

After starting that test copy with Auto or PS5 enabled, open **Insert → Controls
→ Large PS5 controller guide**. Callout lines, button markers and current
keyboard/mouse legends surround the supplied image. Known actions use the
existing port's Jump/Grab/Call Trico labels; unknown actions keep button names.
The supplied controller-only crop has no unrelated action labels to carry over.
Markers are reference callouts, not a live button-state visualizer.

The resizable window defaults to 90% of display width and 88% of height. Image
aspect ratio is preserved and labels scale with the available canvas. For the
private 1599×984 crop, a typical 2560×1440 guide uses roughly 1200 display pixels
of image width, below source resolution. A larger image does not create detail
beyond its source resolution. Layout bounds are tested at 720p through 2160p;
actual in-game readability and highlight calibration remain playtest gates.

The guide is only displayed while the settings menu is open. It does not install
a background observer or add a permanent gameplay HUD. The settings menu holds
input neutral; it does not promise to pause the simulation, so open it safely.

## Validation and remaining gates

`python port/tests/run_release_regressions.py` runs synthetic selection,
manual/auto switching, disconnection, cache generation, exact-match rejection,
BC7 roundtrip, settings, withdrawn launcher and package-exclusion checks without
launching a game. Windows also exercises the real PNG decoder with an existing
synthetic 2×2 fixture and verifies effective remap metadata. Local tests can
optionally read the owner's crop/ELF; those files are never fixtures or uploads.

Before marking the PR ready: clean Windows/Linux package builds, native guide
visual alignment at 1080p/1440p, PS5/Xbox hotplug and drift checks, remapped keys,
off/on/original restoration, and a campaign coverage audit. These changes have
not been injected into or tested by interrupting the user's running session.

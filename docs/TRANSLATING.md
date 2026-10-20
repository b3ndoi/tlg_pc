# Translation contributions

## What is translated today

| Surface | Serbian Latin (`sr_Latn_RS`) | How it works |
| --- | --- | --- |
| Launcher | All 147 current interface keys | UTF-8 JSON, English fallback |
| Common gameplay tutorials | 72 of 72 entries in the initial profile | Optional host-only texture replacements |
| Story subtitles, game menus, host Insert menu, voices, trophy metadata | Not translated | Original text/audio retained |

This is an initial, unreviewed fan translation, **not a fully translated game**.
The local EU 01.00 English archive contains 479 subtitle textures; this first
profile covers the 72 common tutorial textures, not the other 407. Some artwork
is identical, so the compiler produces 66 unique replacements. Other revisions
and regions have not been validated. Unmatched artwork is always kept original.

The game stores these strings as BC7 images. A launcher locale or an invented
`TLG_LANGUAGE` number cannot translate them. We commit new fan-written text and
texture geometry/fingerprints, **never extracted game pixels, archives, scripts,
dialogue dumps, saves, trophy assets or keys**. Original licenses, copyright and
credits remain intact; this is an unofficial community contribution.

## Try the tutorial translation without changing a running game

Prepare a **separate test copy**, with its own output/user directory and a physical
copy of your save. Do not compile into an active game directory, edit original
archives, share writable saves, or change a running session's environment/settings.
The compiler refuses to overwrite an existing output file.

From `port/` in the source tree (or the root of an extracted package):

```powershell
python -m venv .venv-translation
.venv-translation\Scripts\python -m pip install -r requirements-translation.txt
.venv-translation\Scripts\python scripts/compile_translation.py --catalog translations/sr_Latn_RS.json --check
.venv-translation\Scripts\python scripts/compile_translation.py --catalog translations/sr_Latn_RS.json --output C:/private-tests/sr-tutorials.tlgtrn --preview C:/private-tests/translation-preview
```

Create the private parent folder first. Linux uses
`.venv-translation/bin/python` with the same arguments. Previews must be a new
directory. Pillow is a contributor-tool dependency, not a game/runtime dependency.
The existing, openly licensed DejaVu Sans font is used and its license is packaged.

In the **separate copy's** launcher, choose **English** for game language,
**Srpski (latinica)** for interface language if desired, and select the new pack
under **Local tutorial translation pack**. The pack selector does not alter voice
language, FPS, controls, frame-rate fixes or timeout. Choose the desired test
profile independently. The native equivalent is the next child's environment:

```powershell
$env:TLG_TRANSLATION_PACK = 'C:/private-tests/sr-tutorials.tlgtrn'
```

Do not set this globally. Keep `TLG_LANGUAGE=1` for the English base. At startup
the log reports the loaded replacement count. A missing/invalid pack reports
fallback and keeps original text; successful loading alone does not prove that
a specific tutorial matched. Clear the selector (and any explicitly set environment
variable) to return to original text on the next start.

There are no game-memory patches, subtitle/BOD/Lua changes, timing hooks, input
changes, save edits or archive writes. Texture matching uses the original 128-bit
fingerprint, byte count, format, tiling, geometry, levels and layers; GPU-modified
resources are excluded. Replacements are uploaded only to the host texture, and
the pack is immutable for the session. Default/off behavior is unchanged at
30 and 60 FPS. Translating at 30 FPS changes only the opted-in text artwork.

## Make a translation PR

1. Fork `b3ndoi/tlg_pc`, update your `main`, then make a focused branch:

   ```sh
   git switch main
   git pull --ff-only
   git switch -c translate/your-locale
   ```

2. Pick a stable identifier: `de_DE`, `sr_Latn_RS`, `sr_Cyrl_RS`, etc. Use
   `language[_Script]_REGION`. Keep Latin and Cyrillic in distinct catalogs.
3. For the launcher, copy `port/launcher/locales/en_US.json` to your locale filename.
   Translate values, including `_language_name`, not keys. Missing keys fall back
   to English. Preserve **all Python format fields** (`{count}`, `{title}`, `{id}`,
   `{error}`, etc.), spelling/case included. Do not translate SDL key names in
   examples, executable names, file extensions, URLs or product/author credits.
4. For in-game tutorials, copy `port/translations/sr_Latn_RS.json` to your locale
   filename, change `locale` and `name`, then replace the Serbian text. Use the
   IDs and your own legally obtained game for context. Empty values or omitted
   entries intentionally retain original English. Keep `schema` and `profile`.
   Do not edit `targets.json` in a translation-only PR.
5. Save files as **UTF-8 without BOM**, with actual Unicode characters, NFC
   normalization, and LF line endings. Serbian Latin must retain `č ć ž š đ`
   and `Č Ć Ž Š Đ`; do not replace letters with ASCII approximations. JSON `\n`
   means a real line break. Keep the original line count. The validator rejects
   duplicate keys, invalid UTF-8, lone surrogates, unsupported controls, unknown
   IDs/tokens and decomposed text. Controller tokens `{circle}`, `{cross}`,
   `{triangle}`, `{r1}` must remain exactly as specified; their order may change
   to suit grammar. They currently render as open-font PS-style symbols, not
   auto-switching keyboard/Xbox labels.
6. Keep text concise. The compiler checks the font for missing glyphs and fits
   text without cropping (minimum 16 px). Review **every generated preview** for
   legibility, punctuation and consistent terminology. Do not shorten by deleting
   safety-relevant instructions. Right-to-left text and complex shaping need a
   separately reviewed renderer/font profile; this first pack is tested for
   Latin-script text only. UTF-8 support is not a claim of complete script support.
7. Run the checks below. Privately test representative tutorials in a separate
   game copy at 30 and 60 FPS. Check diacritics, accents, hold/press distinctions,
   line wrapping, fade/placement, original-text fallback and controller symbols.
   Do not claim in-game testing if only CPU/render fixtures were run.
8. Stage only the text files and relevant documentation, inspect the diff, and push:

   ```sh
   git diff --check
   git add port/launcher/locales/your_LOCALE.json port/translations/your_LOCALE.json
   git diff --cached --stat
   git diff --cached
   git commit -m "i18n: add your language translations"
   git push -u origin translate/your-locale
   ```

9. Open a PR against **`b3ndoi/tlg_pc:main`** and copy the checklist from
   `.github/PULL_REQUEST_TEMPLATE/translation.md` into its description.
   State language/script, coverage, terminology choices, tests actually run, game
   region/revision and remaining untranslated surfaces. Ask a native speaker to
   review. Keep UI/engine changes separate from translation-only contributions.
   Do not include generated `.tlgtrn`, preview PNGs, game files, trophy icons,
   firmware, logs with private paths, or save data. If visual evidence is needed,
   share only a text-only generated preview privately; no extracted assets in Git
   or release artifacts. The project's asset guard also rejects compiled packs.

## Checks

From `port/` (commands below use the Python from your virtual environment):

```sh
python scripts/compile_translation.py --catalog translations/your_LOCALE.json --check
python tests/test_launcher_localization.py
python tests/test_translations.py
python tests/run_release_regressions.py
```

The full regression runner needs the project's C/C++ build toolchain; GUI fixtures
are withdrawn and use synthetic files, never the real game. Linux uses `xvfb-run`
for Tk checks. CI installs Pillow and runs independent BC7 decode/render tests,
Unicode-path tests, malformed-pack/fingerprint fixtures, and original 30-FPS
environment checks. Both package scripts include catalogs/font credits and verify
the Serbian launcher catalog is present in the frozen app.

## Expanding beyond tutorials

Story and menu translations are **not** enabled by adding arbitrary IDs here.
An engine/profile PR must first identify the exact source textures, dimensions,
line counts, device glyphs, locale selection and draw/material behavior offline.
Do not translate by guessing from filenames or changing subtitle timing to fit.
Review the font/shaping and texture-cache safety rules, add synthetic fixtures,
then accept community translations against those stable IDs. No original game
text/artwork should be uploaded as a source template. Keep voice tracks untouched
unless a separately licensed, explicitly supported project is proposed.

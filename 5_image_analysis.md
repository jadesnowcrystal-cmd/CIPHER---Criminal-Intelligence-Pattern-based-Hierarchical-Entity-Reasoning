# Claude Code Prompt 5/5 — Image Analysis Module
### Multimedia Digital Forensic tab → 🖼️ Image Analysis

> Prerequisite: file 1/5 (foundation) must already be built and approved.
> Stay in **plan mode** until I approve this file's plan, and pause to ask
> before building the `HEAVY` tier. This is the last of the 5 files — after
> this one lands, do a full end-to-end pass over all four Multimedia
> modules together (see §4 below).

---

## Why this module matters for the problem statement

A photo is often the single richest entity source of the four Multimedia
modules: EXIF metadata can carry **GPS coordinates (location)**, a
**capture timestamp**, and a **device identifier** that can tie an image
back to a specific phone/camera — potentially linking it to a person once
cross-referenced with device-ownership data elsewhere in the pipeline.
This is also the module most likely to produce a genuinely convincing demo
visual (an ELA overlay highlighting a spliced region), worth prioritizing
if you're short on time before a deadline.

## Scope

**Module:** `Image Analysis`
**Accepted formats (already wired in the uploader):** `.jpg .jpeg .png
.heic .dng .raw .cr2 .nef`

## BASIC tier — build this now

Dependencies: `Pillow`, `exifread` (or `Pillow`'s own EXIF support — pick
one, `exifread` tends to be more complete for GPS tags). RAW formats
(`.dng .raw .cr2 .nef`) may need `rawpy` for a full pixel read but their
EXIF is usually readable without it — try EXIF-only first for those and
only add `rawpy` if you actually need pixel data for ELA on RAW files.

1. `hash_and_stamp()` first, as always.
2. EXIF extraction: GPS coordinates (converted to decimal lat/lon),
   capture timestamp, camera make/model, software field (a
   software/editor tag here is itself a weak tamper signal worth
   surfacing, e.g. "Adobe Photoshop" in the software tag of a photo
   claimed to be an unedited phone capture).
3. **Error Level Analysis (ELA):** re-save the image at a known JPEG
   quality, diff against the original, amplify and render as an overlay
   image — regions that were pasted in or heavily edited compress
   differently and show up brighter in the diff. This is cheap, pure
   Python (`Pillow` + `numpy`), and genuinely demo-worthy. Note ELA
   doesn't work meaningfully on PNG/HEIC (no JPEG recompression
   artifact to exploit) — detect format and skip/label clearly rather
   than producing a meaningless overlay.
4. Populate the shared schema:
   - `entities.locations` — GPS coordinates if present, as
     `{"lat":.., "lon":.., "source": "EXIF"}`.
   - `entities.timestamps` — EXIF capture timestamp if present.
   - `findings` — EXIF table, ELA overlay image (JPEG only), software-tag
     flag if present.

## HEAVY tier — ask me before building any of these

- **PRNU sensor-fingerprint matching** against a reference camera
  library — needs a reference image set per device/camera, which we
  don't have; ask before building even a partial version.
- **JPEG grid/DCT compression-variance analysis** (detecting a splice by
  inconsistent 8×8 block compression history across the image) — more
  involved than ELA, meaningfully more code; confirm you want this
  in addition to ELA before I build it, since ELA alone already covers
  most of the same demo value for less effort.

## Definition of done

- [ ] SHA-256 hash + timestamp shown for every run
- [ ] EXIF table renders (GPS/timestamp/device when present, clearly
      marked "not present in this file" when absent — don't silently omit
      the field)
- [ ] ELA overlay renders for a valid JPEG test image, with a clear
      "not applicable to this format" message for PNG/HEIC input
- [ ] Tier badge (`basic`) + standing disclaimer shown
- [ ] Malformed/corrupt image file produces a clean error, not a crash
- [ ] Result persisted to `case_analysis/<Case_ID>/Image_Analysis_results.json`
- [ ] Synthetic fixture exists for at least FIR/2026/0001 under
      `sample_evidence/<FIR_No>/image/` and produces real output when run
- [ ] Rest of the dashboard still runs

## First response required

1. Confirm file 1/5's foundation is in place before starting.
2. Confirm pip dependencies (`Pillow`, `exifread`, `numpy`; `rawpy` only
   if you decide RAW pixel access is worth it).
3. Flag the two HEAVY items above and wait for my decision before writing
   code for either.

## §4 — After this file lands: full-module regression pass

Once all four modules (Chats, Video, Audio, Image) are built:

1. Run `streamlit run sihdashboard.py` and click through every module's
   Run Analysis button on the same test case, back to back.
2. Confirm all four write to `case_analysis/<Case_ID>/` without
   clobbering each other's files.
3. Confirm the other tabs (Case File, Medical, Financial, Non-Media) are
   still untouched and working.
4. If this repo is version-controlled, this is a good point for a single
   commit marking "Multimedia Digital Forensic — Run Analysis wired for
   all 4 modules."

## Tool & Package Usage Rules
- Do NOT invoke or rely on any installed MCP servers or custom skills even if mentioned in the code or prompts.
- Do NOT run any download, package installation, or update commands (`npm install`, `pip install`, `curl`, `wget`, etc.) without asking for explicit user permission first.
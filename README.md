# Oh Fudge, My Battery Chat!

A self-contained Windows app that shows SteamVR device battery levels (headset,
controllers, trackers, base stations - anything SteamVR reports a battery for)
as an OBS Browser Source overlay. Named after every streamer's least favorite
moment: "Ohh fudge, my battery is low, why didn't you remind me chat?!" Built
for a Quest Pro connected through SteamVR (Oculus Link / Air Link / Virtual
Desktop's SteamVR bridge), but works with any SteamVR-tracked device.

## How it works

- `OhFudgeMyBatteryChat.exe` opens a small **configurator GUI**. It reads
  live battery data from SteamVR (via the OpenVR API) and runs a local web
  server in the background.
- That server serves an overlay page at `http://127.0.0.1:8710/overlay`
  (port shown in the GUI) - add that URL as a **Browser Source** in OBS.
- The **Add** button in "Overlay Items" is a choice of two things to add:
  - **Add Device** - a battery readout bound to one SteamVR device: pick
    the device, a normal picture, a low-battery picture, a warning sound, a
    low-battery threshold, whether it's always visible (just swaps art when
    low) or hidden until it pops in when low, and where it sits on screen.
  - **Add Overlay Effect** - a standalone alert you can layer on top of
    anything: a picture, an optional sound, and an optional styled caption
    (text above/below/over the picture, with font, size, color, a wobble/
    shake/pulse animation, and an outline), triggered by **Battery Low**,
    **Battery Normal**, **Device Disconnected**, or **Device Connected**.
    Target a **Specific Device**, **Any Device**, or **All Devices** (with
    an optional **Ignore Device** to exclude one from Any/All matching, e.g.
    a spare controller that's always low). Add as many as you want.
- Both kinds support **Appear/Disappear pop animations** (fade, slide, pop
  from a direction, fade + shake) with a **Test Animation** button that loops
  the animation live on the real overlay page while the dialog is open.
- Dragging either kind on the position canvas **snaps to align** with any
  other Device or Effect already placed (edges/centers, on either axis), with
  a yellow guide line while snapped - handy for lining several up in a row.
- Pictures can be static images, animated GIFs, or `.webm` video (rendered
  muted/looping, like a sticker). Sounds can be `.wav`/`.mp3`/`.ogg`.
- If you don't pick your own art, generic placeholder icons (plain
  geometric shapes, not Valve/Meta artwork - see Licensing below) and a
  synthesized alert beep are used automatically.
- The top bar has a **Language** picker (English, Deutsch, Français,
  Español, 日本語, and a just-for-fun tlhIngan Hol/Klingon) and an **About**
  box with version, author, and a GitHub link placeholder - edit
  `APP_VERSION`/`APP_AUTHOR`/`APP_GITHUB_URL` near the top of `app/gui.py`
  to fill those in with your own details.

## Using it

1. Launch SteamVR (with your headset connected) and `OhFudgeMyBatteryChat.exe`.
2. The left panel lists currently-connected SteamVR devices with live battery %.
3. Click **Add** and choose **Add Device** or **Add Overlay Effect**, fill in
   the dialog, and drag it into position on the mini preview canvas (it
   snaps to align with anything else you've already placed).
4. Copy the URL shown at the top (default `http://127.0.0.1:8710/overlay`)
   into OBS: **Sources > + > Browser Source**, paste the URL, set size to
   1920x1080 (or your canvas size - positions are percentage-based so other
   resolutions scale fine).
5. Leave "Shutdown source when not visible" **unchecked** in OBS if you want
   low-battery alerts to keep working while that scene isn't active.
6. If a warning sound doesn't play in OBS, check the Browser Source's
   "Control audio via OBS" option - some OBS versions gate autoplay audio
   behind that setting.

Your configuration (devices, effects, art, sounds, layout) is saved to a
**`Data` folder next to the .exe** (not buried in %APPDATA%), so it's easy to
find, back up, or hand to a friend along with the .exe. Custom media you pick
gets copied into `Data\assets\`. If the exe's folder turns out to be
read-only (e.g. running from Program Files), it falls back to
`%APPDATA%\OhFudgeMyBatteryChat\` automatically.

## Sharing with friends

Just send them the `.exe` - it's fully self-contained (bundles Python, the
OpenVR API, and Pillow). They don't need Python, pip, or any of this
installed. They do need **SteamVR** installed and running with their headset
connected through it. If you also want to hand them your saved setup, copy
the `Data` folder alongside the exe too.

## Rebuilding the .exe after making changes

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "OhFudgeMyBatteryChat" --collect-all openvr --add-data "app/fonts;fonts" main.py
```

The output lands in `dist\OhFudgeMyBatteryChat.exe`.

## Running from source (for development)

```bash
pip install -r requirements.txt
python main.py
```

## Notes / limitations

- Battery data only appears while SteamVR is running and the device is
  actively tracked through it. If your Quest Pro is only in native
  Oculus/Meta mode (no SteamVR bridge), this app won't see it.
- Some devices (notably some base stations) don't report a battery -
  they'll show "n/a" and Battery Low/Normal effects won't fire for them.
- Devices are matched by their SteamVR serial number, so a saved Device
  item or Effect keeps pointing at "your right controller" even if SteamVR
  renumbers device indices between sessions.
- This hasn't been tested against a real SteamVR/headset in this build
  session (no hardware available here) - the overlay rendering, trigger
  logic, animations, and packaging were verified end-to-end with simulated
  device data. Please try it with your actual Quest Pro/SteamVR setup and
  let me know if anything looks off.
- **Any/All Device** effects (and any effect watching for a disconnect)
  need the app to have seen a device at least once this session before it
  can notice it disconnecting - that "seen" list resets each time you
  restart the app, so give SteamVR a moment to report your devices after
  launch before relying on a disconnect alert.
- The Klingon (tlhIngan Hol) translation is a fun best-effort using real
  vocabulary where it exists and reasonable invented compounds for modern
  terms Klingon has no canonical word for (there's no certified translation
  for "dropdown menu") - treat it as an easter egg, not an authoritative
  translation. When Klingon is selected, buttons/labels/frame titles/menu
  items render in the real pIqaD script (bundled font: "pIqaD qolqoS" by
  Daniel Dadap, SIL Open Font License - see `app/fonts/LICENSE-pIqaD-qolqoS.txt`),
  loaded privately for this process only (no system-wide font install).
  Comboboxes, text fields, device serial numbers, and native error popups
  stay in Latin-letter Klingon - that font has no Latin glyphs at all, so
  anything that mixes in real device data intentionally isn't switched over.

## Licensing note on bundled art/sound

The default icons are plain shapes drawn with Pillow at first run (not
Valve/Meta/Meta Quest artwork), and the default alert sound is a
synthesized beep - both safe to bundle and share. Swap in your own pictures
and sounds any time from the GUI.

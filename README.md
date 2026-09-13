<div align="center">

# Oh Fudge, My Battery Chat!

[![Version](https://img.shields.io/badge/version-v1.0-blue)](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/v1.0)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6)](#)
[![Requires](https://img.shields.io/badge/requires-SteamVR-orange)](#)
[![Languages](https://img.shields.io/badge/languages-6-brightgreen)](#language-support)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)
[![Made with Claude](https://img.shields.io/badge/made%20with-Claude-8A63D2)](https://claude.com)

*A self-contained Windows overlay that finally answers "why didn't you remind me chat?!"*

</div>

---

> **Made with Claude.** This entire app - every feature below, the OpenVR
> integration, the six-language UI, even the real Klingon pIqaD script
> rendering - was built collaboratively with [Claude](https://claude.com)
> (Anthropic) through conversational pair-programming, including the live
> hardware debugging that tracked down a real SteamVR tracker driver quirk.

A self-contained Windows app that shows SteamVR device battery levels (headset,
controllers, trackers, base stations - anything SteamVR reports a battery for)
as an OBS Browser Source overlay. Named after every streamer's least favorite
moment: "Ohh fudge, my battery is low, why didn't you remind me chat?!" Built
for a Quest Pro connected through SteamVR (Oculus Link / Air Link / Virtual
Desktop's SteamVR bridge), but works with any SteamVR-tracked device.

## Contents

- [How it works](#how-it-works)
- [Using it](#using-it)
- [Sharing with friends](#sharing-with-friends)
- [Language support](#language-support)
- [Building from source](#building-from-source)
- [Notes / limitations](#notes--limitations)
- [Licensing](#licensing)

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
    Target a **Specific Device** or **All Devices** (with a multi-select
    **Ignore Devices** list to exclude any number of them, e.g. a spare
    controller that's always low, or base stations that never have one).
    Add as many as you want.
- Both kinds support **Appear/Disappear pop animations** (fade, slide, pop
  from a direction, fade + shake) with a **Test Animation** button that loops
  the animation live on the real overlay page while the dialog is open.
- Dragging either kind on the position canvas **snaps to align** with any
  other Device or Effect already placed (edges/centers, on either axis), with
  a yellow guide line while snapped - handy for lining several up in a row.
- Pictures can be static images, animated GIFs, or `.webm` video (rendered
  muted/looping, like a sticker). Sounds can be `.wav`/`.mp3`/`.ogg`.
- If you don't pick your own art, generic placeholder icons (plain
  geometric shapes, not Valve/Meta artwork - see [Licensing](#licensing))
  and a synthesized alert beep are used automatically.
- Base stations always show **"No battery"** instead of a bare "n/a" -
  they're mains/USB-powered, so that's expected, not a bug.
- Every device shows its **brand** (HTC, Valve, Tundra Labs, Meta, etc.)
  alongside its model - and yes, "Oculus" is shown as "Meta," because Oculus
  became Meta in 2021 and SteamVR still reports the old name.
- A one-time notice explains that some devices (looking at you, certain
  trackers) only report battery in bursts and may show nothing until they've
  been power-cycled or run low - not a bug in this app either.

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

Grab the exe from [the latest release](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/latest)
or build it yourself (below) - it's fully self-contained (bundles Python, the
OpenVR API, and Pillow). Your friends don't need Python, pip, or any of this
installed. They do need **SteamVR** installed and running with their headset
connected through it. If you also want to hand them your saved setup, copy
the `Data` folder alongside the exe too.

## Language support

The whole UI (buttons, labels, dialogs, menus) switches between six
languages from the top bar: English, Deutsch, Français, Español, 日本語, and
tlhIngan Hol (Klingon). Klingon renders in the real pIqaD script using a
bundled open-licensed font (see [Licensing](#licensing)) - comboboxes, text
fields, and device serial numbers stay in Latin-letter Klingon, since that
font has no Latin glyphs and would show blank boxes for anything mixed with
real device data.

## Building from source

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "OhFudgeMyBatteryChat" --collect-all openvr --add-data "app/fonts;fonts" main.py
```

The output lands in `dist\OhFudgeMyBatteryChat.exe`. The in-app About box's
version/author/GitHub link come from constants near the top of `app/gui.py`
(`APP_VERSION`, `APP_AUTHOR`, `APP_GITHUB_URL`) - update those before
rebuilding if they drift from reality.

To run it straight from source instead of building an exe:

```bash
pip install -r requirements.txt
python main.py
```

## Notes / limitations

- Battery data only appears while SteamVR is running and the device is
  actively tracked through it. If your Quest Pro is only in native
  Oculus/Meta mode (no SteamVR bridge), this app won't see it.
- Some devices don't report a battery at all (SteamVR itself has nothing to
  give) - base stations are the expected case, but a handful of third-party
  trackers have also been observed not reporting until power-cycled or low.
- Devices are matched by their SteamVR serial number, so a saved Device
  item or Effect keeps pointing at "your right controller" even if SteamVR
  renumbers device indices between sessions.
- **All Devices** effects (and any effect watching for a disconnect) need
  the app to have seen a device at least once this session before it can
  notice it disconnecting - that "seen" list resets each time you restart
  the app, so give SteamVR a moment to report your devices after launch
  before relying on a disconnect alert.
- Verified on real hardware: Meta Quest Pro, Valve Index (Knuckles)
  controllers, HTC Vive Tracker 3.0, Tundra Tracker, and Valve base
  stations - across a real streaming setup, not just simulated data.
- The Klingon (tlhIngan Hol) translation is a fun best-effort using real
  vocabulary where it exists and reasonable invented compounds for modern
  terms Klingon has no canonical word for (there's no certified translation
  for "dropdown menu") - treat it as an easter egg, not an authoritative
  translation.

## Licensing

The code in this repository is [MIT licensed](LICENSE).

The default icons are plain shapes drawn with Pillow at first run (not
Valve/Meta/Meta Quest artwork), and the default alert sound is a synthesized
beep - both original and safe to bundle and share. Swap in your own pictures
and sounds any time from the GUI.

The bundled Klingon font, `app/fonts/pIqaD-qolqoS.ttf` ("pIqaD qolqoS" by
Daniel Dadap), is licensed separately under the
[SIL Open Font License 1.1](app/fonts/LICENSE-pIqaD-qolqoS.txt), not MIT.

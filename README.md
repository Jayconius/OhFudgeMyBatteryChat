<div align="center">

# Oh Fudge, My Battery Chat!

[![Version](https://img.shields.io/badge/version-v1.1.0-blue)](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/v1.1.0)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6)](#)
[![Requires](https://img.shields.io/badge/requires-SteamVR-orange)](#)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

*A SteamVR battery overlay for OBS - so chat can finally remind you.*

🌐 **English** | [Deutsch](README.de.md) | [Français](README.fr.md) | [Español](README.es.md) | [日本語](README.ja.md)

![Screenshot](docs/screenshot.png)

</div>

Shows your headset, controllers, and trackers' battery live on stream, with
pop-in alerts when something's running low - as a normal OBS Browser Source.

> [!TIP]
> **Not streaming?** You don't need OBS at all - click **Open in Browser**
> in the app and use it as a standalone personal low-battery alarm.

## Quick start

1. Grab the exe from [Releases](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/latest)
   and run it with **SteamVR** already open.
2. Click **Add** to add a device readout or a low-battery alert, then drag
   it into place.
3. Copy the URL shown at the top into OBS as a **Browser Source** (size
   1920x1080).

That's it - no Python or extra installs needed, the exe is self-contained.

## How-to guides

> [!NOTE]
> **Some devices only report battery in chunks, not continuously.** A
> handful of trackers in particular may show **"n/a"** until they've been
> power-cycled, or until the battery actually gets low. That's the
> device's own driver, not a bug in this app - see it show real data for
> anything else, and it'll show real data for that device too the moment
> its driver decides to report it.

<details>
<summary><strong>Adding the OBS Browser Source</strong></summary>

1. In OBS: **Sources > + > Browser Source**, give it a name, click OK.
2. Paste in the URL shown at the top of the app (default
   `http://127.0.0.1:8710/overlay`).
3. Set **Width** to `1920` and **Height** to `1080`. Item *positions* scale
   to any canvas size fine, but item *sizes* are calibrated against this
   1920x1080 reference in the position editor - match it so things look
   the same size as you previewed them, not bigger or smaller.
4. Leave **"Shutdown source when not visible"** unchecked if you want
   low-battery alerts to keep working while that scene isn't on screen.
5. If a warning sound doesn't play, check this source's **"Control audio
   via OBS"** option - some OBS versions gate autoplay audio behind it.

</details>

<details>
<summary><strong>Adding a Device (a live battery readout)</strong></summary>

1. Click **Add > Add Device**.
2. Pick the device from the list on the left (click **Refresh** if it's not
   showing yet).
3. Give it a label and a low-battery threshold (%).
4. Choose **Always visible** (icon stays put, just swaps picture when low)
   or **Hidden until low** (pops in only once it's low).
5. **Pictures & Sound**: pick a normal picture and a low-battery picture,
   and a warning sound - or skip any of these to use the built-in defaults.
   Clicking **Choose...** opens straight to `Data\assets\device icons`, a
   pack of illustrated headset/controller/tracker art bundled with the app -
   pick from those or browse to your own image/GIF/WebM.
6. **Picture Animation**: give the Normal and/or Low Battery picture its own
   idle Wobble/Shake/Pulse animation, so a static image isn't just sitting
   there. Picking one for the Low picture replaces the automatic red
   pulse-glow with your choice.
7. **Label Text / Battery % Text**: each gets its own font, size, color,
   animation, and outline - independent of one another.
8. **Animation**: if you chose "Hidden until low," pick how it pops in and
   out, and try it with **Test Animation** before saving.
9. **Placement**: drag it into position on the preview canvas - it snaps
   to align with anything else you've already placed.
10. Click **Save**.

</details>

<details>
<summary><strong>Adding an Overlay Effect (a standalone alert)</strong></summary>

1. Click **Add > Add Overlay Effect**.
2. **Target**: a **Specific Device**, or **All Devices** (optionally
   excluding a few from the multi-select list).
3. **Trigger**: Battery Low, Battery Normal, Device Disconnected, or Device
   Connected.
4. **Picture & Sound**: pick an image (or GIF/video) and a sound for the
   alert, or leave either blank to use the defaults.
5. **Caption Text** (optional): type a message, then set its position
   relative to the picture, font, size, color, an outline, and a wobble/
   shake/pulse animation.
6. **Animation**: pick how the alert pops in and out, and try it with
   **Test Animation** before saving.
7. **Placement**: drag it into position - same snap-to-align as Devices.
8. Click **Save**.

</details>

## Features

- Live battery % for any SteamVR device, with a low-battery pop-in alert
- Use your own pictures/GIFs/videos and sounds, plus a bundled pack of
  illustrated device art - or the built-in defaults
- Independent font/size/color/animation/outline customization for Label
  Text, Battery % Text, and Overlay Effect captions
- Optional idle animations (Wobble/Shake/Pulse) for device pictures
- Drag-to-position with snap-to-align, plus several pop/fade animations
- Nudge Groups keep multiple low-battery alerts from overlapping - lines
  them up automatically, oldest first
- Optional startup check for new releases, off by default
- Runs in English, Deutsch, Français, Español, 日本語, and Klingon

## Building from source

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "OhFudgeMyBatteryChat" --collect-all openvr --add-data "app/fonts;fonts" --add-data "assets;device_icons" main.py
```

## License

MIT - see [LICENSE](LICENSE). The bundled Klingon font is licensed
separately under the SIL Open Font License (see
`app/fonts/LICENSE-pIqaD-qolqoS.txt`).

---

<sub>Built with [Claude](https://claude.com) (Anthropic) via conversational pair-programming.</sub>

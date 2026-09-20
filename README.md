<div align="center">

<img src="docs/images/banner.png" alt="Oh Fudge, My Battery Chat!" width="100%">

*A SteamVR battery overlay for OBS - so chat can finally remind you.*

[![Download](https://img.shields.io/github/v/release/Jayconius/OhFudgeMyBatteryChat?style=for-the-badge&label=Download&color=2f855a)](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/latest)
[![Windows](https://img.shields.io/badge/platform-Windows-0078d4?style=for-the-badge&logo=windows&logoColor=white)](#)
[![SteamVR](https://img.shields.io/badge/requires-SteamVR-f97316?style=for-the-badge)](#)
[![MIT](https://img.shields.io/badge/license-MIT-4c8dff?style=for-the-badge)](LICENSE)

🌐 **English** | [Deutsch](README.de.md) | [Français](README.fr.md) | [Español](README.es.md) | [日本語](README.ja.md)

</div>

---

## ✨ What is it?

Your headset, controllers and trackers show their **battery live on stream**, and an **alert pops up** when something is running low. It's a normal OBS Browser Source - nothing to install into OBS.

<p align="center"><img src="docs/images/overlay.png" alt="The overlay over a game scene: six device batteries, a low battery alert and a muted microphone warning" width="90%"></p>

> [!TIP]
> **Not streaming?** You don't need OBS at all. Click **Open in Browser** in the app and use it as a personal low-battery alarm.

## 📥 Download

| | |
|---|---|
| 💿 **[Oh Fudge, My Battery Chat!](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/latest)** | The app. One exe, nothing to install. |
| 🎙️ **[Oh Fudge VR Macro App](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/macros-v1.0.0)** | Optional. Big mute buttons in a small window you can pin in VR. |
| 🧪 **[Demo Simulator](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/simulator-v2.0.0)** | Optional. Fake devices and microphones, to try things without a headset. |

> [!NOTE]
> The exes aren't code-signed, so Windows SmartScreen may say *"unknown publisher"*. Click **More info → Run anyway**.

## 🚀 Quick start

1. **Start it** with SteamVR already open. Your devices appear on the left.
2. **Click Add** to add a battery readout (*Add Device*) or an alert (*Add Overlay Effect*), then drag it where you want it. Double-click a row later to edit it.
3. **Copy the URL** at the top into OBS as a **Browser Source** (size 1920x1080). Done!

<p align="center"><img src="docs/images/app.png" alt="The app window: connected devices on the left, overlay items on the right" width="90%"></p>

## 🎛️ What can it do?

| | |
|---|---|
| 🔋 **Live batteries** | Any SteamVR device: headset, controllers, trackers. Use your own pictures, GIFs or videos - or the bundled art pack. |
| 🚨 **Low-battery alerts** | Pop in when a device drops below your %, with a sound. Nudge Groups line several alerts up so they never overlap. |
| ⚡ **Charging** | A picture while it charges, plus a warning if it's still draining on the charger. |
| 🎬 **Overlay Effects** | Standalone popups for: battery low / normal, device connected / disconnected, charging, tracking lost and headset removed *(experimental)*. |
| 💜 **Twitch chat commands** | Let chat trigger an alert with a command like `!battery` - for everyone, VIPs or mods. |
| 🎙️ **Microphones** *(experimental)* | Alerts for a wireless mic: connected, disconnected, muted, talking, silent. |
| 🔘 **Mute macros** *(experimental)* | Mute, unmute or toggle a mic with a global hotkey or a big on-screen button. |
| 🧩 **Sync Groups** | Devices that pop in together, as a set, once all of them are ready. |
| 🎨 **Make it yours** | Fonts, colors, outlines, wobble / shake / pulse animations, dark or light theme. |
| 🌍 **Languages** | English, Deutsch, Français, Español, 日本語 and Klingon. |

## 🧰 Everything in three windows

All the setup happens in three simple windows: **Add Device** (a live battery readout), **Add Effect** (an alert) and **Macros** (mute buttons and hotkeys). Click the picture to see it bigger.

<p align="center"><a href="docs/images/settings.png"><img src="docs/images/settings.png" alt="The Add Device, Add Effect and Macros windows side by side" width="100%"></a></p>

## 🎙️ Mute macros and the VR Macro App

*New (Experimental)*

1. Click **Macros** (top right), then **Add**: pick a microphone, what the macro does (mute, unmute or toggle) and, if you like, a **global hotkey** such as `CTRL+SHIFT+NUM5`. It works while a game has focus.
2. For big on-screen buttons click **Open Oh Fudge VR Macro App** in the same window. If it isn't in the app's folder yet, the app offers to download it - only after you click Yes, and it's only kept if its checksum matches GitHub's.
3. Each macro is a button that shows **LIVE**, **MUTED** or **OFFLINE**. It starts locked so nothing moves by accident: **right-click > Edit layout** to move and resize buttons and change their colors, then **Done**.
4. Pin the window in VR with **OVR Toolkit, XSOverlay or Desktop+**. It never takes focus from your game.

Macros change the Windows mute setting. A wireless mic's own hardware mute button usually can't be seen by Windows, so use a macro (or Windows' mute) if you want the **Mic Muted** alert to react.

<p align="center"><img src="docs/images/vr-macro-app.png" alt="The Oh Fudge VR Macro App: six microphone buttons showing LIVE, MUTED and OFFLINE, floating over a background" width="90%"></p>

## 🧪 Try it without a headset

Get the [Demo Simulator](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/simulator-v2.0.0) and drop `OhFudgeMyBatteryChatSimulator.exe` in the **same folder** as `OhFudgeMyBatteryChat.exe`. Run both: the app shows the simulator's fake devices and microphones, each with sliders and checkboxes. Close the simulator to go back to your real ones.

## 📖 How-to guides

<details>
<summary><b>Adding the OBS Browser Source</b></summary>

<br>

1. In OBS: **Sources > + > Browser Source**, name it, click OK.
2. Paste the URL from the top of the app (default `http://127.0.0.1:8710/overlay`).
3. Set **Width** `1920` and **Height** `1080`. Positions scale to any canvas, but sizes are calibrated to 1920x1080.
4. Leave **"Shutdown source when not visible"** unchecked, so alerts keep working while the scene is off screen.
5. No sound? Tick this source's **"Control audio via OBS"**.

Once added it stays in sync by itself: adding, editing or removing something refreshes the Browser Source within about a second.

</details>

<details>
<summary><b>Adding a Device (a live battery readout)</b></summary>

<br>

1. Click **Add > Add Device**.
2. Pick the device on the left (click **Refresh** if it's missing). Tick **"Show already-added devices"** to reuse one.
3. Give it a label and a low-battery threshold (%). Choose **Always visible** or **Hidden until low**.
4. **Pictures & Sound**: click **Choose...** to browse the bundled art pack, or pick your own image, GIF or WebM. Skip anything to use the defaults.
5. Style the text, add an animation, and drag it into place on the preview - it snaps to align with your other items.
6. Click **Save**.

</details>

<details>
<summary><b>Adding an Overlay Effect (a standalone alert)</b></summary>

<br>

1. Click **Add > Add Overlay Effect**.
2. **Target**: a **Specific Device**, **All Devices** (the alert shows while every one of them matches) or an **Audio Device** (a Windows microphone).
3. **Trigger**: pick when it shows, for example *Battery Low* or *Mic Muted*.
4. Pick a picture and sound (or use the defaults), and add a caption if you like.
5. Optional: type a **chat command** such as `!battery` so Twitch chat can trigger it too (link your account with **Connect Twitch Account** first).
6. Choose the animation, drag it into place, and click **Save**.

</details>

## 🔒 Privacy

- Everything runs on your PC. The overlay is served on `127.0.0.1` only.
- The app only goes online when you ask it to: the optional update check (off by default), linking Twitch (you approve on Twitch's own page - you never type a password into this app), or downloading an optional companion tool after you click Yes.

## ⚠️ Good to know

- **Windows only**, and SteamVR needs to be open to see real devices.
- Some devices report battery in chunks, so they may show **"n/a"** until they're power-cycled or actually low. That's the device's driver, not a bug here.
- The microphone, tracking-lost and headset-removed features are new. They're tested with the Demo Simulator (and one wireless mic); tracking and headset proximity aren't confirmed on real hardware yet - reports welcome!
- Hotkeys: another program using the same combination wins, some games block global hotkeys, and NumLock must be on for numpad keys.

## 🛠️ Build it yourself

Needs Python 3.12. The `.spec` files aren't in the repo, so use these commands:

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "OhFudgeMyBatteryChat" --collect-all openvr --collect-all pycaw --collect-all comtypes --add-data "app/fonts;fonts" --add-data "assets;device_icons" main.py
pyinstaller --onefile --windowed --name "OhFudgeVRMacroApp" --paths . tools/vr_macro_app.py
```

## 📄 License

MIT - see [LICENSE](LICENSE). The bundled Klingon font is licensed separately under the SIL Open Font License (see `app/fonts/LICENSE-pIqaD-qolqoS.txt`).

---

<sub>Not affiliated with Valve, Meta, Twitch or OBS. Those names belong to their owners.<br>Built with [Claude](https://claude.com) (Anthropic) via conversational pair-programming.</sub>

<div align="center">

# Oh Fudge, My Battery Chat!

[![Version](https://img.shields.io/badge/version-v1.2.0-blue)](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/v1.2.0)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6)](#)
[![Requires](https://img.shields.io/badge/requires-SteamVR-orange)](#)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

*Ein SteamVR-Akku-Overlay für OBS - damit der Chat dich endlich daran erinnern kann.*

🌐 [English](README.md) | **Deutsch** | [Français](README.fr.md) | [Español](README.es.md) | [日本語](README.ja.md)

![Screenshot](docs/screenshot.png)

</div>

Zeigt den Akkustand von Headset, Controllern und Trackern live im Stream an,
mit Einblend-Warnungen, wenn etwas zur Neige geht - als ganz normale
OBS-Browserquelle.

> [!TIP]
> **Streamst du nicht?** Du brauchst OBS gar nicht - klick in der App auf
> **Im Browser öffnen** und nutze sie als eigenständigen persönlichen
> Akku-Alarm.

## Schnellstart

1. Lade die exe aus den [Releases](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/latest)
   herunter und starte sie bei bereits laufendem **SteamVR**.
2. Klicke auf **Hinzufügen**, um eine Geräteanzeige oder einen Akku-Warnhinweis
   hinzuzufügen, und ziehe ihn an die gewünschte Position. Doppelklicke später
   auf einen Eintrag in der Liste, um ihn zu bearbeiten.
3. Kopiere die oben angezeigte URL in OBS als **Browserquelle** (Größe
   1920x1080).

Das war's schon - kein Python oder zusätzliche Installationen nötig, die exe
ist eigenständig lauffähig.

## Anleitungen

> [!NOTE]
> **Manche Geräte melden den Akkustand nur in Schüben, nicht fortlaufend.**
> Vor allem einzelne Tracker zeigen möglicherweise erst **„n/a"** an, bis sie
> neu gestartet wurden oder der Akku wirklich niedrig ist. Das liegt am
> Treiber des jeweiligen Geräts, nicht an dieser App - wenn andere Geräte
> korrekt Daten anzeigen, ist alles in Ordnung, und auch dieses Gerät zeigt
> echte Daten an, sobald sein Treiber sie meldet.

<details>
<summary><strong>Die OBS-Browserquelle einrichten</strong></summary>

1. In OBS: **Quellen > + > Browserquelle**, einen Namen vergeben, auf OK
   klicken.
2. Füge die oben in der App angezeigte URL ein (Standard:
   `http://127.0.0.1:8710/overlay`).
3. Setze **Breite** auf `1920` und **Höhe** auf `1080`. Die *Positionen* der
   Elemente skalieren problemlos auf jede Canvas-Größe, aber die *Größen*
   der Elemente sind im Positions-Editor auf diese Referenz von 1920x1080
   kalibriert - halte dich daran, damit alles so groß erscheint wie in der
   Vorschau, nicht größer oder kleiner.
4. Lasse **„Quelle beenden, wenn nicht sichtbar"** deaktiviert, wenn
   Akku-Warnungen auch dann funktionieren sollen, wenn diese Szene gerade
   nicht eingeblendet ist.
5. Falls ein Warnton nicht abgespielt wird, prüfe die Option **„Audio über
   OBS steuern"** dieser Quelle - manche OBS-Versionen blockieren
   Autoplay-Audio sonst.

Einmal hinzugefügt, bleibt sie von selbst synchron - das Hinzufügen,
Bearbeiten oder Entfernen eines Geräts/Effekts aktualisiert die bereits
geöffnete Browserquelle automatisch innerhalb von etwa einer Sekunde. Kein
manuelles Rechtsklicken mehr auf „Cache der aktuellen Seite aktualisieren"
nötig.

</details>

<details>
<summary><strong>Ein Gerät hinzufügen (eine Live-Akkuanzeige)</strong></summary>

1. Klicke auf **Hinzufügen > Gerät hinzufügen**.
2. Wähle das Gerät aus der Liste links aus (klicke auf **Aktualisieren**,
   falls es noch nicht angezeigt wird). Geräte, die bereits von einem
   anderen Gerät/Effekt verwendet werden, sind standardmäßig ausgeblendet -
   aktiviere **„Bereits hinzugefügte Geräte anzeigen"**, wenn du eines
   trotzdem erneut verwenden möchtest.
3. Vergib eine Bezeichnung und einen Schwellenwert für niedrigen Akkustand
   (%).
4. Wähle **Immer sichtbar** (Symbol bleibt bestehen, wechselt bei niedrigem
   Akku nur das Bild) oder **Versteckt bis niedrig** (blendet erst bei
   niedrigem Akku ein).
5. **Bilder & Ton**: Wähle ein Normalbild, ein Bild für niedrigen Akkustand
   und einen Warnton - oder überspringe einzelne davon, um die eingebauten
   Standards zu nutzen. Ein Klick auf **Auswählen...** öffnet direkt
   `Data\assets\device icons`, ein mit der App gebündeltes Paket
   illustrierter Headset-/Controller-/Tracker-Grafiken - wähle daraus oder
   durchsuche dein eigenes Bild/GIF/WebM.
6. **Bildanimation**: Gib dem Normal- und/oder Niedrigakku-Bild eine eigene
   Ruheanimation (Wackeln/Schütteln/Pulsieren), damit ein statisches Bild
   nicht einfach nur dasteht. Wählst du eine für das Niedrigakku-Bild,
   ersetzt sie das automatische rote Puls-Glühen.
7. **Bezeichnungstext / Akku-%-Text**: Beide erhalten eine eigene
   Schriftart, Größe, Farbe, Animation und Kontur - unabhängig voneinander.
8. **Animation**: Falls du „Versteckt bis niedrig" gewählt hast, lege fest,
   wie es ein- und ausblendet, und probiere es vor dem Speichern mit
   **Animation testen** aus.
9. **Platzierung**: Ziehe es auf der Vorschau-Fläche an die gewünschte
   Position - es rastet an bereits platzierten Elementen ein.
10. Klicke auf **Speichern**.

</details>

<details>
<summary><strong>Einen Overlay-Effekt hinzufügen (ein eigenständiger Alarm)</strong></summary>

1. Klicke auf **Hinzufügen > Overlay-Effekt hinzufügen**.
2. **Ziel**: ein **bestimmtes Gerät** oder **Alle Geräte** (optional
   einzelne über die Mehrfachauswahl-Liste ausschließen).
3. **Auslöser**: Akku niedrig, Akku normal, Gerät getrennt oder Gerät
   verbunden.
4. **Bild & Ton**: Wähle ein Bild (oder GIF/Video) und einen Ton für den
   Alarm, oder lasse eines davon leer, um die Standards zu nutzen.
5. **Beschriftungstext** (optional): Gib eine Nachricht ein und lege dann
   ihre Position relativ zum Bild fest, außerdem Schriftart, Größe, Farbe,
   eine Kontur und eine Wackel-/Schüttel-/Puls-Animation.
6. **Animation**: Lege fest, wie der Alarm ein- und ausblendet, und
   probiere es vor dem Speichern mit **Animation testen** aus.
7. **Platzierung**: Ziehe ihn an die gewünschte Position - gleiches
   Einrasten wie bei Geräten.
8. Klicke auf **Speichern**.

</details>

<details>
<summary><strong>Testen ohne SteamVR (der Demo-Simulator)</strong></summary>

Hol dir den eigenständigen [Demo-Simulator](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/simulator-v1.0.0),
wenn du Clips aufnehmen, Screenshots machen oder einfach Geräte-/Effekt-
Konfigurationen ausprobieren möchtest, ohne ein Headset aufzusetzen.

1. Lege `OhFudgeMyBatteryChatSimulator.exe` in denselben Ordner wie
   `OhFudgeMyBatteryChat.exe`, damit sich beide einen Data-Ordner teilen,
   und starte dann beide.
2. Er listet deine echten konfigurierten Geräte auf (oder vier generische
   Platzhalter plus ein 5-Punkte-Ganzkörper-Tracker-Set, falls du noch
   keine hinzugefügt hast), jeweils mit einem Akku-Schieberegler und einer
   „Verbunden"-Checkbox.
3. Die echte App übernimmt das automatisch, solange beide laufen -
   erfordert v1.2.0 oder neuer. Schließe den Simulator (oder stoppe ihn
   einfach), um die Kontrolle wieder an das echte SteamVR zu übergeben -
   kein Neustart nötig.

</details>

## Funktionen

- Live-Akkustand in % für jedes SteamVR-Gerät, mit Einblend-Warnung bei
  niedrigem Akku
- Eigene Bilder/GIFs/Videos und Töne verwenden, plus ein mitgeliefertes
  Paket illustrierter Gerätegrafiken - oder die eingebauten Standards
- Unabhängige Anpassung von Schriftart/Größe/Farbe/Animation/Kontur für
  Bezeichnungstext, Akku-%-Text und Overlay-Effekt-Beschriftungen
- Optionale Ruheanimationen (Wackeln/Schütteln/Pulsieren) für Gerätebilder
- Positionierung per Drag & Drop mit Einrasten, plus mehrere Einblend-/
  Ausblendanimationen
- Nudge-Gruppen verhindern, dass sich mehrere Akku-Warnungen überlappen -
  sie reihen sich automatisch auf, älteste zuerst
- Dunkles/helles Design, passt sich automatisch an deine Windows-
  Einstellung an (oder manuell umstellbar im Info-Fenster)
- Die OBS-Browserquelle bleibt automatisch synchron, wenn du etwas
  hinzufügst/änderst/entfernst - kein manuelles Aktualisieren nötig
- Ein eigenständiger [Demo-Simulator](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/simulator-v1.0.0)
  zum Testen/Aufnehmen ohne laufendes SteamVR
- Optionale Update-Prüfung beim Start, standardmäßig deaktiviert
- Läuft auf Englisch, Deutsch, Französisch, Spanisch, Japanisch und
  Klingonisch

## Aus dem Quellcode erstellen

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "OhFudgeMyBatteryChat" --collect-all openvr --add-data "app/fonts;fonts" --add-data "assets;device_icons" main.py
```

## Lizenz

MIT - siehe [LICENSE](LICENSE). Die mitgelieferte klingonische Schriftart
steht separat unter der SIL Open Font License (siehe
`app/fonts/LICENSE-pIqaD-qolqoS.txt`).

---

<sub>Entwickelt mit [Claude](https://claude.com) (Anthropic) im
dialogbasierten Pair-Programming.</sub>

<sub>Diese Übersetzung wurde maschinell erstellt (von Claude). Bei
Unklarheiten ist die englische Version ([README.md](README.md))
maßgeblich.</sub>

<div align="center">

# Oh Fudge, My Battery Chat!

[![Version](https://img.shields.io/badge/version-v1.1.0-blue)](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/v1.1.0)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6)](#)
[![Requires](https://img.shields.io/badge/requires-SteamVR-orange)](#)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

*Un overlay de batterie SteamVR pour OBS - pour que le chat puisse enfin
vous le rappeler.*

🌐 [English](README.md) | [Deutsch](README.de.md) | **Français** | [Español](README.es.md) | [日本語](README.ja.md)

![Screenshot](docs/screenshot.png)

</div>

Affiche en direct sur le stream le niveau de batterie de votre casque, de
vos manettes et de vos trackers, avec des alertes qui apparaissent quand
quelque chose est faible - comme une simple source de navigateur OBS.

> [!TIP]
> **Vous ne streamez pas ?** Vous n'avez pas besoin d'OBS du tout - cliquez
> sur **Ouvrir dans le navigateur** dans l'application pour l'utiliser
> comme alarme personnelle de batterie faible, en autonome.

## Démarrage rapide

1. Récupérez l'exe depuis les [Releases](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/latest)
   et lancez-le avec **SteamVR** déjà ouvert.
2. Cliquez sur **Ajouter** pour ajouter un affichage d'appareil ou une
   alerte de batterie faible, puis faites-le glisser en place.
3. Copiez l'URL affichée en haut dans OBS en tant que **source
   navigateur** (taille 1920x1080).

C'est tout - pas besoin de Python ni d'installations supplémentaires,
l'exe est autonome.

## Guides pratiques

> [!NOTE]
> **Certains appareils ne communiquent leur batterie que par à-coups, pas
> en continu.** Quelques trackers en particulier peuvent afficher
> **« n/a »** tant qu'ils n'ont pas été redémarrés, ou tant que la
> batterie n'est pas réellement faible. C'est le pilote de l'appareil qui
> en est responsable, pas un bug de cette application - si les autres
> appareils affichent bien des données, tout va bien, et celui-ci
> affichera aussi de vraies données dès que son pilote décidera de les
> communiquer.

<details>
<summary><strong>Ajouter la source navigateur OBS</strong></summary>

1. Dans OBS : **Sources > + > Source navigateur**, donnez-lui un nom,
   cliquez sur OK.
2. Collez l'URL affichée en haut de l'application (par défaut
   `http://127.0.0.1:8710/overlay`).
3. Réglez la **largeur** sur `1920` et la **hauteur** sur `1080`. Les
   *positions* des éléments s'adaptent bien à n'importe quelle taille de
   canevas, mais les *tailles* des éléments sont calibrées sur cette
   référence 1920x1080 dans l'éditeur de position - respectez-la pour que
   les éléments gardent la taille prévisualisée, ni plus grande ni plus
   petite.
4. Laissez **« Arrêter la source si non visible »** décoché si vous
   voulez que les alertes de batterie faible continuent de fonctionner
   même quand cette scène n'est pas affichée.
5. Si un son d'alerte ne se joue pas, vérifiez l'option **« Contrôler
   l'audio via OBS »** de cette source - certaines versions d'OBS
   bloquent l'audio en lecture automatique sans ça.

</details>

<details>
<summary><strong>Ajouter un appareil (un affichage de batterie en direct)</strong></summary>

1. Cliquez sur **Ajouter > Ajouter un appareil**.
2. Choisissez l'appareil dans la liste de gauche (cliquez sur
   **Actualiser** s'il n'apparaît pas encore).
3. Donnez-lui un libellé et un seuil de batterie faible (%).
4. Choisissez **Toujours visible** (l'icône reste en place, l'image
   change seulement quand la batterie est faible) ou **Masqué jusqu'à
   faible** (n'apparaît qu'une fois la batterie faible).
5. **Images & son** : choisissez une image normale, une image de batterie
   faible et un son d'alerte - ou ignorez l'un de ces éléments pour
   utiliser les valeurs par défaut intégrées. Cliquer sur **Choisir...**
   ouvre directement `Data\assets\device icons`, un pack d'illustrations
   de casques/manettes/trackers fourni avec l'application - choisissez-y
   une image ou parcourez votre propre image/GIF/WebM.
6. **Animation de l'image** : donnez à l'image normale et/ou à celle de
   batterie faible sa propre animation de repos (Wobble/Shake/Pulse), pour
   qu'une image statique ne reste pas figée. En choisir une pour l'image
   de batterie faible remplace la pulsation rouge automatique par votre
   choix.
7. **Texte du libellé / texte du % de batterie** : chacun dispose de sa
   propre police, taille, couleur, animation et contour - indépendamment
   l'un de l'autre.
8. **Animation** : si vous avez choisi « Masqué jusqu'à faible », choisissez
   comment l'élément apparaît et disparaît, et testez-le avec **Tester
   l'animation** avant d'enregistrer.
9. **Placement** : faites-le glisser sur le canevas d'aperçu - il s'aligne
   automatiquement sur tout ce que vous avez déjà placé.
10. Cliquez sur **Enregistrer**.

</details>

<details>
<summary><strong>Ajouter un effet d'overlay (une alerte autonome)</strong></summary>

1. Cliquez sur **Ajouter > Ajouter un effet d'overlay**.
2. **Cible** : un **appareil spécifique**, ou **Tous les appareils**
   (avec possibilité d'en exclure quelques-uns via la liste à sélection
   multiple).
3. **Déclencheur** : batterie faible, batterie normale, appareil
   déconnecté ou appareil connecté.
4. **Image & son** : choisissez une image (ou un GIF/vidéo) et un son
   pour l'alerte, ou laissez l'un des deux vide pour utiliser les valeurs
   par défaut.
5. **Texte de légende** (facultatif) : saisissez un message, puis
   réglez sa position par rapport à l'image, sa police, sa taille, sa
   couleur, un contour, et une animation wobble/shake/pulse.
6. **Animation** : choisissez comment l'alerte apparaît et disparaît, et
   testez-la avec **Tester l'animation** avant d'enregistrer.
7. **Placement** : faites-le glisser en place - même alignement
   automatique que pour les appareils.
8. Cliquez sur **Enregistrer**.

</details>

## Fonctionnalités

- Pourcentage de batterie en direct pour tout appareil SteamVR, avec
  alerte de batterie faible
- Utilisez vos propres images/GIFs/vidéos et sons, plus un pack
  d'illustrations d'appareils fourni - ou les valeurs par défaut
  intégrées
- Personnalisation indépendante de la police/taille/couleur/animation/
  contour pour le texte du libellé, le texte du % de batterie et les
  légendes des effets d'overlay
- Animations de repos facultatives (Wobble/Shake/Pulse) pour les images
  d'appareils
- Positionnement par glisser-déposer avec alignement automatique, plus
  plusieurs animations d'apparition/disparition
- Les groupes de décalage (Nudge Groups) évitent que plusieurs alertes de
  batterie faible se chevauchent - elles s'alignent automatiquement, les
  plus anciennes en premier
- Vérification facultative des nouvelles versions au démarrage,
  désactivée par défaut
- Fonctionne en anglais, allemand, français, espagnol, japonais et
  klingon

## Compiler depuis les sources

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "OhFudgeMyBatteryChat" --collect-all openvr --add-data "app/fonts;fonts" --add-data "assets;device_icons" main.py
```

## Licence

MIT - voir [LICENSE](LICENSE). La police klingonne fournie est sous
licence distincte SIL Open Font License (voir
`app/fonts/LICENSE-pIqaD-qolqoS.txt`).

---

<sub>Créé avec [Claude](https://claude.com) (Anthropic) via de la
programmation en binôme conversationnelle.</sub>

<sub>Cette traduction a été générée automatiquement (par Claude). En cas
de doute, la version anglaise ([README.md](README.md)) fait
référence.</sub>

<div align="center">

<img src="docs/images/banner.png" alt="Oh Fudge, My Battery Chat!" width="100%">

*Une superposition de batterie SteamVR pour OBS - pour que le chat puisse enfin vous le rappeler.*

[![Download](https://img.shields.io/github/v/release/Jayconius/OhFudgeMyBatteryChat?style=for-the-badge&label=Download&color=2f855a)](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/latest)
[![Windows](https://img.shields.io/badge/plateforme-Windows-0078d4?style=for-the-badge&logo=windows&logoColor=white)](#)
[![SteamVR](https://img.shields.io/badge/nécessite-SteamVR-f97316?style=for-the-badge)](#)
[![MIT](https://img.shields.io/badge/licence-MIT-4c8dff?style=for-the-badge)](LICENSE)

🌐 [English](README.md) | [Deutsch](README.de.md) | **Français** | [Español](README.es.md) | [日本語](README.ja.md)

</div>

---

## ✨ Qu'est-ce que c'est ?

Votre casque, vos manettes et vos trackers affichent leur **batterie en direct sur le stream**, et une **alerte apparaît** dès que l'un d'eux faiblit. C'est une source Navigateur OBS classique - rien à installer dans OBS.

<p align="center"><img src="docs/images/overlay.png" alt="La superposition sur une scène de jeu : six batteries d'appareils, une alerte de batterie faible et un avertissement de micro coupé" width="90%"></p>

> [!TIP]
> **Vous ne streamez pas ?** Vous n'avez pas besoin d'OBS. Cliquez sur **Ouvrir dans le navigateur** dans l'application et utilisez-la comme alarme personnelle de batterie faible.

## 📥 Téléchargement

| | |
|---|---|
| 💿 **[Oh Fudge, My Battery Chat!](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/latest)** | L'application. Un seul exe, rien à installer. |
| 🎙️ **[Oh Fudge VR Macro App](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/macros-v1.0.0)** | Facultatif. De gros boutons de coupure du micro dans une petite fenêtre à épingler en VR. |
| 🧪 **[Demo Simulator](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/simulator-v2.0.0)** | Facultatif. De faux appareils et micros, pour essayer sans casque. |

> [!NOTE]
> Les exe ne sont pas signés : Windows SmartScreen peut afficher *« éditeur inconnu »*. Cliquez sur **Informations complémentaires → Exécuter quand même**.

## 🚀 Démarrage rapide

1. **Lancez l'application** avec SteamVR déjà ouvert. Vos appareils apparaissent à gauche.
2. **Cliquez sur Ajouter** pour créer un affichage de batterie (*Ajouter un appareil*) ou une alerte (*Ajouter un effet d'overlay*), puis faites-le glisser à sa place. Double-cliquez sur une ligne pour la modifier plus tard.
3. **Copiez l'URL** du haut dans OBS comme **Source Navigateur** (taille 1920x1080). C'est tout !

<p align="center"><img src="docs/images/app.png" alt="La fenêtre de l'application : appareils connectés à gauche, éléments de la superposition à droite" width="90%"></p>

## 🎛️ Que peut-elle faire ?

| | |
|---|---|
| 🔋 **Batterie en direct** | Tout appareil SteamVR : casque, manettes, trackers. Vos propres images, GIF ou vidéos - ou le pack d'illustrations fourni. |
| 🚨 **Alertes de batterie faible** | Elles apparaissent sous votre seuil, avec un son. Les groupes Nudge alignent plusieurs alertes pour qu'elles ne se chevauchent jamais. |
| ⚡ **Charge** | Une image pendant la charge, et un avertissement si la batterie baisse malgré le chargeur. |
| 🎬 **Effets de superposition** | Pop-ups autonomes pour : batterie faible / normale, appareil connecté / déconnecté, charge, tracking perdu et casque retiré *(expérimental)*. |
| 💜 **Commandes du chat Twitch** | Laissez le chat déclencher une alerte avec une commande comme `!battery` - pour tous, les VIP ou les modérateurs. |
| 🎙️ **Micros** *(expérimental)* | Alertes pour un micro sans fil : connecté, déconnecté, coupé, en train de parler, silencieux. |
| 🔘 **Macros de coupure du micro** *(expérimental)* | Couper, réactiver ou basculer un micro avec un raccourci global ou un gros bouton à l'écran. |
| 🧩 **Groupes de synchronisation** | Des appareils qui apparaissent ensemble, comme un ensemble, une fois que tous sont prêts. |
| 🎨 **À votre goût** | Polices, couleurs, contours, animations (oscillation / secousse / pulsation), thème sombre ou clair. |
| 🌍 **Langues** | English, Deutsch, Français, Español, 日本語 et klingon. |

## 🎙️ Macros de coupure du micro et Oh Fudge VR Macro App

*Nouveau (expérimental)*

1. Cliquez sur **Macros** (en haut à droite), puis **Ajouter** : choisissez un micro, ce que fait la macro (couper, réactiver ou basculer) et, si vous le souhaitez, un **raccourci global** comme `CTRL+MAJ+NUM5`. Il fonctionne même quand un jeu a le focus.
2. Pour de gros boutons à l'écran, cliquez sur **Ouvrir Oh Fudge VR Macro App** dans la même fenêtre. Si elle n'est pas encore dans le dossier de l'application, celle-ci propose de la télécharger - seulement après votre clic sur Oui, et elle n'est conservée que si sa somme de contrôle correspond à celle de GitHub.
3. Chaque macro est un bouton qui affiche **LIVE**, **MUTED** ou **OFFLINE**. Elle démarre verrouillée pour que rien ne bouge par accident : **clic droit > Edit layout** pour déplacer, redimensionner et recolorer les boutons, puis **Done**.
4. Épinglez la fenêtre en VR avec **OVR Toolkit, XSOverlay ou Desktop+**. Elle ne prend jamais le focus de votre jeu.

Les macros modifient le réglage de sourdine de Windows. Le bouton de coupure d'un micro sans fil n'est généralement pas visible par Windows : utilisez une macro (ou la sourdine de Windows) pour que l'alerte **Micro coupé** réagisse.

<p align="center"><img src="docs/images/vr-macro-app.png" alt="L'Oh Fudge VR Macro App : six boutons de micro affichant LIVE, MUTED et OFFLINE, sur un arrière-plan" width="90%"></p>

## 🧪 Essayer sans casque

Récupérez le [Simulateur de démo](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/simulator-v2.0.0) et placez `OhFudgeMyBatteryChatSimulator.exe` dans le **même dossier** que `OhFudgeMyBatteryChat.exe`. Lancez les deux : l'application affiche les faux appareils et micros du simulateur, chacun avec des curseurs et des cases à cocher. Fermez le simulateur pour retrouver vos vrais appareils.

## 📖 Guides pratiques

<details>
<summary><b>Ajouter la source Navigateur OBS</b></summary>

<br>

1. Dans OBS : **Sources > + > Navigateur**, nommez-la, OK.
2. Collez l'URL affichée en haut de l'application (par défaut `http://127.0.0.1:8710/overlay`).
3. Réglez **Largeur** `1920` et **Hauteur** `1080`. Les positions s'adaptent à toute taille de canevas, mais les tailles sont calibrées sur 1920x1080.
4. Laissez **« Arrêter la source si non visible »** décoché, pour que les alertes continuent de fonctionner quand la scène n'est pas à l'écran.
5. Pas de son ? Cochez **« Contrôler l'audio via OBS »** pour cette source.

Une fois ajoutée, elle reste synchronisée toute seule : ajouter, modifier ou supprimer quelque chose rafraîchit la source en une seconde environ.

</details>

<details>
<summary><b>Ajouter un appareil (un affichage de batterie en direct)</b></summary>

<br>

1. Cliquez sur **Ajouter > Ajouter un appareil**.
2. Choisissez l'appareil à gauche (cliquez sur **Actualiser** s'il manque). Cochez **« Afficher les appareils déjà ajoutés »** pour en réutiliser un.
3. Donnez-lui un libellé et un seuil de batterie faible (%). Choisissez **Toujours visible** ou **Masqué jusqu'à faible**.
4. **Images et son** : cliquez sur **Choisir...** pour parcourir le pack d'illustrations fourni, ou choisissez votre propre image, GIF ou WebM. Ce que vous ignorez utilise les valeurs par défaut.
5. Stylez le texte, ajoutez une animation et faites-le glisser à sa place dans l'aperçu - il s'aligne sur vos autres éléments.
6. Cliquez sur **Enregistrer**.

</details>

<details>
<summary><b>Ajouter un effet d'overlay (une alerte autonome)</b></summary>

<br>

1. Cliquez sur **Ajouter > Ajouter un effet d'overlay**.
2. **Cible** : un **appareil précis**, **tous les appareils** (l'alerte s'affiche tant que tous correspondent) ou un **périphérique audio** (un micro Windows).
3. **Déclencheur** : choisissez quand elle s'affiche, par exemple *Batterie faible* ou *Micro coupé*.
4. Choisissez une image et un son (ou les valeurs par défaut) et ajoutez une légende si vous le souhaitez.
5. Facultatif : saisissez une **commande de chat** comme `!battery` pour que le chat Twitch puisse aussi la déclencher (liez d'abord votre compte avec **Connecter un compte Twitch**).
6. Choisissez l'animation, placez-la et cliquez sur **Enregistrer**.

</details>

## 🔒 Confidentialité

- Tout fonctionne sur votre PC. La superposition n'est servie que sur `127.0.0.1`.
- L'application ne se connecte à Internet que si vous le demandez : la vérification de mises à jour facultative (désactivée par défaut), la liaison avec Twitch (vous approuvez sur la page de Twitch - vous ne saisissez jamais de mot de passe dans cette application) ou le téléchargement d'un outil complémentaire facultatif après votre clic sur Oui.

## ⚠️ Bon à savoir

- **Windows uniquement**, et SteamVR doit être ouvert pour voir les vrais appareils.
- Certains appareils ne signalent leur batterie que par à-coups et peuvent afficher **« n/a »** jusqu'à un redémarrage ou une batterie vraiment faible. C'est le pilote de l'appareil, pas un bug ici.
- Les fonctions micro, tracking perdu et casque retiré sont nouvelles. Elles sont testées avec le Simulateur de démo (et un micro sans fil) ; le tracking et la détection du casque ne sont pas encore confirmés sur du vrai matériel - vos retours sont les bienvenus !
- Raccourcis : un autre programme utilisant la même combinaison l'emporte, certains jeux bloquent les raccourcis globaux, et Verr. num. doit être activé pour les touches du pavé numérique.

## 🛠️ Le compiler soi-même

Nécessite Python 3.12. Les fichiers `.spec` ne sont pas dans le dépôt, utilisez donc ces commandes :

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "OhFudgeMyBatteryChat" --collect-all openvr --collect-all pycaw --collect-all comtypes --add-data "app/fonts;fonts" --add-data "assets;device_icons" main.py
pyinstaller --onefile --windowed --name "OhFudgeVRMacroApp" --paths . tools/vr_macro_app.py
```

## 📄 Licence

MIT - voir [LICENSE](LICENSE). La police klingon fournie est sous licence distincte, la SIL Open Font License (voir `app/fonts/LICENSE-pIqaD-qolqoS.txt`).

---

<sub>Sans lien avec Valve, Meta, Twitch ou OBS. Ces noms appartiennent à leurs propriétaires.<br>Créé avec [Claude](https://claude.com) (Anthropic) par programmation en binôme conversationnelle.</sub>

"""Minimal i18n for the configurator GUI.

The app's own name ("Oh Fudge, My Battery Chat!") is a pun and stays the same
in every language, like a product name would - only the UI *content* around
it is translated. Klingon (tlh) is a fun best-effort localization using real
tlhIngan Hol vocabulary where it exists and reasonable invented compounds for
modern tech terms that Klingon has no canonical word for (there is no
certified Klingon translation of "dropdown menu") - treat it as an easter
egg, not an authoritative translation.

Usage: `from . import i18n` then `i18n.t("some_key")`. Missing translations
fall back to English, then to the raw key, so a half-translated language
never crashes or shows a blank label.

`t_piqad(key)` is a variant used only by "pure chrome" widgets (buttons,
frame titles, checkboxes - text with no embedded serial numbers, version
strings, or other Latin-only data) that renders in the real pIqaD script
when Klingon is active, since the bundled pIqaD font has no Latin glyphs at
all and would show blank boxes for anything else. See piqad.py.
"""
from . import piqad

LANGUAGES = {
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "ja": "日本語",
    "tlh": "tlhIngan Hol",
}

_current_lang = "en"


def set_language(lang: str):
    global _current_lang
    _current_lang = lang if lang in LANGUAGES else "en"


def get_language() -> str:
    return _current_lang


def t(key: str) -> str:
    entry = STRINGS.get(key)
    if not entry:
        return key
    return entry.get(_current_lang) or entry.get("en") or key


def t_piqad(key: str) -> str:
    text = t(key)
    if _current_lang == "tlh" and piqad.ensure_font_loaded():
        return piqad.transliterate(text)
    return text


# key -> {lang: text}
STRINGS = {
    # -- Main window chrome --------------------------------------------
    "steamvr_checking": {"en": "SteamVR: checking...", "de": "SteamVR: wird geprüft...", "fr": "SteamVR : vérification...", "es": "SteamVR: comprobando...", "ja": "SteamVR: 確認中...", "tlh": "SteamVR: wIghojtaH..."},
    "steamvr_connected_fmt": {"en": "SteamVR: Connected ({n} device(s))", "de": "SteamVR: Verbunden ({n} Gerät(e))", "fr": "SteamVR : Connecté ({n} appareil(s))", "es": "SteamVR: Conectado ({n} dispositivo(s))", "ja": "SteamVR: 接続済み（デバイス{n}台）", "tlh": "SteamVR: chu'wI' ({n} Duy)"},
    "steamvr_prefix": {"en": "SteamVR:", "de": "SteamVR:", "fr": "SteamVR :", "es": "SteamVR:", "ja": "SteamVR:", "tlh": "SteamVR:"},
    "steamvr_not_detected": {"en": "not detected", "de": "nicht gefunden", "fr": "non détecté", "es": "no detectado", "ja": "未検出", "tlh": "qatlh tu'lu'be'"},
    "btn_start_server": {"en": "Start Overlay Server", "de": "Overlay-Server starten", "fr": "Démarrer le serveur d'overlay", "es": "Iniciar servidor de superposición", "ja": "オーバーレイサーバーを開始", "tlh": "chu' HeghtaH"},
    "btn_stop_server": {"en": "Stop Overlay Server", "de": "Overlay-Server stoppen", "fr": "Arrêter le serveur d'overlay", "es": "Detener servidor de superposición", "ja": "オーバーレイサーバーを停止", "tlh": "chu' mev"},
    "btn_copy_url": {"en": "Copy URL", "de": "URL kopieren", "fr": "Copier l'URL", "es": "Copiar URL", "ja": "URLをコピー", "tlh": "URL qon"},
    "btn_open_browser": {"en": "Open in Browser", "de": "Im Browser öffnen", "fr": "Ouvrir dans le navigateur", "es": "Abrir en el navegador", "ja": "ブラウザで開く", "tlh": "leghwI'Daq poSmoH"},
    "panel_devices": {"en": "Connected SteamVR Devices", "de": "Verbundene SteamVR-Geräte", "fr": "Appareils SteamVR connectés", "es": "Dispositivos SteamVR conectados", "ja": "接続中のSteamVRデバイス", "tlh": "SteamVR Duy'a' chu'wI'"},
    "panel_items": {"en": "Overlay Items", "de": "Overlay-Elemente", "fr": "Éléments de l'overlay", "es": "Elementos de superposición", "ja": "オーバーレイ項目", "tlh": "chu' Doch"},
    "col_class": {"en": "Class", "de": "Klasse", "fr": "Classe", "es": "Clase", "ja": "種類", "tlh": "Segh"},
    "col_battery": {"en": "Battery", "de": "Akku", "fr": "Batterie", "es": "Batería", "ja": "バッテリー", "tlh": "HuH"},
    "col_serial": {"en": "Serial", "de": "Seriennummer", "fr": "Numéro de série", "es": "Número de serie", "ja": "シリアル", "tlh": "mI'"},
    "col_brand": {"en": "Brand", "de": "Marke", "fr": "Marque", "es": "Marca", "ja": "ブランド", "tlh": "chenmoHwI'"},
    "battery_no_battery": {"en": "No battery", "de": "Kein Akku", "fr": "Pas de batterie", "es": "Sin batería", "ja": "バッテリーなし", "tlh": "HuH Qo'"},

    "btn_ok": {"en": "OK", "de": "OK", "fr": "OK", "es": "Aceptar", "ja": "OK", "tlh": "toH"},
    "notice_title": {"en": "Battery Reporting Notice", "de": "Hinweis zur Akkuanzeige", "fr": "Remarque sur la batterie", "es": "Aviso sobre la batería", "ja": "バッテリー表示に関するお知らせ", "tlh": "HuH De' ghantoH"},
    "notice_battery_chunks_body": {
        "en": "Some SteamVR devices (especially certain trackers) only update their battery status in chunks, and may not report a percentage until the battery actually gets low or the device is freshly powered on. If a device shows no battery data here, that's normal - it isn't a bug, and it should appear once that device's driver decides to report it.",
        "de": "Manche SteamVR-Geräte (besonders bestimmte Tracker) aktualisieren ihren Akkustand nur in Schüben und melden möglicherweise erst einen Prozentwert, wenn der Akku wirklich niedrig ist oder das Gerät frisch eingeschaltet wurde. Wenn hier bei einem Gerät keine Akkudaten angezeigt werden, ist das normal - das ist kein Fehler, und der Wert sollte erscheinen, sobald der Treiber des Geräts ihn meldet.",
        "fr": "Certains appareils SteamVR (en particulier certains trackers) ne mettent à jour leur niveau de batterie que par à-coups, et peuvent ne signaler un pourcentage que lorsque la batterie est réellement faible ou que l'appareil vient d'être rallumé. Si un appareil n'affiche aucune donnée de batterie ici, c'est normal - ce n'est pas un bug, et la valeur devrait apparaître dès que le pilote de cet appareil décide de la signaler.",
        "es": "Algunos dispositivos SteamVR (especialmente ciertos rastreadores) solo actualizan su nivel de batería en bloques, y puede que no informen un porcentaje hasta que la batería esté realmente baja o el dispositivo se acabe de encender. Si un dispositivo no muestra datos de batería aquí, es normal - no es un error, y el valor debería aparecer en cuanto el controlador de ese dispositivo decida informarlo.",
        "ja": "一部のSteamVRデバイス（特定のトラッカーなど）はバッテリー状態をまとめて更新するため、実際にバッテリーが低下するか、電源を入れ直すまでパーセント表示が反映されないことがあります。ここでバッテリーデータが表示されないデバイスがあっても、それは正常な状態です。不具合ではなく、そのデバイスのドライバーが報告するタイミングで表示されるようになります。",
        "tlh": "puH Duy'a' ('ach tlha' mIw) HuH mI' loSDaq neH cha'; HuH mach 'oH DIchDaq neH pagh Duy chu'taHvIS mI' cha'. Duy HuH mI' tu'lu'be'chugh, motlh 'oH - Qagh Qo', 'ej chu'wI' wanI'DI' mI' cha' DIchDaq.",
    },
    "chk_dont_show_again": {"en": "Don't show this again", "de": "Nicht mehr anzeigen", "fr": "Ne plus afficher ce message", "es": "No volver a mostrar esto", "ja": "次回から表示しない", "tlh": "reH cha'Qo'"},
    "col_type": {"en": "Type", "de": "Typ", "fr": "Type", "es": "Tipo", "ja": "タイプ", "tlh": "Segh"},
    "col_label": {"en": "Label", "de": "Bezeichnung", "fr": "Libellé", "es": "Etiqueta", "ja": "ラベル", "tlh": "pong"},
    "col_device": {"en": "Device", "de": "Gerät", "fr": "Appareil", "es": "Dispositivo", "ja": "デバイス", "tlh": "Duy"},
    "col_mode": {"en": "Mode", "de": "Modus", "fr": "Mode", "es": "Modo", "ja": "モード", "tlh": "Do"},
    "col_threshold": {"en": "Threshold", "de": "Schwelle", "fr": "Seuil", "es": "Umbral", "ja": "しきい値", "tlh": "veH"},
    "add_btn": {"en": "Add", "de": "Hinzufügen", "fr": "Ajouter", "es": "Añadir", "ja": "追加", "tlh": "chel"},
    "menu_add_device": {"en": "Add Device...", "de": "Gerät hinzufügen...", "fr": "Ajouter un appareil...", "es": "Añadir dispositivo...", "ja": "デバイスを追加...", "tlh": "Duy chel..."},
    "menu_add_effect": {"en": "Add Overlay Effect...", "de": "Overlay-Effekt hinzufügen...", "fr": "Ajouter un effet d'overlay...", "es": "Añadir efecto de superposición...", "ja": "オーバーレイ効果を追加...", "tlh": "chu' nab chel..."},
    "btn_edit": {"en": "Edit", "de": "Bearbeiten", "fr": "Modifier", "es": "Editar", "ja": "編集", "tlh": "chojmoH"},
    "btn_remove": {"en": "Remove", "de": "Entfernen", "fr": "Supprimer", "es": "Eliminar", "ja": "削除", "tlh": "teq"},
    "footer_hint": {
        "en": "Add the URL above as a Browser Source in OBS (size 1920x1080). Positions are percentage-based, so other resolutions work too.",
        "de": "Fügen Sie die obige URL in OBS als Browser-Quelle hinzu (Größe 1920x1080). Positionen sind prozentual, andere Auflösungen funktionieren also auch.",
        "fr": "Ajoutez l'URL ci-dessus comme source navigateur dans OBS (taille 1920x1080). Les positions sont en pourcentage, donc les autres résolutions fonctionnent aussi.",
        "es": "Añade la URL de arriba como fuente de navegador en OBS (tamaño 1920x1080). Las posiciones son en porcentaje, así que otras resoluciones también funcionan.",
        "ja": "上記のURLをOBSのブラウザソースとして追加してください（サイズ1920x1080）。位置はパーセント基準なので、他の解像度でも動作します。",
        "tlh": "OBS Daq URL yIchel (1920x1080 tIn). Daqmey ratlh boch, latlh tInmey Qap je.",
    },
    "msg_select_item_title": {"en": "Select an item", "de": "Element auswählen", "fr": "Sélectionner un élément", "es": "Selecciona un elemento", "ja": "項目を選択してください", "tlh": "Doch yIwIv"},
    "msg_select_item_body": {"en": "Select a Device or Effect to edit first.", "de": "Wählen Sie zuerst ein Gerät oder einen Effekt zum Bearbeiten aus.", "fr": "Sélectionnez d'abord un appareil ou un effet à modifier.", "es": "Selecciona primero un dispositivo o efecto para editar.", "ja": "編集するデバイスまたは効果を先に選択してください。", "tlh": "Duy pagh nab yIwIv, vaj yIchojmoH"},
    "msg_remove_device_title": {"en": "Remove Device", "de": "Gerät entfernen", "fr": "Supprimer l'appareil", "es": "Eliminar dispositivo", "ja": "デバイスを削除", "tlh": "Duy teq"},
    "msg_remove_effect_title": {"en": "Remove Effect", "de": "Effekt entfernen", "fr": "Supprimer l'effet", "es": "Eliminar efecto", "ja": "効果を削除", "tlh": "nab teq"},
    "msg_remove_body_fmt": {"en": "Remove '{label}' from the overlay?", "de": "„{label}“ aus dem Overlay entfernen?", "fr": "Supprimer « {label} » de l'overlay ?", "es": "¿Eliminar '{label}' de la superposición?", "ja": "「{label}」をオーバーレイから削除しますか？", "tlh": "'{label}' chu'vo' teqlaH'a'?"},
    "type_device": {"en": "Device", "de": "Gerät", "fr": "Appareil", "es": "Dispositivo", "ja": "デバイス", "tlh": "Duy"},
    "type_effect": {"en": "Effect", "de": "Effekt", "fr": "Effet", "es": "Efecto", "ja": "効果", "tlh": "nab"},
    "mode_always": {"en": "Always", "de": "Immer", "fr": "Toujours", "es": "Siempre", "ja": "常時", "tlh": "reH"},
    "mode_low_only": {"en": "Low only", "de": "Nur bei niedrig", "fr": "Faible seulement", "es": "Solo si baja", "ja": "低下時のみ", "tlh": "'ach mach"},
    "devclass_HMD": {"en": "Headset", "de": "Headset", "fr": "Casque", "es": "Visor", "ja": "ヘッドセット", "tlh": "nach mIw"},
    "devclass_Controller": {"en": "Controller", "de": "Controller", "fr": "Manette", "es": "Mando", "ja": "コントローラー", "tlh": "ghoS mIw"},
    "devclass_GenericTracker": {"en": "Tracker", "de": "Tracker", "fr": "Traceur", "es": "Rastreador", "ja": "トラッカー", "tlh": "tlha' mIw"},
    "devclass_TrackingReference": {"en": "Base Station", "de": "Basisstation", "fr": "Station de base", "es": "Estación base", "ja": "ベースステーション", "tlh": "waw' pa'"},
    "devclass_Other": {"en": "Other", "de": "Andere", "fr": "Autre", "es": "Otro", "ja": "その他", "tlh": "latlh"},

    # -- About / Language -------------------------------------------------
    "about_btn": {"en": "ℹ About", "de": "ℹ Info", "fr": "ℹ À propos", "es": "ℹ Acerca de", "ja": "ℹ 情報", "tlh": "ℹ Del"},
    "about_title": {"en": "About", "de": "Info", "fr": "À propos", "es": "Acerca de", "ja": "情報", "tlh": "Del"},
    "about_version_label": {"en": "Version:", "de": "Version:", "fr": "Version :", "es": "Versión:", "ja": "バージョン:", "tlh": "boch mI':"},
    "about_author_label": {"en": "Author:", "de": "Autor:", "fr": "Auteur :", "es": "Autor:", "ja": "作者:", "tlh": "ghojmoHwI':"},
    "about_github_label": {"en": "GitHub:", "de": "GitHub:", "fr": "GitHub :", "es": "GitHub:", "ja": "GitHub:", "tlh": "GitHub:"},
    "about_close": {"en": "Close", "de": "Schließen", "fr": "Fermer", "es": "Cerrar", "ja": "閉じる", "tlh": "SoQmoH"},
    "lang_label": {"en": "Language:", "de": "Sprache:", "fr": "Langue :", "es": "Idioma:", "ja": "言語:", "tlh": "Hol:"},

    # -- Shared dialog chrome ----------------------------------------------
    "dlg_title_device": {"en": "Overlay Item - Device", "de": "Overlay-Element - Gerät", "fr": "Élément d'overlay - Appareil", "es": "Elemento de superposición - Dispositivo", "ja": "オーバーレイ項目 - デバイス", "tlh": "chu' Doch - Duy"},
    "dlg_title_effect": {"en": "Overlay Item - Effect", "de": "Overlay-Element - Effekt", "fr": "Élément d'overlay - Effet", "es": "Elemento de superposición - Efecto", "ja": "オーバーレイ項目 - 効果", "tlh": "chu' Doch - nab"},
    "frame_device": {"en": "Device", "de": "Gerät", "fr": "Appareil", "es": "Dispositivo", "ja": "デバイス", "tlh": "Duy"},
    "btn_refresh": {"en": "Refresh", "de": "Aktualisieren", "fr": "Actualiser", "es": "Actualizar", "ja": "更新", "tlh": "chu' qem"},
    "chk_manual_serial": {"en": "Manual serial (SteamVR not running right now)", "de": "Manuelle Seriennummer (SteamVR läuft gerade nicht)", "fr": "Numéro de série manuel (SteamVR n'est pas lancé actuellement)", "es": "Número de serie manual (SteamVR no está en ejecución ahora)", "ja": "手動シリアル入力（現在SteamVR未起動）", "tlh": "mI' ghItlhmoH (SteamVR Qapbe' DaH)"},
    "err_no_device_title": {"en": "No device", "de": "Kein Gerät", "fr": "Aucun appareil", "es": "Sin dispositivo", "ja": "デバイスなし", "tlh": "Duy tu'lu'be'"},
    "err_enter_serial": {"en": "Enter a serial number, or uncheck manual entry and pick a live device.", "de": "Geben Sie eine Seriennummer ein oder deaktivieren Sie die manuelle Eingabe und wählen Sie ein Gerät.", "fr": "Saisissez un numéro de série, ou décochez la saisie manuelle et choisissez un appareil actif.", "es": "Introduce un número de serie, o desmarca la entrada manual y elige un dispositivo activo.", "ja": "シリアル番号を入力するか、手動入力のチェックを外して実機デバイスを選んでください。", "tlh": "mI' yIghItlh pagh Duy yIwIv"},
    "err_no_devices_detected": {"en": "No SteamVR devices detected. Start SteamVR, click Refresh, or use manual serial entry.", "de": "Keine SteamVR-Geräte erkannt. Starten Sie SteamVR, klicken Sie auf Aktualisieren, oder geben Sie die Seriennummer manuell ein.", "fr": "Aucun appareil SteamVR détecté. Lancez SteamVR, cliquez sur Actualiser, ou saisissez le numéro de série manuellement.", "es": "No se detectaron dispositivos SteamVR. Inicia SteamVR, haz clic en Actualizar, o introduce el número de serie manualmente.", "ja": "SteamVRデバイスが検出されません。SteamVRを起動して更新するか、手動でシリアルを入力してください。", "tlh": "SteamVR Duy tu'lu'be'. SteamVR yIchu', 'ej chu' qem yItIv, pagh mI' yIghItlh"},
    "err_pick_device": {"en": "Pick a device from the list.", "de": "Wählen Sie ein Gerät aus der Liste.", "fr": "Choisissez un appareil dans la liste.", "es": "Elige un dispositivo de la lista.", "ja": "リストからデバイスを選択してください。", "tlh": "tetlhvo' Duy yIwIv"},
    "btn_choose": {"en": "Choose...", "de": "Auswählen...", "fr": "Choisir...", "es": "Elegir...", "ja": "選択...", "tlh": "yIwIv..."},
    "btn_test": {"en": "Test", "de": "Test", "fr": "Tester", "es": "Probar", "ja": "テスト", "tlh": "chojmoH"},
    "warn_sound_title": {"en": "Couldn't play sound", "de": "Ton konnte nicht abgespielt werden", "fr": "Impossible de lire le son", "es": "No se pudo reproducir el sonido", "ja": "音を再生できませんでした", "tlh": "wab tIqbe'"},
    "frame_pop_animation_device": {"en": "Pop Animation (Hidden until Low mode)", "de": "Einblend-Animation (Modus „Versteckt bis niedrig“)", "fr": "Animation d'apparition (mode « Masqué jusqu'à faible »)", "es": "Animación emergente (modo \"Oculto hasta bajo\")", "ja": "ポップアニメーション（低下まで非表示モード）", "tlh": "chu' vem (So' Do)"},
    "frame_pop_animation_effect": {"en": "Pop Animation", "de": "Einblend-Animation", "fr": "Animation d'apparition", "es": "Animación emergente", "ja": "ポップアニメーション", "tlh": "chu' vem"},
    "lbl_appear": {"en": "Appear:", "de": "Erscheinen:", "fr": "Apparition :", "es": "Aparecer:", "ja": "出現:", "tlh": "cha':"},
    "lbl_disappear": {"en": "Disappear:", "de": "Verschwinden:", "fr": "Disparition :", "es": "Desaparecer:", "ja": "消失:", "tlh": "ghIb:"},
    "btn_test_animation": {"en": "▶ Test Animation", "de": "▶ Animation testen", "fr": "▶ Tester l'animation", "es": "▶ Probar animación", "ja": "▶ アニメーションをテスト", "tlh": "▶ chu' chojmoH"},
    "btn_stop_test": {"en": "■ Stop Test", "de": "■ Test stoppen", "fr": "■ Arrêter le test", "es": "■ Detener prueba", "ja": "■ テスト停止", "tlh": "■ chojmoH mev"},
    "hint_loops": {"en": "Loops on the live overlay until you close this window.", "de": "Wiederholt sich im Live-Overlay, bis Sie dieses Fenster schließen.", "fr": "Se répète sur l'overlay en direct jusqu'à la fermeture de cette fenêtre.", "es": "Se repite en la superposición en vivo hasta que cierres esta ventana.", "ja": "このウィンドウを閉じるまで、実際のオーバーレイでループ再生されます。", "tlh": "SoQmoH pa' chu' vIt DIchDaq qaSqu'"},
    "frame_position": {"en": "Position (drag the box)", "de": "Position (Kästchen ziehen)", "fr": "Position (glisser le cadre)", "es": "Posición (arrastra el cuadro)", "ja": "位置（ボックスをドラッグ）", "tlh": "Daq (box yIchu')"},
    "lbl_icon_width": {"en": "Icon width (px):", "de": "Symbolbreite (px):", "fr": "Largeur de l'icône (px) :", "es": "Ancho del icono (px):", "ja": "アイコン幅（px）:", "tlh": "chevlaw ghurmey (px):"},
    "chk_snap": {"en": "Snap to other items", "de": "An andere Elemente einrasten", "fr": "Aligner sur les autres éléments", "es": "Ajustar a otros elementos", "ja": "他の項目にスナップ", "tlh": "latlh Doch tlhap"},
    "hint_snap": {"en": "Yellow line = aligned\nwith another item", "de": "Gelbe Linie = ausgerichtet\nan einem anderen Element", "fr": "Ligne jaune = aligné\navec un autre élément", "es": "Línea amarilla = alineado\ncon otro elemento", "ja": "黄色い線＝他の項目と\n位置が揃っています", "tlh": "SuD raQ = boch\nlatlh Doch je"},
    "canvas_drag_me": {"en": "drag me", "de": "ziehen", "fr": "glissez-moi", "es": "arrástrame", "ja": "ドラッグ", "tlh": "chu' vIH"},
    "btn_cancel": {"en": "Cancel", "de": "Abbrechen", "fr": "Annuler", "es": "Cancelar", "ja": "キャンセル", "tlh": "batlh 'Iw"},
    "btn_save": {"en": "Save", "de": "Speichern", "fr": "Enregistrer", "es": "Guardar", "ja": "保存", "tlh": "polmoH"},

    # -- Device item dialog --------------------------------------------
    "frame_basics": {"en": "Basics", "de": "Grundlagen", "fr": "Général", "es": "Básico", "ja": "基本設定", "tlh": "wa'DIch"},
    "lbl_label": {"en": "Label:", "de": "Bezeichnung:", "fr": "Libellé :", "es": "Etiqueta:", "ja": "ラベル:", "tlh": "pong:"},
    "lbl_threshold": {"en": "Low battery threshold:", "de": "Schwelle für niedrigen Akku:", "fr": "Seuil de batterie faible :", "es": "Umbral de batería baja:", "ja": "低下しきい値:", "tlh": "HuH mach veH:"},
    "radio_always": {"en": "Always visible (swap art when low)", "de": "Immer sichtbar (Bild wechselt bei niedrig)", "fr": "Toujours visible (change de visuel si faible)", "es": "Siempre visible (cambia de imagen si está bajo)", "ja": "常に表示（低下時に画像を切替）", "tlh": "reH cha' (mach 'oH ghu' choH)"},
    "radio_low_only": {"en": "Hidden until low (pop in when low)", "de": "Versteckt bis niedrig (erscheint bei niedrig)", "fr": "Masqué jusqu'à faible (apparaît si faible)", "es": "Oculto hasta bajo (aparece si está bajo)", "ja": "低下するまで非表示（低下時にポップイン）", "tlh": "So' 'ach mach (mach cha')"},
    "chk_show_label": {"en": "Show label text", "de": "Bezeichnung anzeigen", "fr": "Afficher le libellé", "es": "Mostrar texto de etiqueta", "ja": "ラベルテキストを表示", "tlh": "pong cha'"},
    "chk_show_percent": {"en": "Show battery %", "de": "Akku-% anzeigen", "fr": "Afficher le % de batterie", "es": "Mostrar % de batería", "ja": "バッテリー%を表示", "tlh": "HuH % cha'"},
    "frame_media": {"en": "Media (image, animated GIF, or WebM)", "de": "Medien (Bild, animiertes GIF oder WebM)", "fr": "Média (image, GIF animé ou WebM)", "es": "Medios (imagen, GIF animado o WebM)", "ja": "メディア（画像・GIF・WebM）", "tlh": "nagh mIw (mIw, GIF, WebM je)"},
    "lbl_normal_pic": {"en": "Normal picture:", "de": "Normalbild:", "fr": "Image normale :", "es": "Imagen normal:", "ja": "通常時の画像:", "tlh": "mIw motlh:"},
    "lbl_low_pic": {"en": "Low battery picture:", "de": "Bild bei niedrigem Akku:", "fr": "Image batterie faible :", "es": "Imagen de batería baja:", "ja": "低下時の画像:", "tlh": "mIw HuH mach:"},
    "lbl_warning_sound": {"en": "Warning sound:", "de": "Warnton:", "fr": "Son d'alerte :", "es": "Sonido de aviso:", "ja": "警告音:", "tlh": "ghuH wab:"},

    # -- Effect dialog ---------------------------------------------------
    "frame_target": {"en": "Target", "de": "Ziel", "fr": "Cible", "es": "Objetivo", "ja": "対象", "tlh": "chov"},
    "targetmode_specific": {"en": "Specific Device", "de": "Bestimmtes Gerät", "fr": "Appareil spécifique", "es": "Dispositivo específico", "ja": "特定のデバイス", "tlh": "wa' Duy"},
    "targetmode_all": {"en": "All Devices", "de": "Alle Geräte", "fr": "Tous les appareils", "es": "Todos los dispositivos", "ja": "すべてのデバイス", "tlh": "Hoch Duy"},
    "lbl_ignore_devices": {"en": "Ignore Devices:", "de": "Geräte ignorieren:", "fr": "Ignorer les appareils :", "es": "Ignorar dispositivos:", "ja": "無視するデバイス:", "tlh": "Duy yImev (law'):"},
    "hint_ignore_devices": {"en": "Click a device to toggle it in/out of the exclude list", "de": "Klicken Sie auf ein Gerät, um es zur Ausschlussliste hinzuzufügen oder zu entfernen", "fr": "Cliquez sur un appareil pour l'ajouter ou le retirer de la liste d'exclusion", "es": "Haz clic en un dispositivo para añadirlo o quitarlo de la lista de exclusión", "ja": "デバイスをクリックして除外リストに追加/削除します", "tlh": "Duy yIchu' 'ej mev tetlhDaq chel/teq"},
    "opt_none": {"en": "(None)", "de": "(Keins)", "fr": "(Aucun)", "es": "(Ninguno)", "ja": "（なし）", "tlh": "(pagh)"},
    "lbl_trigger": {"en": "Trigger:", "de": "Auslöser:", "fr": "Déclencheur :", "es": "Disparador:", "ja": "トリガー:", "tlh": "chargh:"},
    "lbl_battery_threshold": {"en": "Battery threshold:", "de": "Akku-Schwelle:", "fr": "Seuil de batterie :", "es": "Umbral de batería:", "ja": "バッテリーしきい値:", "tlh": "HuH veH:"},
    "hint_threshold_effect": {"en": "% (only used by Battery Low/Normal triggers)", "de": "% (nur für Auslöser „Akku niedrig/normal“)", "fr": "% (utilisé seulement pour les déclencheurs Batterie faible/normale)", "es": "% (solo se usa con los disparadores Batería baja/normal)", "ja": "%（バッテリー低下／正常トリガーのみ使用）", "tlh": "% ('ach HuH mach/motlh chargh lo'lu')"},
    "lbl_picture": {"en": "Picture:", "de": "Bild:", "fr": "Image :", "es": "Imagen:", "ja": "画像:", "tlh": "mIw:"},
    "frame_caption": {"en": "Caption Text", "de": "Beschriftungstext", "fr": "Texte de légende", "es": "Texto de leyenda", "ja": "キャプション文字", "tlh": "ghItlh"},
    "lbl_text": {"en": "Text:", "de": "Text:", "fr": "Texte :", "es": "Texto:", "ja": "テキスト:", "tlh": "ghItlh:"},
    "lbl_position": {"en": "Position:", "de": "Position:", "fr": "Position :", "es": "Posición:", "ja": "位置:", "tlh": "Daq:"},
    "lbl_animation": {"en": "Animation:", "de": "Animation:", "fr": "Animation :", "es": "Animación:", "ja": "アニメーション:", "tlh": "vIH:"},
    "lbl_font": {"en": "Font:", "de": "Schriftart:", "fr": "Police :", "es": "Fuente:", "ja": "フォント:", "tlh": "ghItlh Segh:"},
    "lbl_size": {"en": "Size:", "de": "Größe:", "fr": "Taille :", "es": "Tamaño:", "ja": "サイズ:", "tlh": "tIn:"},
    "lbl_font_color": {"en": "Font color:", "de": "Schriftfarbe:", "fr": "Couleur du texte :", "es": "Color de fuente:", "ja": "文字色:", "tlh": "rItlh ghItlh:"},
    "chk_outline": {"en": "Outline", "de": "Umrandung", "fr": "Contour", "es": "Contorno", "ja": "縁取り", "tlh": "tlhoy"},
    "lbl_thickness": {"en": "Thickness:", "de": "Dicke:", "fr": "Épaisseur :", "es": "Grosor:", "ja": "太さ:", "tlh": "chIm:"},
    "lbl_outline_color": {"en": "Outline color:", "de": "Umrandungsfarbe:", "fr": "Couleur du contour :", "es": "Color del contorno:", "ja": "縁取りの色:", "tlh": "rItlh tlhoy:"},

    # -- Trigger / animation option labels (combobox display values) ----
    "trigger_battery_low": {"en": "Battery Low", "de": "Akku niedrig", "fr": "Batterie faible", "es": "Batería baja", "ja": "バッテリー低下", "tlh": "HuH mach"},
    "trigger_battery_normal": {"en": "Battery Normal (not low)", "de": "Akku normal (nicht niedrig)", "fr": "Batterie normale (pas faible)", "es": "Batería normal (no baja)", "ja": "バッテリー正常（低下でない）", "tlh": "HuH motlh ('ach mach Qo')"},
    "trigger_device_disconnected": {"en": "Device Disconnected", "de": "Gerät getrennt", "fr": "Appareil déconnecté", "es": "Dispositivo desconectado", "ja": "デバイス切断", "tlh": "Duy chu'ta'be'"},
    "trigger_device_connected": {"en": "Device Connected", "de": "Gerät verbunden", "fr": "Appareil connecté", "es": "Dispositivo conectado", "ja": "デバイス接続", "tlh": "Duy chu'ta'"},

    "enter_pop_bottom": {"en": "Pop in from Bottom", "de": "Von unten einblenden", "fr": "Apparition par le bas", "es": "Aparecer desde abajo", "ja": "下からポップイン", "tlh": "bIng cha'"},
    "enter_pop_top": {"en": "Pop in from Top", "de": "Von oben einblenden", "fr": "Apparition par le haut", "es": "Aparecer desde arriba", "ja": "上からポップイン", "tlh": "Dung cha'"},
    "enter_pop_left": {"en": "Pop in from Left", "de": "Von links einblenden", "fr": "Apparition par la gauche", "es": "Aparecer desde la izquierda", "ja": "左からポップイン", "tlh": "poS cha'"},
    "enter_pop_right": {"en": "Pop in from Right", "de": "Von rechts einblenden", "fr": "Apparition par la droite", "es": "Aparecer desde la derecha", "ja": "右からポップイン", "tlh": "nIH cha'"},
    "enter_fade": {"en": "Fade in", "de": "Einblenden", "fr": "Fondu entrant", "es": "Aparecer con fundido", "ja": "フェードイン", "tlh": "nIb cha'"},
    "enter_fade_shake": {"en": "Fade in + Shake", "de": "Einblenden + Wackeln", "fr": "Fondu entrant + secousse", "es": "Fundido + sacudida", "ja": "フェードイン＋振動", "tlh": "nIb cha' + tlhup"},

    "exit_fade": {"en": "Fade out", "de": "Ausblenden", "fr": "Fondu sortant", "es": "Desaparecer con fundido", "ja": "フェードアウト", "tlh": "nIb ghIb"},
    "exit_slide_left": {"en": "Slide out Left", "de": "Nach links ausblenden", "fr": "Glisser vers la gauche", "es": "Deslizar hacia la izquierda", "ja": "左へスライドアウト", "tlh": "poS ghIb"},
    "exit_slide_right": {"en": "Slide out Right", "de": "Nach rechts ausblenden", "fr": "Glisser vers la droite", "es": "Deslizar hacia la derecha", "ja": "右へスライドアウト", "tlh": "nIH ghIb"},
    "exit_slide_top": {"en": "Slide out Up", "de": "Nach oben ausblenden", "fr": "Glisser vers le haut", "es": "Deslizar hacia arriba", "ja": "上へスライドアウト", "tlh": "Dung ghIb"},
    "exit_slide_bottom": {"en": "Slide out Down", "de": "Nach unten ausblenden", "fr": "Glisser vers le bas", "es": "Deslizar hacia abajo", "ja": "下へスライドアウト", "tlh": "bIng ghIb"},

    "textpos_above": {"en": "Above Picture", "de": "Über dem Bild", "fr": "Au-dessus de l'image", "es": "Sobre la imagen", "ja": "画像の上", "tlh": "mIw Dung"},
    "textpos_below": {"en": "Below Picture", "de": "Unter dem Bild", "fr": "Sous l'image", "es": "Debajo de la imagen", "ja": "画像の下", "tlh": "mIw bIng"},
    "textpos_middle": {"en": "Middle of Picture", "de": "Mitte des Bildes", "fr": "Au milieu de l'image", "es": "En medio de la imagen", "ja": "画像の中央", "tlh": "mIw botlh"},

    "textanim_none": {"en": "None", "de": "Keine", "fr": "Aucune", "es": "Ninguna", "ja": "なし", "tlh": "pagh"},
    "textanim_wobble": {"en": "Wobble", "de": "Wackeln", "fr": "Vacillement", "es": "Bamboleo", "ja": "ゆらゆら", "tlh": "tlhup mach"},
    "textanim_shake": {"en": "Shake", "de": "Schütteln", "fr": "Secousse", "es": "Sacudida", "ja": "振動", "tlh": "tlhup"},
    "textanim_pulse": {"en": "Pulse", "de": "Pulsieren", "fr": "Pulsation", "es": "Pulso", "ja": "パルス", "tlh": "tIv"},
}

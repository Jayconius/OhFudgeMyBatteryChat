<div align="center">

# Oh Fudge, My Battery Chat!

[![Version](https://img.shields.io/badge/version-v1.3.1-blue)](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/v1.3.1)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6)](#)
[![Requires](https://img.shields.io/badge/requires-SteamVR-orange)](#)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

*Una superposición de batería de SteamVR para OBS - para que el chat por
fin pueda recordártelo.*

🌐 [English](README.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | **Español** | [日本語](README.ja.md)

![Screenshot](docs/screenshot.png)

</div>

Muestra en directo, durante la retransmisión, la batería de tu casco, tus
mandos y tus trackers, con alertas emergentes cuando algo se está
quedando bajo - como una fuente de navegador de OBS normal.

> [!TIP]
> **¿No estás retransmitiendo?** No necesitas OBS para nada - haz clic en
> **Abrir en el navegador** dentro de la aplicación y úsala como una
> alarma personal independiente de batería baja.

## Inicio rápido

1. Descarga el exe desde [Releases](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/latest)
   y ejecútalo con **SteamVR** ya abierto.
2. Haz clic en **Añadir** para añadir una lectura de dispositivo o una
   alerta de batería baja, y luego arrástrala a su sitio. Haz doble clic
   en una fila de la lista más adelante para editarla.
3. Copia la URL que aparece arriba en OBS como **fuente de navegador**
   (tamaño 1920x1080).

Eso es todo - no hace falta Python ni instalaciones adicionales, el exe
es autónomo.

## Guías prácticas

> [!NOTE]
> **Algunos dispositivos solo informan la batería en bloques, no de
> forma continua.** En particular, algunos trackers pueden mostrar
> **"n/a"** hasta que se reinician o hasta que la batería realmente baja.
> Eso depende del propio controlador del dispositivo, no es un fallo de
> esta aplicación - si el resto de dispositivos muestra datos
> correctamente, todo va bien, y ese dispositivo también mostrará datos
> reales en cuanto su controlador decida informarlos.

<details>
<summary><strong>Añadir la fuente de navegador de OBS</strong></summary>

1. En OBS: **Fuentes > + > Fuente de navegador**, dale un nombre y haz
   clic en Aceptar.
2. Pega la URL que aparece arriba en la aplicación (por defecto
   `http://127.0.0.1:8710/overlay`).
3. Configura el **Ancho** en `1920` y el **Alto** en `1080`. Las
   *posiciones* de los elementos se adaptan bien a cualquier tamaño de
   lienzo, pero los *tamaños* de los elementos están calibrados con esta
   referencia de 1920x1080 en el editor de posición - respétala para que
   todo se vea del mismo tamaño que en la vista previa, ni más grande ni
   más pequeño.
4. Deja **"Detener la fuente cuando no sea visible"** desmarcado si
   quieres que las alertas de batería baja sigan funcionando aunque esa
   escena no esté en pantalla.
5. Si un sonido de advertencia no se reproduce, revisa la opción
   **"Controlar el audio a través de OBS"** de esta fuente - algunas
   versiones de OBS bloquean el audio de reproducción automática si no
   está activada.

Una vez añadida, se mantiene sincronizada sola - añadir, editar o eliminar
un Dispositivo/Efecto actualiza automáticamente la fuente de navegador ya
abierta en aproximadamente un segundo, sin necesidad de hacer clic derecho
para "Actualizar caché de la página actual".

</details>

<details>
<summary><strong>Añadir un dispositivo (una lectura de batería en directo)</strong></summary>

1. Haz clic en **Añadir > Añadir dispositivo**.
2. Elige el dispositivo de la lista de la izquierda (haz clic en
   **Actualizar** si todavía no aparece). Los dispositivos ya usados por
   otro Dispositivo/Efecto se ocultan por defecto - marca **"Mostrar
   dispositivos ya añadidos"** si necesitas reutilizar uno de todos modos.
3. Ponle una etiqueta y un umbral de batería baja (%).
4. Elige **Siempre visible** (el icono se queda fijo, solo cambia la
   imagen cuando la batería baja) o **Oculto hasta que baja** (aparece
   solo cuando la batería está baja).
5. **Imágenes y sonido**: elige una imagen normal, una imagen de batería
   baja y un sonido de advertencia - o deja cualquiera de ellos en blanco
   para usar los valores predeterminados. Al hacer clic en
   **Elegir...** se abre directamente `Data\assets\device icons`, un
   paquete de ilustraciones de cascos/mandos/trackers incluido con la
   aplicación - elige una de ahí o busca tu propia imagen/GIF/WebM.
6. **Animación de imagen**: dale a la imagen normal y/o a la de batería
   baja su propia animación de reposo (Wobble/Shake/Pulse), para que una
   imagen estática no se quede simplemente ahí parada. Si eliges una para
   la imagen de batería baja, sustituye el resplandor rojo pulsante
   automático por tu elección.
7. **Texto de la etiqueta / texto de % de batería**: cada uno tiene su
   propia fuente, tamaño, color, animación y contorno - de forma
   independiente entre sí.
8. **Animación**: si elegiste "Oculto hasta que baja", elige cómo
   aparece y desaparece, y pruébalo con **Probar animación** antes de
   guardar.
9. **Colocación**: arrástralo a su posición en el lienzo de vista previa
   - se ajusta automáticamente a cualquier otro elemento ya colocado.
10. Haz clic en **Guardar**.

</details>

<details>
<summary><strong>Añadir un efecto de superposición (una alerta independiente)</strong></summary>

1. Haz clic en **Añadir > Añadir efecto de superposición**.
2. **Objetivo**: un **dispositivo específico**, o **Todos los
   dispositivos** (opcionalmente excluyendo algunos desde la lista de
   selección múltiple).
3. **Disparador**: Batería baja, Batería normal, Dispositivo
   desconectado o Dispositivo conectado.
4. **Imagen y sonido**: elige una imagen (o GIF/vídeo) y un sonido para
   la alerta, o deja cualquiera de los dos en blanco para usar los
   valores predeterminados.
5. **Texto de la leyenda** (opcional): escribe un mensaje y luego
   define su posición respecto a la imagen, la fuente, el tamaño, el
   color, un contorno y una animación wobble/shake/pulse.
6. **Animación**: elige cómo aparece y desaparece la alerta, y pruébala
   con **Probar animación** antes de guardar.
7. **Colocación**: arrástrala a su posición - el mismo ajuste
   automático que con los dispositivos.
8. Haz clic en **Guardar**.

</details>

<details>
<summary><strong>Probar sin SteamVR (el Simulador de demostración)</strong></summary>

Consigue el [Simulador de demostración](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/simulator-v2.0.0)
independiente si quieres grabar clips, hacer capturas de pantalla, o
simplemente probar configuraciones de Dispositivos/Efectos sin ponerte el
casco.

1. Coloca `OhFudgeMyBatteryChatSimulator.exe` en la **misma carpeta** que
   `OhFudgeMyBatteryChat.exe` para que compartan una carpeta Data, y luego
   ejecuta ambos.
2. Lista tus Dispositivos realmente configurados (o cuatro marcadores de
   posición genéricos más un conjunto de trackers de cuerpo completo de 5
   puntos si aún no has añadido ninguno), cada uno con un control
   deslizante de batería y una casilla "Conectado".
3. La aplicación real lo detecta automáticamente mientras ambas se
   ejecutan - requiere v1.2.0 o posterior. Cierra el Simulador (o
   simplemente detenlo) para devolver el control al SteamVR real, sin
   necesidad de reiniciar.

</details>

<details>
<summary><strong>Macros de silencio y Oh Fudge VR Macro App (Nuevo, experimental)</strong></summary>

1. Haz clic en **Macros** (arriba a la derecha) y luego en **Añadir**: elige
   un micrófono (un **dispositivo de audio**), qué hace la macro (silenciar,
   activar o alternar) y, si quieres, un **atajo global** como
   `CTRL+MAYÚS+NUM5` - funciona aunque un juego tenga el foco o la aplicación
   esté en la bandeja del sistema.
2. Para botones grandes en pantalla, haz clic en **Abrir Oh Fudge VR Macro
   App** en la misma ventana. Si aún no está en la carpeta de la aplicación,
   esta ofrece descargarla desde su [versión de GitHub](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/macros-v1.0.0) - solo después
   de que pulses Sí, y solo se conserva si su suma de verificación coincide
   con la que publica GitHub. O descárgala tú y pon `OhFudgeVRMacroApp.exe`
   en la **misma carpeta** que `OhFudgeMyBatteryChat.exe`.
3. Muestra un botón por macro (**LIVE**, **MUTED** u **OFFLINE**). Empieza
   bloqueada para que nada se mueva por accidente. **Clic derecho > Edit
   layout** (modo edición) permite arrastrar y cambiar el tamaño de los botones,
   cambiar sus colores, redimensionar la ventana y más - pulsa **Done** para
   bloquearla de nuevo (los menús de la aplicación están en inglés).
4. Ancla la ventana en VR con una superposición de escritorio como XSOverlay,
   OVR Toolkit o Desktop+. Nunca le quita el foco a tu juego. ¿Prefieres un
   navegador? Los mismos botones están en `http://127.0.0.1:8710/macros`
   (con tu propio puerto).

Las macros cambian el ajuste de silencio de Windows. El botón de silencio de
un micrófono inalámbrico normalmente no lo ve Windows: usa una macro (o el
silencio de Windows) para que el disparador **Micrófono silenciado** reaccione.

</details>

## Características

- Porcentaje de batería en directo para cualquier dispositivo SteamVR,
  con alerta emergente de batería baja
- Usa tus propias imágenes/GIFs/vídeos y sonidos, además de un paquete
  incluido de ilustraciones de dispositivos - o los valores
  predeterminados integrados
- Personalización independiente de fuente/tamaño/color/animación/
  contorno para el texto de la etiqueta, el texto de % de batería y las
  leyendas de los efectos de superposición
- Animaciones de reposo opcionales (Wobble/Shake/Pulse) para las
  imágenes de dispositivos
- Colocación por arrastre con ajuste automático, además de varias
  animaciones de aparición/desvanecimiento
- Los grupos de desplazamiento (Nudge Groups) evitan que varias alertas
  de batería baja se superpongan - se alinean automáticamente, la más
  antigua primero
- Tema claro/oscuro, adaptándose automáticamente a tu configuración de
  Windows (o ajustable manualmente en Acerca de)
- La fuente de navegador de OBS se mantiene sincronizada automáticamente
  al añadir/editar/eliminar algo - sin necesidad de actualizar
  manualmente
- Un [Simulador de demostración](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/simulator-v2.0.0)
  independiente para probar/grabar sin SteamVR en ejecución
- Comprobación opcional de nuevas versiones al iniciar, desactivada por
  defecto
- **Comandos del chat de Twitch** - deja que el chat dispare una alerta con
  un comando como `!battery`, limitado a todos, VIP o moderadores (opcional -
  vinculas tu cuenta en la página de autorización de Twitch)
- **Grupos de sincronización** - dispositivos que aparecen juntos, como un
  conjunto, cuando todos están listos
- **Nuevo (experimental):** efectos para un dispositivo de audio (micrófono
  inalámbrico conectado, desconectado, silenciado, hablando, en silencio) y
  macros de silencio con atajos globales
- **Nuevo (experimental):** la aplicación independiente
  [Oh Fudge VR Macro App](https://github.com/Jayconius/OhFudgeMyBatteryChat/releases/tag/macros-v1.0.0) - tus botones de silencio en una pequeña
  ventana sin bordes que puedes anclar en VR
- Funciona en inglés, alemán, francés, español, japonés y klingon

## Compilar desde el código fuente

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "OhFudgeMyBatteryChat" --collect-all openvr --collect-all pycaw --collect-all comtypes --add-data "app/fonts;fonts" --add-data "assets;device_icons" main.py
pyinstaller --onefile --windowed --name "OhFudgeVRMacroApp" tools/vr_macro_app.py
```

## Licencia

MIT - consulta [LICENSE](LICENSE). La fuente klingon incluida tiene
licencia aparte bajo la SIL Open Font License (consulta
`app/fonts/LICENSE-pIqaD-qolqoS.txt`).

---

<sub>Creado con [Claude](https://claude.com) (Anthropic) mediante
programación conversacional en pareja.</sub>

<sub>Esta traducción se generó automáticamente (por Claude). Si algo no
queda claro, la versión en inglés ([README.md](README.md)) es la que
prevalece.</sub>

# ReySnap

Herramienta de capturas de pantalla para Linux inspirada en el flujo de
trabajo de PixPin/Snipaste: captura, anota sobre la propia selección y
ancla imágenes siempre visibles encima de las demás ventanas.

Escrita en Python + PySide6. Funciona en X11 (Linux Mint / Cinnamon) y,
de forma parcial, en Wayland (requiere `grim`).

## Funciones

- **Captura de región (Ctrl+1)** — la pantalla se congela y puedes:
  - arrastrar para seleccionar una región, o hacer **un clic** sobre una
    ventana para seleccionarla automáticamente;
  - ver una **lupa de píxeles** con coordenadas y color HEX mientras apuntas;
  - ajustar la selección con las asas de los bordes o moverla arrastrando;
  - **anotar directamente sobre la selección** con la barra de herramientas
    que aparece debajo: rectángulo (R), elipse (E), flecha (A), lápiz (P),
    marcador (M), texto (T) y **globos numerados (N)** para tutoriales,
    con paleta de colores y grosores;
  - terminar con **Enter / doble clic** (copiar), **Ctrl+2** dentro de la
    selección (anclar), **Ctrl+S** (guardar) o **Esc** (cancelar).
- **Anclar (Ctrl+2)** — si hay una imagen en el portapapeles la ancla
  directamente; si no, abre una captura cuya acción por defecto es anclar.
  Las imágenes ancladas se comportan como en PixPin:
  - **rueda del ratón** = zoom (5 %–500 %), **Ctrl+rueda** = opacidad,
    **clic central** = restaurar tamaño y opacidad;
  - arrastrar desde un borde redimensiona manteniendo la proporción;
  - **L** bloquea el pin, **T** alterna "siempre visible",
    **doble clic / Esc / Ctrl+W** lo cierran;
  - clic derecho abre el menú (copiar, guardar, bloquear, opacidad…);
  - el borde indica el estado: azul = activo, gris = inactivo,
    naranja = bloqueado.
- **OCR local (Shift+C en la captura)** — reconoce el texto de la
  selección con Tesseract, todo en tu máquina: español, inglés, chino
  simplificado, chino tradicional y ruso. Copia el resultado al
  portapapeles y lo muestra en una ventana editable.
- **Selector de color (Ctrl+Shift+C)** — lupa con rejilla de píxeles;
  clic copia el HEX al portapapeles.
- **Regla (Ctrl+Shift+R)** — mide distancias y ángulos en pantalla.
- **Anotar imagen** — abre un archivo de imagen en el editor de anotaciones.
- Bandeja del sistema, arranque automático al iniciar sesión y atajos
  configurables desde una interfaz gráfica (Preferencias → Atajos).
- **Interfaz en 5 idiomas** (español, English, 简体中文, 繁體中文,
  Русский) y **tema claro/oscuro/sistema**, ambos cambiables en vivo
  desde Preferencias.

Los atajos por defecto son los mismos que los de PixPin: `Ctrl+1` para
capturar y `Ctrl+2` para anclar.

## Instalación (Linux Mint / Ubuntu)

```bash
git clone https://github.com/TU_USUARIO/reysnap.git
cd reysnap
./install.sh
```

El instalador crea el entorno de Python, añade **ReySnap al menú de
aplicaciones** y lo deja **arrancando solo al iniciar sesión**. Para
quitarlo del menú y del autoinicio: `./install.sh --uninstall`.

En Wayland instala además `grim` (`sudo apt install grim`).

## Uso rápido

| Tecla | Acción |
|---|---|
| `Ctrl+1` | Capturar región |
| `Ctrl+2` | Anclar portapapeles / captura |
| Dentro de la captura: `R E A P M T N` | Herramientas de anotación |
| `Ctrl+Z` | Deshacer anotación |
| `Enter` / doble clic | Confirmar (copiar) |
| `Ctrl+S` | Guardar como… |
| Clic derecho / `Esc` | Descartar selección / cancelar |

Las capturas guardadas van a `~/Imágenes/ReySnap` (configurable), y la
configuración vive en `~/.config/reysnap/config.json`.

## Pruebas

Tests de humo sin abrir ventanas (modo offscreen de Qt):

```bash
.venv/bin/python tests/smoke_test.py
```

## Hoja de ruta

- Grabación de pantalla en GIF
- Captura con desplazamiento (scroll largo)
- Anotar imágenes ya ancladas (tecla Espacio sobre un pin)
- Mosaico/pixelado, foco (spotlight) y marca de agua
- Grupos de pins
- Soporte para Windows

## Limitaciones conocidas

- Los atajos globales usan `pynput`, que funciona bien en X11 pero tiene
  soporte limitado en Wayland.
- La detección automática de ventanas solo está disponible en X11.

## Licencia

MIT. ReySnap es una reimplementación independiente inspirada en la
experiencia de uso de PixPin; no contiene código ni recursos de PixPin.

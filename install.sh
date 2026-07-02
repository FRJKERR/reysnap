#!/usr/bin/env bash
# Instalador de PinSnap para Linux Mint / Ubuntu.
#
# Uso:  ./install.sh
#
# Crea un entorno virtual junto al código, instala las dependencias,
# añade PinSnap al menú de aplicaciones y lo deja arrancando solo al
# iniciar sesión.  Para desinstalar: ./install.sh --uninstall

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$APP_DIR/.venv"
BIN="$VENV/bin/pinsnap"
DESKTOP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
ICON_DIR="$HOME/.local/share/icons/hicolor/128x128/apps"

if [[ "${1:-}" == "--uninstall" ]]; then
    rm -f "$DESKTOP_DIR/pinsnap.desktop" "$AUTOSTART_DIR/pinsnap.desktop" \
          "$ICON_DIR/pinsnap.png"
    echo "PinSnap eliminado del menú y del arranque automático."
    echo "El código y el entorno virtual siguen en: $APP_DIR"
    exit 0
fi

echo "== PinSnap: instalación =="

# ----------------------------------------------------------------------
# 1. Dependencia del sistema (PySide6 la necesita para X11)
# ----------------------------------------------------------------------
if ! ldconfig -p | grep -q libxcb-cursor; then
    echo "-> Falta libxcb-cursor0; instalando (pedirá tu contraseña)…"
    sudo apt-get install -y libxcb-cursor0
fi

# Tesseract habilita el OCR (opcional pero recomendado)
if ! command -v tesseract >/dev/null; then
    echo "-> Instalando Tesseract para el OCR (español + inglés)…"
    sudo apt-get install -y tesseract-ocr tesseract-ocr-spa \
        tesseract-ocr-chi-sim tesseract-ocr-chi-tra tesseract-ocr-rus \
        || echo "   (OCR omitido; puedes instalarlo más tarde)"
fi

# ----------------------------------------------------------------------
# 2. Entorno de Python
# ----------------------------------------------------------------------
if [[ ! -x "$VENV/bin/python" ]]; then
    echo "-> Creando entorno virtual…"
    python3 -m venv "$VENV"
fi
echo "-> Instalando dependencias…"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -e "$APP_DIR"

# ----------------------------------------------------------------------
# 3. Icono y entrada de menú
# ----------------------------------------------------------------------
mkdir -p "$DESKTOP_DIR" "$AUTOSTART_DIR" "$ICON_DIR"
cp "$APP_DIR/resources/icons/pinsnap.png" "$ICON_DIR/pinsnap.png"

cat > "$DESKTOP_DIR/pinsnap.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PinSnap
Comment=Capturas de pantalla, anotaciones y anclado (estilo PixPin)
Exec=$BIN
Icon=pinsnap
Terminal=false
Categories=Utility;Graphics;
StartupNotify=false
EOF

# ----------------------------------------------------------------------
# 4. Arranque automático al iniciar sesión
# ----------------------------------------------------------------------
cp "$DESKTOP_DIR/pinsnap.desktop" "$AUTOSTART_DIR/pinsnap.desktop"
echo "X-GNOME-Autostart-enabled=true" >> "$AUTOSTART_DIR/pinsnap.desktop"

echo
echo "== Listo =="
echo "  • Menú:        busca 'PinSnap' en el menú de aplicaciones"
echo "  • Autoinicio:  arrancará solo la próxima vez que inicies sesión"
echo "  • Ahora mismo: $BIN &"
echo "  • Atajos:      Ctrl+1 captura · Ctrl+2 ancla"

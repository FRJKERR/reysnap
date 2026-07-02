# Política de seguridad

## Versiones con soporte

| Versión | Soporte |
| ------- | ------- |
| 1.x     | ✅      |

## Cómo reportar una vulnerabilidad

Si encuentras un problema de seguridad, **no abras un issue público**.
Escríbeme por la pestaña *Security → Report a vulnerability* de GitHub
(aviso privado) y lo atenderé lo antes posible.

## Alcance y diseño

ReySnap está diseñado para minimizar la superficie de ataque:

- **No hace ninguna conexión de red.** No hay telemetría, actualizaciones
  automáticas ni servicios en la nube; el OCR se ejecuta localmente con
  Tesseract.
- Los atajos globales usan un escuchador de teclado (`pynput`), necesario
  para detectar las combinaciones configuradas. Las teclas solo se comparan
  en memoria: no se registran, almacenan ni transmiten.
- La configuración vive en `~/.config/reysnap/config.json` y se valida al
  cargar (valores fuera de rango se corrigen).
- Las llamadas a programas externos (`grim` en Wayland, `tesseract` para
  OCR) usan listas de argumentos fijas, nunca una shell.

"""ReySnap – interface translations.

Spanish is the source language: every user-facing string in the code
is written in Spanish and wrapped in :func:`tr`, which looks up the
active language in the table below.  Unknown strings fall back to the
Spanish source, so a missing translation can never crash the UI.

Supported: Español, English, 简体中文, 繁體中文, Русский — the same set
the OCR ships with.
"""

from __future__ import annotations

# Code → native display name (shown in Preferences)
LANGUAGES = {
    "es": "Español",
    "en": "English",
    "zh_CN": "简体中文",
    "zh_TW": "繁體中文",
    "ru": "Русский",
}

_current = "es"


def set_language(code: str) -> None:
    global _current
    _current = code if code in LANGUAGES else "es"


def get_language() -> str:
    return _current


def tr(text: str) -> str:
    """Translate a Spanish source string into the active language."""
    if _current == "es":
        return text
    return _T.get(text, {}).get(_current, text)


# Spanish source → {lang: translation}
_T: dict = {
    # ------------------------------------------------------------- tray
    "Capturar pantalla": {
        "en": "Take screenshot", "zh_CN": "截图", "zh_TW": "截圖",
        "ru": "Сделать снимок",
    },
    "Anclar captura": {
        "en": "Pin capture", "zh_CN": "贴图", "zh_TW": "貼圖",
        "ru": "Закрепить снимок",
    },
    "Anotar imagen": {
        "en": "Annotate image", "zh_CN": "标注图片", "zh_TW": "標註圖片",
        "ru": "Аннотировать изображение",
    },
    "Selector de color": {
        "en": "Color picker", "zh_CN": "取色器", "zh_TW": "取色器",
        "ru": "Пипетка",
    },
    "Regla": {
        "en": "Ruler", "zh_CN": "标尺", "zh_TW": "標尺", "ru": "Линейка",
    },
    "Preferencias": {
        "en": "Preferences", "zh_CN": "偏好设置", "zh_TW": "偏好設定",
        "ru": "Настройки",
    },
    "Salir": {
        "en": "Quit", "zh_CN": "退出", "zh_TW": "結束", "ru": "Выход",
    },
    # ---------------------------------------------------------- overlay
    "Rectángulo (R)": {
        "en": "Rectangle (R)", "zh_CN": "矩形 (R)", "zh_TW": "矩形 (R)",
        "ru": "Прямоугольник (R)",
    },
    "Elipse (E)": {
        "en": "Ellipse (E)", "zh_CN": "椭圆 (E)", "zh_TW": "橢圓 (E)",
        "ru": "Эллипс (E)",
    },
    "Flecha (A)": {
        "en": "Arrow (A)", "zh_CN": "箭头 (A)", "zh_TW": "箭頭 (A)",
        "ru": "Стрелка (A)",
    },
    "Lápiz (P)": {
        "en": "Pencil (P)", "zh_CN": "铅笔 (P)", "zh_TW": "鉛筆 (P)",
        "ru": "Карандаш (P)",
    },
    "Marcador (M)": {
        "en": "Highlighter (M)", "zh_CN": "荧光笔 (M)", "zh_TW": "螢光筆 (M)",
        "ru": "Маркер (M)",
    },
    "Texto (T)": {
        "en": "Text (T)", "zh_CN": "文字 (T)", "zh_TW": "文字 (T)",
        "ru": "Текст (T)",
    },
    "Globos numerados (N)": {
        "en": "Numbered badges (N)", "zh_CN": "序号标注 (N)",
        "zh_TW": "序號標註 (N)", "ru": "Нумерация (N)",
    },
    "Deshacer (Ctrl+Z)": {
        "en": "Undo (Ctrl+Z)", "zh_CN": "撤销 (Ctrl+Z)",
        "zh_TW": "復原 (Ctrl+Z)", "ru": "Отменить (Ctrl+Z)",
    },
    "Anclar a la pantalla (Ctrl+2)": {
        "en": "Pin to screen (Ctrl+2)", "zh_CN": "贴到屏幕 (Ctrl+2)",
        "zh_TW": "貼到螢幕 (Ctrl+2)", "ru": "Закрепить на экране (Ctrl+2)",
    },
    "Reconocer texto – OCR (Shift+C)": {
        "en": "Recognize text – OCR (Shift+C)", "zh_CN": "文字识别 OCR (Shift+C)",
        "zh_TW": "文字辨識 OCR (Shift+C)", "ru": "Распознать текст – OCR (Shift+C)",
    },
    "Guardar como… (Ctrl+S)": {
        "en": "Save as… (Ctrl+S)", "zh_CN": "另存为… (Ctrl+S)",
        "zh_TW": "另存新檔… (Ctrl+S)", "ru": "Сохранить как… (Ctrl+S)",
    },
    "Cancelar (Esc)": {
        "en": "Cancel (Esc)", "zh_CN": "取消 (Esc)", "zh_TW": "取消 (Esc)",
        "ru": "Отмена (Esc)",
    },
    "Copiar y cerrar (Enter)": {
        "en": "Copy and close (Enter)", "zh_CN": "复制并关闭 (Enter)",
        "zh_TW": "複製並關閉 (Enter)", "ru": "Скопировать и закрыть (Enter)",
    },
    "Grosor {w}px": {
        "en": "Width {w}px", "zh_CN": "粗细 {w}px", "zh_TW": "粗細 {w}px",
        "ru": "Толщина {w}px",
    },
    "Arrastre para seleccionar una región · clic = ventana · Esc para cancelar": {
        "en": "Drag to select a region · click = window · Esc to cancel",
        "zh_CN": "拖动框选区域 · 单击选择窗口 · Esc 取消",
        "zh_TW": "拖曳框選區域 · 點擊選擇視窗 · Esc 取消",
        "ru": "Перетащите, чтобы выделить область · клик = окно · Esc — отмена",
    },
    # -------------------------------------------------------------- pin
    "Copiar imagen": {
        "en": "Copy image", "zh_CN": "复制图片", "zh_TW": "複製圖片",
        "ru": "Скопировать изображение",
    },
    "Guardar como…": {
        "en": "Save as…", "zh_CN": "另存为…", "zh_TW": "另存新檔…",
        "ru": "Сохранить как…",
    },
    "Bloquear": {
        "en": "Lock", "zh_CN": "锁定", "zh_TW": "鎖定", "ru": "Заблокировать",
    },
    "Siempre visible": {
        "en": "Always on top", "zh_CN": "置顶", "zh_TW": "置頂",
        "ru": "Поверх всех окон",
    },
    "Mostrar borde": {
        "en": "Show border", "zh_CN": "显示边框", "zh_TW": "顯示邊框",
        "ru": "Показывать рамку",
    },
    "Opacidad": {
        "en": "Opacity", "zh_CN": "不透明度", "zh_TW": "不透明度",
        "ru": "Непрозрачность",
    },
    "Tamaño original (100 %)": {
        "en": "Original size (100 %)", "zh_CN": "原始大小 (100 %)",
        "zh_TW": "原始大小 (100 %)", "ru": "Исходный размер (100 %)",
    },
    "Cerrar": {
        "en": "Close", "zh_CN": "关闭", "zh_TW": "關閉", "ru": "Закрыть",
    },
    "Guardar imagen anclada": {
        "en": "Save pinned image", "zh_CN": "保存贴图", "zh_TW": "儲存貼圖",
        "ru": "Сохранить закреплённое изображение",
    },
    # ------------------------------------------------------ preferences
    "ReySnap – Preferencias": {
        "en": "ReySnap – Preferences", "zh_CN": "ReySnap – 偏好设置",
        "zh_TW": "ReySnap – 偏好設定", "ru": "ReySnap – Настройки",
    },
    "Restablecer atajos": {
        "en": "Reset shortcuts", "zh_CN": "重置快捷键", "zh_TW": "重設快捷鍵",
        "ru": "Сбросить горячие клавиши",
    },
    "Cancelar": {
        "en": "Cancel", "zh_CN": "取消", "zh_TW": "取消", "ru": "Отмена",
    },
    "Guardar": {
        "en": "Save", "zh_CN": "保存", "zh_TW": "儲存", "ru": "Сохранить",
    },
    "Carpeta de guardado:": {
        "en": "Save folder:", "zh_CN": "保存目录：", "zh_TW": "儲存資料夾：",
        "ru": "Папка для сохранения:",
    },
    "Examinar…": {
        "en": "Browse…", "zh_CN": "浏览…", "zh_TW": "瀏覽…", "ru": "Обзор…",
    },
    "Formato de imagen:": {
        "en": "Image format:", "zh_CN": "图片格式：", "zh_TW": "圖片格式：",
        "ru": "Формат изображения:",
    },
    "Copiar al portapapeles tras capturar": {
        "en": "Copy to clipboard after capture", "zh_CN": "截图后复制到剪贴板",
        "zh_TW": "截圖後複製到剪貼簿", "ru": "Копировать в буфер после снимка",
    },
    "Mostrar cursor en la captura": {
        "en": "Show cursor in capture", "zh_CN": "截图包含鼠标指针",
        "zh_TW": "截圖包含滑鼠指標", "ru": "Показывать курсор на снимке",
    },
    "Retardo de captura:": {
        "en": "Capture delay:", "zh_CN": "截图延时：", "zh_TW": "截圖延時：",
        "ru": "Задержка снимка:",
    },
    "General": {
        "en": "General", "zh_CN": "常规", "zh_TW": "一般", "ru": "Общие",
    },
    "Haga clic en el campo de atajo y pulse la combinación de teclas deseada.": {
        "en": "Click a shortcut field and press the desired key combination.",
        "zh_CN": "点击快捷键输入框并按下想要的组合键。",
        "zh_TW": "點擊快捷鍵輸入框並按下想要的組合鍵。",
        "ru": "Нажмите на поле и введите нужное сочетание клавиш.",
    },
    "Capturar pantalla:": {
        "en": "Take screenshot:", "zh_CN": "截图：", "zh_TW": "截圖：",
        "ru": "Снимок экрана:",
    },
    "Anclar captura:": {
        "en": "Pin capture:", "zh_CN": "贴图：", "zh_TW": "貼圖：",
        "ru": "Закрепить снимок:",
    },
    "Selector de color:": {
        "en": "Color picker:", "zh_CN": "取色器：", "zh_TW": "取色器：",
        "ru": "Пипетка:",
    },
    "Regla:": {
        "en": "Ruler:", "zh_CN": "标尺：", "zh_TW": "標尺：", "ru": "Линейка:",
    },
    "Anotar imagen:": {
        "en": "Annotate image:", "zh_CN": "标注图片：", "zh_TW": "標註圖片：",
        "ru": "Аннотировать изображение:",
    },
    "Atajos": {
        "en": "Shortcuts", "zh_CN": "快捷键", "zh_TW": "快捷鍵",
        "ru": "Горячие клавиши",
    },
    "Opacidad predeterminada:": {
        "en": "Default opacity:", "zh_CN": "默认不透明度：",
        "zh_TW": "預設不透明度：", "ru": "Непрозрачность по умолчанию:",
    },
    "Mostrar borde en ventanas ancladas": {
        "en": "Show border on pinned windows", "zh_CN": "贴图显示边框",
        "zh_TW": "貼圖顯示邊框", "ru": "Рамка у закреплённых окон",
    },
    "Ancladas": {
        "en": "Pinned", "zh_CN": "贴图", "zh_TW": "貼圖", "ru": "Закреплённые",
    },
    "Tema:": {
        "en": "Theme:", "zh_CN": "主题：", "zh_TW": "主題：", "ru": "Тема:",
    },
    "Idioma:": {
        "en": "Language:", "zh_CN": "语言：", "zh_TW": "語言：", "ru": "Язык:",
    },
    "Iniciar automáticamente al iniciar sesión": {
        "en": "Start automatically at login", "zh_CN": "开机自动启动",
        "zh_TW": "開機自動啟動", "ru": "Автозапуск при входе",
    },
    "Avanzado": {
        "en": "Advanced", "zh_CN": "高级", "zh_TW": "進階",
        "ru": "Дополнительно",
    },
    "Conflicto de atajos": {
        "en": "Shortcut conflict", "zh_CN": "快捷键冲突", "zh_TW": "快捷鍵衝突",
        "ru": "Конфликт горячих клавиш",
    },
    'El atajo "{seq}" está asignado a "{a}" y a "{b}".\nElija atajos diferentes.': {
        "en": 'The shortcut "{seq}" is assigned to both "{a}" and "{b}".\nPlease choose different shortcuts.',
        "zh_CN": "快捷键“{seq}”同时分配给了“{a}”和“{b}”。\n请选择不同的快捷键。",
        "zh_TW": "快捷鍵「{seq}」同時分配給了「{a}」和「{b}」。\n請選擇不同的快捷鍵。",
        "ru": "Сочетание «{seq}» назначено и для «{a}», и для «{b}».\nВыберите разные сочетания.",
    },
    "Sistema": {
        "en": "System", "zh_CN": "跟随系统", "zh_TW": "跟隨系統",
        "ru": "Системная",
    },
    "Claro": {
        "en": "Light", "zh_CN": "浅色", "zh_TW": "淺色", "ru": "Светлая",
    },
    "Oscuro": {
        "en": "Dark", "zh_CN": "深色", "zh_TW": "深色", "ru": "Тёмная",
    },
    "Seleccionar carpeta de guardado": {
        "en": "Select save folder", "zh_CN": "选择保存目录",
        "zh_TW": "選擇儲存資料夾", "ru": "Выберите папку для сохранения",
    },
    # -------------------------------------------------------------- app
    "Abrir imagen para anotar": {
        "en": "Open image to annotate", "zh_CN": "打开图片进行标注",
        "zh_TW": "開啟圖片進行標註", "ru": "Открыть изображение",
    },
    "Guardar captura": {
        "en": "Save screenshot", "zh_CN": "保存截图", "zh_TW": "儲存截圖",
        "ru": "Сохранить снимок",
    },
    "Imágenes": {
        "en": "Images", "zh_CN": "图片", "zh_TW": "圖片", "ru": "Изображения",
    },
    "Todos los archivos": {
        "en": "All files", "zh_CN": "所有文件", "zh_TW": "所有檔案",
        "ru": "Все файлы",
    },
    # -------------------------------------------------------------- OCR
    "No se reconoció ningún texto en la selección.": {
        "en": "No text was recognized in the selection.",
        "zh_CN": "未在选区中识别到文字。", "zh_TW": "未在選區中辨識到文字。",
        "ru": "В выделении не распознан текст.",
    },
    "ReySnap – Texto reconocido": {
        "en": "ReySnap – Recognized text", "zh_CN": "ReySnap – 识别结果",
        "zh_TW": "ReySnap – 辨識結果", "ru": "ReySnap – Распознанный текст",
    },
    "El texto ya está copiado al portapapeles. Puedes editarlo aquí:": {
        "en": "The text is already on the clipboard. You can edit it here:",
        "zh_CN": "文字已复制到剪贴板，可在此编辑：",
        "zh_TW": "文字已複製到剪貼簿，可在此編輯：",
        "ru": "Текст уже скопирован в буфер обмена. Его можно отредактировать здесь:",
    },
    "Copiar de nuevo y cerrar": {
        "en": "Copy again and close", "zh_CN": "重新复制并关闭",
        "zh_TW": "重新複製並關閉", "ru": "Скопировать снова и закрыть",
    },
    "OCR no disponible. Instálalo con:": {
        "en": "OCR is not available. Install it with:",
        "zh_CN": "OCR 不可用，请安装：", "zh_TW": "OCR 不可用，請安裝：",
        "ru": "OCR недоступен. Установите:",
    },
    "El OCR falló: {error}": {
        "en": "OCR failed: {error}", "zh_CN": "OCR 失败：{error}",
        "zh_TW": "OCR 失敗：{error}", "ru": "Сбой OCR: {error}",
    },
    # ------------------------------------------------------ ruler/picker
    "Haga clic y arrastre para medir · Esc para cancelar": {
        "en": "Click and drag to measure · Esc to cancel",
        "zh_CN": "点击并拖动进行测量 · Esc 取消",
        "zh_TW": "點擊並拖曳進行測量 · Esc 取消",
        "ru": "Нажмите и перетащите для измерения · Esc — отмена",
    },
    "Clic para copiar · Esc para cancelar": {
        "en": "Click to copy · Esc to cancel", "zh_CN": "单击复制 · Esc 取消",
        "zh_TW": "點擊複製 · Esc 取消", "ru": "Клик — копировать · Esc — отмена",
    },
}

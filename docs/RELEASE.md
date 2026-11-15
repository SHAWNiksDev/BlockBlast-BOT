# Сборка и проверка

Исходники работают с Python 3.10+ на Windows и Linux. Установите `requirements-desktop.txt` и `requirements-build.txt`.

Проверка: `python -m unittest discover -s tests -q` (на Linux задайте `QT_QPA_PLATFORM=offscreen`).

Сборка Windows: `python scripts/windows_tools.py`, затем `python scripts/build_windows.py`.
Сборка Linux: установите ADB, FFmpeg, Tesseract 5+ и выполните `python scripts/build_linux.py`.
Проверка готового пакета: `python scripts/check_bundle.py --bundle dist/BlockBlast-BOT-windows-x86_64` (для Linux замените имя папки).

GitHub Actions проверяет исходники, готовый GUI, шрифты, OCR на сгенерированном изображении, нативные инструменты, блокировку контроллера и работу из папки с кириллицей. Физическое USB-подключение на Windows не проверено.

Приватные снимки и калибровка устройства не публикуются. Проверки, зависевшие от этих снимков, удалены; оставшийся набор не подтверждает распознавание всех реальных тем игры. Для нового устройства требуется калибровка.

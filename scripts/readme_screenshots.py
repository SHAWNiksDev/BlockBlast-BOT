"""Render README previews using generated data, without ADB or local history."""
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtTest import QTest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from blockblast.config import DEFAULTS
from blockblast.desktop import Window

SHAPES = {0: ((0, 0), (0, 1), (1, 0)),
          1: ((0, 0), (0, 1), (0, 2)),
          2: ((0, 0), (0, 1), (1, 0), (1, 1))}
CELLS = {(r, c) for r in range(8) for c in range(8)
         if (r >= 5 and c in (0, 1, 5, 6)) or (r in (2, 3) and c in (3, 4))}


def phone_preview():
    image = Image.new('RGB', (480, 900), '#161c2b')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(ROOT/'blockblast/assets/fonts/DejaVuSans-Bold.ttf'), 24)
    small = ImageFont.truetype(str(ROOT/'blockblast/assets/fonts/DejaVuSans.ttf'), 16)
    draw.text((240, 70), 'BLOCKBLAST BOT', font=font, anchor='mm', fill='#e7ecf5')
    draw.text((240, 110), 'DEMO / GENERATED PREVIEW', font=small, anchor='mm', fill='#9aa8bc')
    for r in range(8):
        for c in range(8):
            x, y = 24+c*54, 235+r*54
            draw.rounded_rectangle((x+2, y+2, x+50, y+50), radius=6,
                                   fill='#7c8cff' if (r, c) in CELLS else '#252e3c')
    for slot, shape in SHAPES.items():
        for r, c in shape:
            x, y = 50+slot*140+c*24, 740+r*24
            draw.rounded_rectangle((x, y, x+21, y+21), radius=3, fill='#7c8cff')
    return image


def main():
    output = ROOT/'docs/previews'
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setStyle('Fusion')
    with TemporaryDirectory(prefix='blockblast-readme-') as folder:
        isolated = Path(folder)
        (isolated/'profiles').mkdir()
        (isolated/'profiles/default.json').write_text('{}\n')
        with patch('blockblast.desktop.ROOT', isolated), \
             patch('blockblast.desktop.load', return_value=dict(DEFAULTS)), \
             patch('blockblast.desktop.save', side_effect=AssertionError('Preview must not save settings')):
            window = Window(discover=False)
            window.timer.stop()
            window.discovered([('demo-device', 'Android · демонстрация')], '')
            window.phone.set_image(phone_preview())
            window.board.set_board(sum(1 << (r*8+c) for r, c in CELLS))
            window.queue.set_pieces(SHAPES)
            window.stats_data = dict(score=12480, best=25000, moves=36, lines=18,
                                     moves_per_minute=24, attempts=36, rejected=0)
            window.update_stats()
            window.set_status('ready')
            window.activity.setPlainText('Предпросмотр интерфейса. Телефон не подключается, ходы не выполняются.\n'
                                         'Поле, фигуры и показатели созданы для иллюстрации.')
            window.show()
            QTest.qWait(500)
            window.status.setText('Демонстрация интерфейса · вымышленные данные')
            if not window.grab().save(str(output/'overview-dark.png')):
                raise RuntimeError('Cannot save overview preview')
            window.theme = 'light'
            window.theme_combo.blockSignals(True)
            window.theme_combo.setCurrentIndex(window.theme_combo.findData('light'))
            window.theme_combo.blockSignals(False)
            window.apply_theme()
            window.tabs.setCurrentIndex(1)
            window.settings_categories.setCurrentRow(1)
            QTest.qWait(300)
            window.status.setText('Демонстрация интерфейса · вымышленные данные')
            if not window.grab().save(str(output/'settings-light.png')):
                raise RuntimeError('Cannot save settings preview')
            window.close()
            from blockblast.calibration import SetupDialog
            from blockblast.vision import State, Piece
            class DemoCapture(QObject):
                result=Signal(object,str)
                finished=Signal()
                def __init__(self,*args):super().__init__()
                def start(self):pass
                def isRunning(self):return False
            with patch('blockblast.calibration.Capture',DemoCapture):
                setup=SetupDialog('demo-device',isolated)
                setup.image=phone_preview();setup.view.set_image(setup.image)
                setup.board=[24,235,456,667];setup.tray=[24,700,456,850];setup.pitch.setValue(24)
                setup.update_regions()
                state=State(sum(1<<(r*8+c) for r,c in CELLS),
                            {i:Piece(shape,(0,0),(0,0,1,1)) for i,shape in SHAPES.items()},
                            tuple(setup.board),(480,900))
                with patch('blockblast.calibration.read',return_value=state):setup.verify()
                setup.show();QTest.qWait(300)
                if not setup.grab().save(str(output/'setup-demo.png')):
                    raise RuntimeError('Cannot save setup preview')
                setup.close()
    print(output)


if __name__ == '__main__':
    main()

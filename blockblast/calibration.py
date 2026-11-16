"""Phone setup: capture in a worker, select regions, verify before saving."""
from pathlib import Path
import uuid

from PySide6.QtCore import Qt, QRectF, Signal, QThread
from PySide6.QtGui import QPainter, QColor, QImage, QPen
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QWidget, QDoubleSpinBox, QFormLayout)
from .adb import ADB
from .runtime import DeviceLease
from .profile import validate_profile
from .vision import read, board_bounds
from .storage import write_json
from .i18n import tr
from .desktop_widgets import BoardView, PieceQueue


def region_profile(size, board, tray, pitch, gain=1.5, lift=2.25):
    profile = dict(screen_size=list(size), board=list(board), tray=list(tray),
                   tray_cell=pitch, drag_gain=gain, lift_cells=lift,
                   release_bias_cells=.25)
    validate_profile(profile)
    if tray[1] < board[3]:
        raise ValueError('Tray must be below the board')
    if board[2]-board[0] < 80 or tray[3]-tray[1] < pitch:
        raise ValueError('Selected region is too small')
    return profile


class Capture(QThread):
    result = Signal(object, str)

    def __init__(self, serial, parent=None):
        super().__init__(parent)
        self.serial = serial

    def run(self):
        try:
            with DeviceLease(self.serial):
                adb = ADB(self.serial)
                adb.check_foreground('com.block.juggle')
                image = adb.screenshot()
            self.result.emit(image, '')
        except Exception as exc:
            self.result.emit(None, str(exc))


class RegionView(QWidget):
    selected = Signal(object)

    def __init__(self):
        super().__init__()
        self.image = None
        self.regions = []
        self.start = None
        self.end = None
        self.setMinimumSize(280, 360)

    def set_image(self, image):
        image = image.convert('RGB')
        self.image = QImage(image.tobytes(), image.width, image.height,
                            image.width*3, QImage.Format.Format_RGB888).copy()
        self.update()

    def image_rect(self):
        if self.image is None:
            return QRectF()
        scale = min(self.width()/self.image.width(), self.height()/self.image.height())
        w, h = self.image.width()*scale, self.image.height()*scale
        return QRectF((self.width()-w)/2, (self.height()-h)/2, w, h)

    def point(self, position):
        rect = self.image_rect()
        if rect.isEmpty() or not rect.contains(position):
            return None
        return ((position.x()-rect.x())*self.image.width()/rect.width(),
                (position.y()-rect.y())*self.image.height()/rect.height())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start = self.point(event.position())
            self.end = self.start

    def mouseMoveEvent(self, event):
        if self.start is not None:
            point = self.point(event.position())
            if point is not None:
                self.end = point
                self.update()

    def mouseReleaseEvent(self, event):
        if self.start is None:
            return
        point = self.point(event.position())
        if point is not None:
            x0,y0 = self.start; x1,y1 = point
            if abs(x1-x0)>5 and abs(y1-y0)>5:
                self.selected.emit([round(min(x0,x1)), round(min(y0,y1)),
                                    round(max(x0,x1)), round(max(y0,y1))])
        self.start = self.end = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.image is None:
            return
        rect = self.image_rect()
        painter.drawImage(rect, self.image)
        regions = list(self.regions)
        if self.start and self.end:
            regions.append([*self.start, *self.end])
        for index, region in enumerate(regions):
            x0,y0,x1,y1 = region
            sx,sy = rect.width()/self.image.width(),rect.height()/self.image.height()
            painter.setPen(QPen(QColor('#7c8cff' if index==0 else '#56d8ad'), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(rect.x()+x0*sx,rect.y()+y0*sy,(x1-x0)*sx,(y1-y0)*sy).normalized())


class SetupDialog(QDialog):
    def __init__(self, serial, root, lang='ru', parent=None):
        super().__init__(parent)
        self.lang=lang; self.root=Path(root); self.image=None
        self.board=None; self.tray=None; self.mode='board'; self.checked=None
        self.profile_path=None
        self.setWindowTitle(self.t('setup_phone'));self.resize(960,800)
        layout=QVBoxLayout(self)
        self.note=QLabel(self.t('setup_intro'));self.note.setWordWrap(True);layout.addWidget(self.note)
        self.view=RegionView();self.view.selected.connect(self.select)
        body=QHBoxLayout();body.addWidget(self.view,1)
        preview=QVBoxLayout();preview.addWidget(QLabel(self.t('board')))
        self.preview_board=BoardView();self.preview_board.setFixedSize(240,240);preview.addWidget(self.preview_board)
        self.preview_pieces=PieceQueue();self.preview_pieces.setFixedWidth(240);preview.addWidget(self.preview_pieces);preview.addStretch()
        body.addLayout(preview);layout.addLayout(body,1)
        row=QHBoxLayout()
        for key, action in [('setup_board',lambda:self.choose('board')),
                            ('setup_tray',lambda:self.choose('tray'))]:
            button=QPushButton(self.t(key));button.clicked.connect(action);row.addWidget(button)
        layout.addLayout(row)
        form=QFormLayout();self.pitch=QDoubleSpinBox();self.pitch.setRange(2,400)
        self.gain=QDoubleSpinBox();self.gain.setRange(.1,5);self.gain.setSingleStep(.05);self.gain.setValue(1.5)
        self.lift=QDoubleSpinBox();self.lift.setRange(0,5);self.lift.setSingleStep(.05);self.lift.setValue(2.25)
        for key,field in [('setup_pitch',self.pitch),('setup_gain',self.gain),('setup_lift',self.lift)]:
            form.addRow(self.t(key),field);field.valueChanged.connect(self.invalidate)
        layout.addLayout(form)
        row=QHBoxLayout();self.check=QPushButton(self.t('setup_check'));self.check.setEnabled(False);self.check.clicked.connect(self.verify)
        self.save_button=QPushButton(self.t('save'));self.save_button.setEnabled(False);self.save_button.clicked.connect(self.store)
        cancel=QPushButton(self.t('setup_cancel'));cancel.clicked.connect(self.reject)
        row.addWidget(self.check);row.addWidget(self.save_button);row.addWidget(cancel);layout.addLayout(row)
        self.capture=Capture(serial,self);self.capture.result.connect(self.captured);self.capture.finished.connect(self.capture_finished);self.capture.start()

    def t(self,key,**values):return tr(key,self.lang,**values)

    def capture_finished(self):
        self.setEnabled(True)

    def reject(self):
        if self.capture.isRunning():
            self.note.setText(self.t('setup_wait'))
            return
        super().reject()

    def closeEvent(self,event):
        if self.capture.isRunning():event.ignore()
        else:super().closeEvent(event)

    def captured(self,image,error):
        if error:self.note.setText(error);return
        self.image=image;self.view.set_image(image);self.check.setEnabled(True)
        try:
            import numpy as np
            self.board=list(board_bounds(np.asarray(image).astype('int16')))
            cell=(self.board[2]-self.board[0])/8;w,h=image.size
            self.tray=[round(w*.07),round(self.board[3]+cell*1.15),round(w*.93),round(min(h*.88,self.board[3]+cell*3.5))]
            self.pitch.setValue(cell*.45);self.update_regions()
            self.verify()
        except ValueError:
            self.note.setText(self.t('setup_select_board'))

    def choose(self,mode):
        self.mode=mode;self.note.setText(self.t('setup_select_'+mode))

    def select(self,region):
        if self.mode=='board':
            self.board=region;self.pitch.setValue((region[2]-region[0])/8*.45)
            self.mode='tray';self.note.setText(self.t('setup_select_tray'))
        else:self.tray=region
        self.invalidate();self.update_regions()

    def update_regions(self):
        self.view.regions=[r for r in (self.board,self.tray) if r is not None];self.view.update()

    def invalidate(self,*args):
        self.checked=None;self.save_button.setEnabled(False)
        self.preview_board.set_board(0);self.preview_pieces.set_pieces({})

    def verify(self):
        self.invalidate()
        try:
            if self.image is None or self.board is None or self.tray is None:
                raise ValueError(self.t('setup_regions_required'))
            profile=region_profile(self.image.size,self.board,self.tray,self.pitch.value(),self.gain.value(),self.lift.value())
            state=read(self.image,profile)
            if not state.pieces:raise ValueError(self.t('setup_empty'))
            self.checked=profile;self.save_button.setEnabled(True)
            self.preview_board.set_board(state.board);self.preview_pieces.set_pieces({key:piece.shape for key,piece in state.pieces.items()})
            self.note.setText(self.t('setup_verified',count=len(state.pieces)))
        except (ValueError,RuntimeError) as exc:self.note.setText(str(exc))

    def store(self):
        if self.checked is None:return
        try:
            directory=self.root/'profiles';directory.mkdir(exist_ok=True)
            path=directory/('local-'+uuid.uuid4().hex+'.json')
            write_json(path,self.checked);self.profile_path=path
        except OSError as exc:self.note.setText(str(exc));return
        self.accept()

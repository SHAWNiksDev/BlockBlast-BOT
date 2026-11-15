"""Small painted controls: vector icons, reveal, switches, game and timeline views."""
from collections import deque
from datetime import datetime
from html import escape
from math import ceil,hypot,cos,sin,pi
from PySide6.QtCore import Qt,QRectF,QSize,QPointF,QVariantAnimation,QEasingCurve,QTimer,Signal
from PySide6.QtGui import (QPainter,QColor,QPen,QPainterPath,QIcon,QPixmap,QImage,QLinearGradient,QFont,QPalette,QFontMetricsF,QTextTable,QTextLength)
from PySide6.QtWidgets import QWidget,QCheckBox,QLabel,QTextBrowser
from .desktop_theme import colors
from .i18n import tr,event_text,event_type,DEBUG_EVENTS,VISIBLE_EVENTS,LANGUAGES


def icon(name,color,size=20):
    """Draw deterministic SVG-style line icons, independent of desktop icon themes."""
    pix=QPixmap(size*2,size*2);pix.fill(Qt.GlobalColor.transparent);pix.setDevicePixelRatio(2)
    p=QPainter(pix);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.scale(size/24,size/24);p.setPen(QPen(QColor(color),1.7,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin));p.setBrush(Qt.BrushStyle.NoBrush)
    path=QPainterPath()
    if name=='sun':
        p.drawEllipse(QPointF(12,12),4,4)
        for i in range(8):
            a=i*pi/4;p.drawLine(QPointF(12+7*cos(a),12+7*sin(a)),QPointF(12+9.5*cos(a),12+9.5*sin(a)))
    elif name=='moon':
        path.moveTo(19,16);path.cubicTo(6,20,3,6,11,3);path.cubicTo(0,4,0,20,12,21);path.cubicTo(15,21,18,19,19,16);p.drawPath(path)
    elif name=='play':
        path.moveTo(8,4);path.lineTo(20,12);path.lineTo(8,20);path.closeSubpath();p.drawPath(path)
    elif name=='pause':p.drawRoundedRect(QRectF(6,4,4,16),1,1);p.drawRoundedRect(QRectF(14,4,4,16),1,1)
    elif name=='stop':p.drawRoundedRect(QRectF(5,5,14,14),2,2)
    elif name=='refresh':
        p.drawArc(QRectF(4,4,16,16),40*16,285*16);path.moveTo(20,3);path.lineTo(20,9);path.lineTo(14,9);p.drawPath(path)
    elif name=='phone':p.drawRoundedRect(QRectF(6,2,12,20),2,2);p.drawLine(10,5,14,5);p.drawLine(11,19,13,19)
    elif name=='score':
        path.moveTo(12,2);path.lineTo(15,8);path.lineTo(22,9);path.lineTo(17,14);path.lineTo(18,21);path.lineTo(12,18);path.lineTo(6,21);path.lineTo(7,14);path.lineTo(2,9);path.lineTo(9,8);path.closeSubpath();p.drawPath(path)
    elif name=='best':p.drawRoundedRect(QRectF(7,3,10,11),2,2);p.drawArc(QRectF(2,4,8,8),90*16,180*16);p.drawArc(QRectF(14,4,8,8),270*16,180*16);p.drawLine(12,14,12,20);p.drawLine(7,21,17,21)
    elif name=='moves':
        for x,y in ((4,4),(13,4),(4,13)):p.drawRoundedRect(QRectF(x,y,7,7),1.5,1.5)
    elif name=='lines':
        for y in (6,12,18):p.drawLine(4,y,20,y)
    elif name=='search':p.drawEllipse(QRectF(3,3,12,12));p.drawLine(14,14,21,21)
    elif name=='check':path.moveTo(5,12);path.lineTo(10,17);path.lineTo(20,6);p.drawPath(path)
    p.end();return QIcon(pix)

class CircularReveal(QWidget):
    """Keep the old DPR-aware window snapshot outside an expanding circular hole."""
    def __init__(self,window,snapshot,center,finished):
        super().__init__(window);self.setGeometry(window.rect());self.snapshot=snapshot;self.center=QPointF(center);self.radius=0
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground);self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.animation=QVariantAnimation(self);self.animation.setDuration(460);self.animation.setStartValue(0.0)
        self.max_radius=max(hypot(center.x()-x,center.y()-y) for x,y in ((0,0),(window.width(),0),(0,window.height()),(window.width(),window.height())))+2
        self.animation.setEndValue(self.max_radius);self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.advance);self.animation.finished.connect(finished)
        self.show();self.raise_()
    def advance(self,value):self.radius=float(value);self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path=QPainterPath();path.addRect(QRectF(self.rect()));hole=QPainterPath();hole.addEllipse(self.center,self.radius,self.radius)
        p.setClipPath(path.subtracted(hole));p.drawPixmap(0,0,self.snapshot)
    def resizeEvent(self,event):
        # A resize during the transition must not leave frozen regions behind.
        if hasattr(self,'animation') and self.size()!=self.snapshot.deviceIndependentSize().toSize():self.animation.setCurrentTime(self.animation.duration())

class Switch(QCheckBox):
    def __init__(self):
        super().__init__();self.position=0.;self.setFixedSize(48,28);self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.animation=QVariantAnimation(self);self.animation.setDuration(150);self.animation.setEasingCurve(QEasingCurve.Type.OutCubic);self.animation.valueChanged.connect(self.advance);self.toggled.connect(self.animate_checked)
    def sizeHint(self):return QSize(48,28)
    def hitButton(self,pos):return self.rect().contains(pos)
    def animate_checked(self,checked):
        self.animation.stop();self.animation.setStartValue(self.position);self.animation.setEndValue(1. if checked else 0.);self.animation.start()
    def advance(self,value):self.position=float(value);self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setOpacity(1 if self.isEnabled() else .45)
        palette=self.palette();a=palette.color(QPalette.ColorRole.Mid);b=palette.color(QPalette.ColorRole.Highlight)
        p.setBrush(QColor(*[round(a.getRgb()[i]*(1-self.position)+b.getRgb()[i]*self.position) for i in range(3)]));p.setPen(Qt.PenStyle.NoPen);p.drawRoundedRect(QRectF(1,3,46,22),11,11)
        p.setBrush(QColor('#FFFFFF'));p.drawEllipse(QRectF(4+24*self.position,6,16,16))
        if self.hasFocus():p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(b,1.5));p.drawRoundedRect(QRectF(.8,.8,46.4,26.4),13,13)

class DeviceIndicator(QWidget):
    def __init__(self):
        super().__init__();self.mode='off';self.phase=0.;self.setFixedSize(20,30)
        self.timer=QTimer(self);self.timer.setInterval(50);self.timer.timeout.connect(self.tick)
    def tick(self):self.phase=(self.phase+.06)%(2*pi);self.update()
    def set_mode(self,mode):
        if mode==self.mode:return
        self.mode=mode
        if mode=='busy':self.timer.start()
        else:self.timer.stop()
        self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c=self.palette().color({'off':QPalette.ColorRole.PlaceholderText,'connected':QPalette.ColorRole.Highlight,'busy':QPalette.ColorRole.Link,'error':QPalette.ColorRole.BrightText}[self.mode])
        if self.mode=='connected':c=QColor('#36B68B')
        if self.mode=='busy':c=QColor('#DCA73B')
        if self.mode=='error':c=QColor('#E6657C')
        for radius,alpha in ((9,15),(7,30),(5,55)):
            glow=QColor(c);glow.setAlpha(round(alpha*(.7+.3*sin(self.phase)) if self.mode=='busy' else alpha));p.setBrush(glow);p.setPen(Qt.PenStyle.NoPen);p.drawEllipse(QPointF(10,15),radius,radius)
        p.setBrush(c);p.drawEllipse(QPointF(10,15),3.5,3.5)

class BoardView(QWidget):
    def __init__(self):
        super().__init__();self.board=0;self.target=0;self.previous=0;self.phase=1.;self.setMinimumSize(210,210)
        self.animation=QVariantAnimation(self);self.animation.setDuration(180);self.animation.setStartValue(0.);self.animation.setEndValue(1.);self.animation.valueChanged.connect(self.animate)
    def animate(self,value):self.phase=float(value);self.update()
    def set_board(self,board,target=None):
        changed=board!=self.board
        if changed:
            self.previous=self.board;self.board=board;self.animation.start()
        target=target or 0
        if changed or target!=self.target:
            self.target=target;self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);n=min(self.width(),self.height())-8;step=n/8;x=(self.width()-n)/2;y=(self.height()-n)/2
        low=self.palette().color(QPalette.ColorRole.AlternateBase);accent=self.palette().color(QPalette.ColorRole.Highlight)
        for i in range(64):
            amount=bool(self.previous>>i&1)*(1-self.phase)+bool(self.board>>i&1)*self.phase
            c=QColor(*[round(low.getRgb()[j]*(1-amount)+accent.getRgb()[j]*amount) for j in range(3)])
            rect=QRectF(x+i%8*step+2,y+i//8*step+2,step-4,step-4)
            grad=QLinearGradient(rect.topLeft(),rect.bottomRight());grad.setColorAt(0,c.lighter(116) if amount else c);grad.setColorAt(1,c.darker(112) if amount else c)
            p.setBrush(grad);p.setPen(QPen(self.palette().color(QPalette.ColorRole.Mid),.8));p.drawRoundedRect(rect,4,4)
            if self.target>>i&1:
                ghost=QColor(accent);ghost.setAlpha(65);p.setBrush(ghost);p.setPen(QPen(accent.lighter(130),1.8,Qt.PenStyle.DashLine));p.drawRoundedRect(rect.adjusted(1,1,-1,-1),4,4)

class PieceQueue(QWidget):
    def __init__(self):super().__init__();self.pieces={};self.setFixedHeight(62)
    def set_pieces(self,pieces):
        if pieces!=self.pieces:self.pieces=dict(pieces);self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);w=min(86,(self.width()-24)/3);start=(self.width()-(w*3+16))/2
        for slot in range(3):
            rect=QRectF(start+slot*(w+8),1,w,58);p.setBrush(self.palette().color(QPalette.ColorRole.Base));p.setPen(self.palette().color(QPalette.ColorRole.Mid));p.drawRoundedRect(rect,8,8)
            shape=self.pieces.get(slot,self.pieces.get(str(slot),()))
            if not shape:continue
            cols=max(c for r,c in shape)+1;rows=max(r for r,c in shape)+1;cell=min(10,40/max(cols,rows));x=rect.center().x()-cols*cell/2;y=rect.center().y()-rows*cell/2
            p.setBrush(self.palette().color(QPalette.ColorRole.Highlight));p.setPen(Qt.PenStyle.NoPen)
            for r,c in shape:p.drawRoundedRect(QRectF(x+c*cell+.6,y+r*cell+.6,cell-1.2,cell-1.2),1.8,1.8)

class PhoneView(QWidget):
    def __init__(self):
        super().__init__()
        self.image=None
        self._pixmap=None
        self._scaled_pixmap=None
        self._scaled_size=None
        self.connected=False
        self.lang='ru'
        self.setMinimumSize(200,320)
    def clear_image(self):
        self.image=None
        self._pixmap=None
        self._scaled_pixmap=None
        self._scaled_size=None
        self.update()
    def set_image(self,image):
        if image is None:
            self.clear_image()
            return
        from PIL import Image
        target_w=360
        target_h=round(image.height*target_w/image.width)
        small=image.resize((target_w,target_h),Image.Resampling.BILINEAR).convert('RGB')
        qimg=QImage(small.tobytes(),small.width,small.height,small.width*3,QImage.Format.Format_RGB888).copy()
        self.image=qimg
        self._pixmap=QPixmap.fromImage(qimg)
        self._scaled_pixmap=None
        self.update()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        self._scaled_pixmap=None
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._pixmap is not None:
            sz=self.size()
            if self._scaled_pixmap is None or self._scaled_size!=sz:
                self._scaled_size=sz
                self._scaled_pixmap=self._pixmap.scaled(sz,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((self.width()-self._scaled_pixmap.width())//2,(self.height()-self._scaled_pixmap.height())//2,self._scaled_pixmap)
            return
        c=self.palette().color(QPalette.ColorRole.PlaceholderText);pix=icon('phone',c.name(),42).pixmap(42,42);y=self.height()/2-62;p.drawPixmap(round((self.width()-42)/2),round(y),pix)
        p.setPen(self.palette().color(QPalette.ColorRole.Text));p.drawText(QRectF(5,y+58,self.width()-10,26),Qt.AlignmentFlag.AlignCenter,tr('phone_ready' if self.connected else 'no_phone',self.lang))
        p.setPen(c);p.drawText(QRectF(14,y+90,self.width()-28,65),Qt.AlignmentFlag.AlignHCenter|Qt.TextFlag.TextWordWrap,tr('preview_hint' if self.connected else 'connect_hint',self.lang))

class EventView(QTextBrowser):
    """Retain semantic records so old visible entries translate and recolor live."""
    recordsChanged=Signal(int)
    def __init__(self,limit=None):
        super().__init__();self.entries=deque(maxlen=limit);self.lang='ru';self.theme='dark';self.query='';self.debug=False;self.follow=True;self.setOpenExternalLinks(False)
        self.setObjectName('eventsView')
        self.setMinimumHeight(60);self.counts=(0,0)
        # Event batches arrive per move.  Rebuilding the rich-text table for
        # every single record is unnecessary; coalesce them into a few renders
        # per second.
        self._timer=QTimer(self);self._timer.setSingleShot(True);self._timer.setInterval(80);self._timer.timeout.connect(self.render)
    def clear(self):
        self._timer.stop();self.entries.clear();self.render();self.recordsChanged.emit(0)
    def append_record(self,record):
        self.entries.append(record)
        self.recordsChanged.emit(len(self.entries))
        if not self._timer.isActive():
            self._timer.start()
    def set_records(self,entries):
        self._timer.stop();self.entries=deque(entries,maxlen=self.entries.maxlen);self.render();self.recordsChanged.emit(len(self.entries))
    def visible(self):
        for e in self.entries:
            if e.get('event') not in VISIBLE_EVENTS|{'message'}:continue
            if e.get('event') in DEBUG_EVENTS and not self.debug:continue
            text=event_text(e,self.lang)
            if text:yield e,text
    def render(self):
        bar=self.verticalScrollBar();old=bar.value();at_end=bar.value()>=bar.maximum()-8
        c=colors(self.theme);parts=[];total=0;shown=0;query=self.query.casefold()
        font=QFont(self.font());font.setPixelSize(11);metrics=QFontMetricsF(font)
        self.badge_width=max(106,ceil(max(metrics.horizontalAdvance('● '+tr('event_'+kind,lang)) for lang in LANGUAGES for kind in ('move','attempt','pause','error','rejected','info','debug')))+26)
        for e,text in self.visible():
            total+=1
            if query and query not in text.casefold():continue
            shown+=1;kind=event_type(e);tint={'move':c['green'],'attempt':c['accent'],'pause':c['yellow'],'error':c['danger'],'rejected':c['danger']}.get(kind,c['muted'])
            stamp=e.get('time','')
            try:stamp=datetime.fromisoformat(stamp).strftime('%H:%M:%S')
            except ValueError:stamp='—'
            stripe=c['card'] if shown%2 else c['field']
            parts.append(f'<tr bgcolor="{stripe}"><td width="74" style="color:{c["muted"]};font-family:monospace;white-space:nowrap">{escape(stamp)}</td><td width="{self.badge_width}" style="color:{tint};font-size:11px;white-space:nowrap">●&nbsp;{escape(tr("event_"+kind,self.lang))}</td><td style="color:{c["text"]}">{escape(text)}</td></tr>')
        self.counts=(shown,total)
        if parts:
            self.setHtml(f'<table width="100%" cellspacing="0" cellpadding="7">'+''.join(parts)+'</table>')
            # Qt rich text may shrink HTML widths. Fix the two metadata columns
            # and prohibit line breaks in the badge at the document-layout level.
            table=next(frame for frame in self.document().rootFrame().childFrames() if isinstance(frame,QTextTable))
            fmt=table.format();fmt.setColumnWidthConstraints([QTextLength(QTextLength.Type.FixedLength,78),QTextLength(QTextLength.Type.FixedLength,self.badge_width),QTextLength(QTextLength.Type.VariableLength,0)]);table.setFormat(fmt)
            for row in range(table.rows()):
                cursor=table.cellAt(row,1).firstCursorPosition();block=cursor.blockFormat();block.setNonBreakableLines(True);cursor.setBlockFormat(block)
        else:self.setHtml(f'<p style="color:{c["muted"]};padding:12px">{escape(tr("empty_events",self.lang))}</p>')
        if self.follow and at_end:bar.setValue(bar.maximum())
        else:bar.setValue(old)

"""Portable Qt desktop with reactive localization and animated appearance."""
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime,timedelta
from PySide6.QtCore import Qt,QTimer,QVariantAnimation,QEasingCurve,QSize,QTranslator
from PySide6.QtGui import QAction,QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QLabel,QPushButton,
 QVBoxLayout,QHBoxLayout,QGridLayout,QSplitter,QTabWidget,QComboBox,QScrollArea,
 QCheckBox,QSpinBox,QDoubleSpinBox,QLineEdit,QGroupBox,QListWidget,QListWidgetItem,
 QFrame,QGraphicsOpacityEffect,QStackedWidget,QGraphicsDropShadowEffect,QFileDialog)
from .config import ROOT,load,save,validate,DEFAULTS
from .runtime import configure_portable
from .desktop_backend import BotWorker,Discovery
from .profile import load_profile
from .history import records,duration,date
from .i18n import tr,reason,LANGUAGES
from .desktop_theme import apply,colors
from .desktop_widgets import BoardView,PhoneView,PieceQueue,Switch,CircularReveal,DeviceIndicator,EventView,icon

NAME='BlockBlast BOT'

class Window(QMainWindow):
    def __init__(self,discover=True):
        super().__init__();self.setWindowTitle(NAME);self.resize(1180,940);self.setMinimumSize(1000,820)
        self.worker=None;self.discovery=None;self.closing=False;self.session_active=False;self.stopping=False
        self.settings_dirty=False;self.last_preview=None;self.preview_at=0.0;self.settings=load();self.lang=self.settings['language'];self.theme=self.settings['theme'];self.bindings=[];self.reveal=None;self.shadow_cards=[]
        self.status_key='ready';self.status_reason='';self.stats_data={};self.device_error='';self.connected_serials=set();self.profile_valid=True;self.setting_rows={};self.row_effects={};self.history_data=[];self.selected_history=None;self.history_events=[]
        self.setWindowIcon(icon('moves',colors(self.theme)['accent']))
        self.start_action=QAction(self);self.start_action.triggered.connect(self.start_bot)
        self.pause_action=QAction(self);self.pause_action.triggered.connect(self.toggle_pause)
        self.stop_action=QAction(self);self.stop_action.triggered.connect(self.stop_bot)
        self.devices=QComboBox();self.devices.setMinimumWidth(220);self.devices.addItem('',None)
        self.devices.currentIndexChanged.connect(self.update_device_state)
        surface=QWidget();surface.setObjectName('surface');self.setCentralWidget(surface)
        outer=QVBoxLayout(surface);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        header=QFrame();header.setObjectName('header');bar=QHBoxLayout(header);bar.setContentsMargins(22,14,22,14);bar.setSpacing(8)
        brand=QVBoxLayout();brand.setSpacing(3);name=QLabel(NAME);name.setObjectName('brand');mode=self.bind(QLabel(),'screen_mode');mode.setObjectName('muted');brand.addWidget(name);brand.addWidget(mode);bar.addLayout(brand);bar.addStretch()
        self.navigation=[]
        for index,key in enumerate(('game','settings','history')):
            button=QPushButton();self.bind(button,key);button.setObjectName('navigation');button.setCheckable(True);button.clicked.connect(lambda checked,i=index:self.tabs.setCurrentIndex(i));bar.addWidget(button);self.navigation.append(button)
        self.theme_button=QPushButton();self.theme_button.setObjectName('themeButton');self.theme_button.setFixedSize(38,36);self.theme_button.clicked.connect(lambda:self.change_theme('light' if self.theme=='dark' else 'dark',self.theme_button));bar.addSpacing(10);bar.addWidget(self.theme_button)
        outer.addWidget(header);self.tabs=QTabWidget();self.tabs.tabBar().hide();outer.addWidget(self.tabs,1)
        self.build_overview();self.build_settings();self.build_history()
        self.tabs.currentChanged.connect(self.select_navigation)
        self.status=QLabel();self.statusBar().addWidget(self.status,1);self.device_note=QLabel();self.statusBar().addPermanentWidget(self.device_note)
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh_ui);self.timer.start(100)
        self.retranslate();self.apply_theme();self.apply_session_state();self.select_navigation(0);self.load_history()
        self.discovery_timer=QTimer(self);self.discovery_timer.setInterval(3000);self.discovery_timer.timeout.connect(self.discover)
        if discover:self.discovery_timer.start();QTimer.singleShot(100,self.discover)

    def t(self,key,**values):return tr(key,self.lang,**values)
    def bind(self,widget,key,method='setText'):
        self.bindings.append((widget,key,method));text=self.t(key);getattr(widget,method)(text.replace('&','&&') if method=='setTitle' else text);return widget
    def label(self,key,muted=False):
        label=self.bind(QLabel(),key)
        if muted:label.setObjectName('muted')
        return label
    def group(self,key):return self.bind(QGroupBox(),key,'setTitle')
    def button(self,key,callback,object_name=None):
        button=self.bind(QPushButton(),key);button.clicked.connect(callback)
        if object_name:button.setObjectName(object_name)
        return button
    def select_navigation(self,index):
        for i,button in enumerate(self.navigation):button.setChecked(i==index)
        old=getattr(self,'fade',None)
        if old:
            old.stop();old.deleteLater();self.fade=None
        page=self.tabs.widget(index)
        # Qt cannot reliably compose a page opacity effect with disabled-row
        # effects inside scroll areas. Keep the settings page free of nesting.
        if index==1:page.setGraphicsEffect(None);return
        effect=QGraphicsOpacityEffect(page);page.setGraphicsEffect(effect)
        self.fade=QVariantAnimation(self);self.fade.setDuration(180);self.fade.setStartValue(.65);self.fade.setEndValue(1.);self.fade.setEasingCurve(QEasingCurve.Type.OutCubic);self.fade.valueChanged.connect(effect.setOpacity);self.fade.start()
        if index==2:self.load_history()
    def action_button(self,action,object_name=None):
        button=QPushButton();button.setIconSize(QSize(16,16))
        if object_name:button.setObjectName(object_name)
        def sync():button.setText(action.text());button.setIcon(action.icon());button.setEnabled(action.isEnabled());button.setToolTip(action.text())
        action.changed.connect(sync);button.clicked.connect(action.trigger);sync();return button

    def stat_card(self,key):
        card=QFrame();card.setObjectName('statCard');layout=QVBoxLayout(card);layout.setContentsMargins(12,9,12,10);layout.setSpacing(5)
        caption=QHBoxLayout();micro=QLabel();micro.setFixedSize(17,17);self.stat_icons.append((micro,key));caption.addWidget(micro);caption.addWidget(self.label(key,True));caption.addStretch();layout.addLayout(caption)
        value=QLabel('—');value.setObjectName('metric');layout.addWidget(value);return card,value

    def build_overview(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(20,18,20,14);layout.setSpacing(14)
        row=QHBoxLayout();row.setSpacing(9);self.indicator=DeviceIndicator();row.addWidget(self.indicator);row.addWidget(self.devices,1)
        self.refresh_button=self.button('refresh',self.discover);row.addWidget(self.refresh_button)
        row.addWidget(self.action_button(self.start_action,'primary'));row.addWidget(self.action_button(self.pause_action));row.addWidget(self.action_button(self.stop_action,'danger'));layout.addLayout(row)
        split=QSplitter();split.setHandleWidth(14);split.setChildrenCollapsible(False);layout.addWidget(split,1)
        phone_box=self.group('phone');self.shadow_cards.append(phone_box);box=QVBoxLayout(phone_box);box.setContentsMargins(0,0,0,0);self.phone=PhoneView();box.addWidget(self.phone,1);split.addWidget(phone_box)
        right=QWidget();right_layout=QVBoxLayout(right);right_layout.setContentsMargins(0,0,0,0);right_layout.setSpacing(12)
        stats=self.group('current');self.shadow_cards.append(stats);grid=QGridLayout(stats);grid.setContentsMargins(0,0,0,0);grid.setSpacing(8);self.metrics={};self.stat_icons=[]
        for i,key in enumerate(('score','best','moves','lines')):
            card,value=self.stat_card(key);grid.addWidget(card,0,i);self.metrics[key]=value
        right_layout.addWidget(stats)
        board_box=self.group('board');self.shadow_cards.append(board_box);b=QVBoxLayout(board_box);b.setContentsMargins(0,0,0,0);b.setSpacing(6)
        self.board=BoardView();self.bind(self.board,'verified','setToolTip');b.addWidget(self.board,1)
        self.queue=PieceQueue();self.bind(self.queue,'queue','setToolTip');b.addWidget(self.queue)
        line=QHBoxLayout();self.hint=QLabel();self.hint.setObjectName('sessionStatus');self.hint.setWordWrap(True);line.addWidget(self.hint,1)
        self.verified=self.label('verified',True);line.addWidget(self.verified);b.addLayout(line)
        self.tempo=QLabel();self.tempo.setObjectName('muted');b.addWidget(self.tempo);right_layout.addWidget(board_box,1);split.addWidget(right);split.setSizes([320,790])
        events_header=QHBoxLayout();events_header.addWidget(self.label('events'));events_header.addStretch()
        self.debug_toggle=Switch();self.bind(self.debug_toggle,'debug','setAccessibleName');self.bind(self.debug_toggle,'debug','setToolTip');events_header.addWidget(self.label('debug',True));events_header.addWidget(self.debug_toggle)
        events_header.addSpacing(10);self.clear_button=self.button('clear',lambda:self.activity.clear(),'link');self.clear_button.setEnabled(False);events_header.addWidget(self.clear_button);layout.addLayout(events_header)
        self.activity=EventView(limit=300);self.activity.setFixedHeight(140);self.activity.recordsChanged.connect(lambda count:self.clear_button.setEnabled(count>0));layout.addWidget(self.activity)
        self.debug_toggle.toggled.connect(self.set_debug);self.tabs.addTab(page,'')

    def build_settings(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(20,18,20,14);layout.setSpacing(12)
        heading=self.label('settings_title');heading.setObjectName('sectionTitle');layout.addWidget(heading);self.settings_banner=QLabel();self.settings_banner.setObjectName('settingsBanner');self.settings_banner.setWordWrap(True);layout.addWidget(self.settings_banner)
        body=QHBoxLayout();body.setSpacing(14);self.settings_categories=QListWidget();self.settings_categories.setObjectName('settingsCategories');self.settings_categories.setFixedWidth(205);body.addWidget(self.settings_categories)
        self.settings_stack=QStackedWidget();body.addWidget(self.settings_stack,1);layout.addLayout(body,1)
        self.category_keys=['appearance','session','strategy','screen','storage']
        for key in self.category_keys:self.settings_categories.addItem(self.t(key))
        appearance=self.group('appearance');a=QVBoxLayout(appearance);a.setContentsMargins(0,0,0,0);a.setSpacing(12)
        self.language_combo=QComboBox()
        for code,name in LANGUAGES.items():self.language_combo.addItem(name,code)
        self.language_combo.setCurrentIndex(self.language_combo.findData(self.lang));self.language_combo.currentIndexChanged.connect(lambda:self.change_language(self.language_combo.currentData()))
        self.theme_combo=QComboBox();self.theme_combo.addItem('', 'dark');self.theme_combo.addItem('', 'light');self.theme_combo.setCurrentIndex(self.theme_combo.findData(self.theme));self.theme_combo.currentIndexChanged.connect(lambda:self.change_theme(self.theme_combo.currentData(),self.theme_combo))
        a.addWidget(self.setting_row('language',self.language_combo,'language_hint'));a.addWidget(self.setting_row('theme',self.theme_combo));a.addWidget(self.label('appearance_hint',True));a.addStretch();self.settings_stack.addWidget(appearance)
        # Game fields share one disabled parent; appearance remains independently available.
        self.settings_editor=QWidget();editor_layout=QVBoxLayout(self.settings_editor);editor_layout.setContentsMargins(0,0,0,0);self.game_stack=QStackedWidget();editor_layout.addWidget(self.game_stack);self.settings_stack.addWidget(self.settings_editor);self.fields={}
        categories=[('session',['max_moves','auto_pause','read_score','score_every']),('strategy',['beam','max_rejections']),('screen',['capture','stream_width','stream_fps','stable_frames','settle_time','verify_timeout','animation_timeout','profile']),('storage',['console_logs','file_logs','save_screenshots','max_sessions','max_history_mb','max_screenshots','max_log_mb','show_board'])]
        self.category_fields=dict(categories)
        limits={'stream_width':(240,2160),'stream_fps':(2,60),'stable_frames':(2,20),'beam':(1,2000),'max_history_mb':(1,4096),'max_moves':(0,10000000),'max_rejections':(0,100),'max_sessions':(1,1000)}
        hints={'max_moves','auto_pause','read_score','score_every','beam','max_rejections','file_logs','save_screenshots','profile'}
        for category,keys in categories:
            group=self.group(category);rows=QVBoxLayout(group);rows.setContentsMargins(0,0,0,0);rows.setSpacing(10)
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame);inner=QWidget();items=QVBoxLayout(inner);items.setContentsMargins(0,0,6,0);items.setSpacing(10)
            for key in keys:
                value=self.settings[key]
                if type(value) is bool:
                    field=Switch();field.setChecked(value);field.toggled.connect(self.mark_settings_dirty)
                elif key=='capture':
                    field=QComboBox()
                    for data in ('auto','stream','screenshot'):field.addItem(self.t(data),data)
                    field.setCurrentIndex(field.findData(value));field.currentIndexChanged.connect(self.mark_settings_dirty)
                elif type(value) is int:
                    field=QSpinBox();field.setRange(*limits.get(key,(1,1000000)));field.setValue(value);field.valueChanged.connect(self.mark_settings_dirty)
                elif type(value) is float:
                    field=QDoubleSpinBox();field.setDecimals(2);field.setRange(.05 if key=='settle_time' else (1 if key=='animation_timeout' else .2),5 if key=='settle_time' else 120);field.setSingleStep(.05 if key=='settle_time' else .5);field.setValue(value);field.valueChanged.connect(self.mark_settings_dirty)
                else:field=QLineEdit(value);field.textChanged.connect(self.mark_settings_dirty)
                items.addWidget(self.setting_row(key,field,'hint_'+key if key in hints else None));self.fields[key]=field
            items.addStretch();scroll.setWidget(inner);rows.addWidget(scroll);self.game_stack.addWidget(group)
        self.settings_categories.currentRowChanged.connect(self.select_category);self.settings_categories.setCurrentRow(0)
        footer=QFrame();footer.setObjectName('settingsFooter');foot=QHBoxLayout(footer);foot.setContentsMargins(14,10,12,10);foot.setSpacing(9)
        self.save_note=QLabel();self.save_note.setObjectName('muted');self.save_note.setWordWrap(True);foot.addWidget(self.save_note,1)
        self.reset_button=self.button('reset',self.reset_settings);self.bind(self.reset_button,'reset_category','setToolTip');foot.addWidget(self.reset_button)
        self.save_button=self.button('save',self.save_settings,'primary');foot.addWidget(self.save_button);layout.addWidget(footer);self.tabs.addTab(page,'')
    def setting_row(self,key,field,hint=None):
        row=QWidget();row.setObjectName('settingRow');line=QHBoxLayout(row);line.setContentsMargins(14,12,14,12);line.setSpacing(16)
        text=QVBoxLayout();text.setSpacing(4);title=self.label(key);title.setWordWrap(True);text.addWidget(title)
        if hint:
            note=self.label(hint,True);note.setWordWrap(True);text.addWidget(note);self.bind(field,hint,'setToolTip')
        else:self.bind(field,key,'setToolTip')
        self.bind(field,key,'setAccessibleName');line.addLayout(text,1)
        if not isinstance(field,Switch):field.setFixedWidth(220);field.setMinimumHeight(34)
        if key=='profile':
            chooser=QWidget();column=QVBoxLayout(chooser);column.setContentsMargins(0,0,0,0);column.setSpacing(4)
            controls=QHBoxLayout();controls.setSpacing(5);controls.addWidget(field)
            self.profile_browse=QPushButton('…');self.profile_browse.clicked.connect(self.browse_profile);self.profile_browse.setFixedSize(36,36)
            # Keep its visible caption compact; localize its accessible label instead.
            self.bind(self.profile_browse,'browse_profile','setToolTip');self.bind(self.profile_browse,'browse_profile','setAccessibleName');controls.addWidget(self.profile_browse);column.addLayout(controls)
            self.profile_note=QLabel();self.profile_note.setWordWrap(True);column.addWidget(self.profile_note);chooser.setFixedWidth(265);line.addWidget(chooser)
        else:line.addWidget(field)
        if key not in ('language','theme'):
            self.setting_rows[key]=row
        return row
    def select_category(self,index):
        self.settings_stack.setCurrentIndex(0 if index==0 else 1)
        if index>0:self.game_stack.setCurrentIndex(index-1)

    def build_history(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(20,18,20,14);layout.setSpacing(12)
        self.history_notice=QLabel();self.history_notice.setObjectName('muted');layout.addWidget(self.history_notice)
        split=QSplitter();split.setHandleWidth(14);split.setChildrenCollapsible(False);self.history=QListWidget();self.history.setMinimumWidth(265);self.history.setSpacing(4);self.history.currentRowChanged.connect(self.show_history);split.addWidget(self.history)
        right=QWidget();r=QVBoxLayout(right);r.setContentsMargins(0,0,0,0);r.setSpacing(12)
        summary=self.group('session_summary');self.shadow_cards.append(summary);summary_layout=QVBoxLayout(summary);summary_layout.setContentsMargins(0,0,0,0);summary_layout.setSpacing(10)
        status_row=QHBoxLayout();status_row.addWidget(self.label('status',True));self.history_reason=QLabel();self.history_reason.setObjectName('statusBadge');self.history_reason.setWordWrap(True);status_row.addWidget(self.history_reason,1);summary_layout.addLayout(status_row);grid=QGridLayout();grid.setSpacing(8);self.history_values={}
        for i,key in enumerate(('score','best','moves','lines','attempts','duration','started','ended')):
            card=QFrame();card.setObjectName('statCard');box=QVBoxLayout(card);box.setContentsMargins(10,8,10,8);box.setSpacing(4);box.addWidget(self.label(key,True));value=QLabel('—');value.setWordWrap(True);box.addWidget(value);self.history_values[key]=value;grid.addWidget(card,i//4,i%4)
        summary_layout.addLayout(grid);r.addWidget(summary)
        timeline=self.group('timeline');t=QVBoxLayout(timeline);t.setContentsMargins(0,0,0,0);t.setSpacing(8)
        self.history_search=QLineEdit();self.bind(self.history_search,'history_search','setPlaceholderText');self.history_search.textChanged.connect(self.filter_history);search_row=QHBoxLayout();search_row.addWidget(self.history_search,1);search_row.addWidget(self.label('debug',True));self.history_debug_toggle=Switch();self.bind(self.history_debug_toggle,'debug','setToolTip');self.bind(self.history_debug_toggle,'debug','setAccessibleName');self.history_debug_toggle.toggled.connect(self.set_debug);search_row.addWidget(self.history_debug_toggle);t.addLayout(search_row)
        self.history_detail=EventView();self.history_detail.follow=False;t.addWidget(self.history_detail,1);self.history_count=QLabel();self.history_count.setObjectName('muted');t.addWidget(self.history_count);r.addWidget(timeline,1);split.addWidget(right);split.setSizes([290,820]);layout.addWidget(split,1);self.tabs.addTab(page,'')

    def retranslate(self):
        app=QApplication.instance()
        old=getattr(app,'_blockblast_translator',None)
        if old:app.removeTranslator(old)
        translator=QTranslator(app)
        if self.lang!='en' and translator.load(str(Path(__file__).parent/'translations'/('qtbase_'+self.lang+'.qm'))):app.installTranslator(translator)
        app._blockblast_translator=translator
        if old:old.deleteLater()
        for widget,key,method in self.bindings:
            text=self.t(key);getattr(widget,method)(text.replace('&','&&') if method=='setTitle' else text)
        for i,key in enumerate(('game','settings','history')):self.tabs.setTabText(i,self.t(key))
        self.start_action.setText(self.t('start'));self.stop_action.setText(self.t('stop'));self.pause_action.setText(self.t('resume' if self.worker and self.worker.control.pause_event.is_set() else 'pause'))
        for i,key in enumerate(self.category_keys):self.settings_categories.item(i).setText(self.t(key))
        for i,key in enumerate(('dark','light')):self.theme_combo.setItemText(i,self.t(key))
        for i,key in enumerate(('auto','stream','screenshot')):self.fields['capture'].setItemText(i,self.t(key))
        self.fields['max_moves'].setSpecialValueText(self.t('unlimited'))
        self.phone.lang=self.lang;self.phone.update();self.theme_button.setToolTip(self.t('theme_toggle'));self.theme_button.setAccessibleName(self.t('theme_toggle'))
        for view in (self.activity,self.history_detail):view.lang=self.lang;view.render()
        self.validate_profile();self.update_status();self.update_settings_note();self.update_stats();self.update_device_state();self.render_history_items();self.render_history_summary();self.filter_history()
    def persist_appearance(self,**changes):
        # Persist only appearance over the last saved game settings; never save dirty game fields.
        candidate=validate(self.settings|changes)
        try:save(candidate)
        except OSError:self.save_note.setText(self.t('save_error'));return False
        self.settings=candidate;return True
    def change_language(self,lang):
        if not lang or lang==self.lang:return
        if not self.persist_appearance(language=lang):
            self.language_combo.blockSignals(True);self.language_combo.setCurrentIndex(self.language_combo.findData(self.lang));self.language_combo.blockSignals(False);return
        self.lang=lang;self.language_combo.blockSignals(True);self.language_combo.setCurrentIndex(self.language_combo.findData(lang));self.language_combo.blockSignals(False);self.retranslate()
    def change_theme(self,theme,source=None):
        if not theme or theme==self.theme:return
        if self.reveal:return
        if not self.persist_appearance(theme=theme):
            self.theme_combo.blockSignals(True);self.theme_combo.setCurrentIndex(self.theme_combo.findData(self.theme));self.theme_combo.blockSignals(False);return
        if hasattr(self,'fade'):self.fade.stop();self.tabs.currentWidget().setGraphicsEffect(None)
        snapshot=self.grab() if self.isVisible() else None
        source=source or self.theme_button;center=source.mapTo(self,source.rect().center());self.theme=theme
        self.theme_combo.blockSignals(True);self.theme_combo.setCurrentIndex(self.theme_combo.findData(theme));self.theme_combo.blockSignals(False)
        self.apply_theme()
        if snapshot:
            self.theme_button.setEnabled(False);self.theme_combo.setEnabled(False)
            self.reveal=CircularReveal(self,snapshot,center,self.finish_reveal);self.reveal.animation.start()
    def finish_reveal(self):
        overlay=self.reveal;self.reveal=None
        if overlay:overlay.hide();overlay.deleteLater()
        self.theme_button.setEnabled(True);self.theme_combo.setEnabled(True)
    def apply_theme(self):
        apply(QApplication.instance(),self.theme);c=colors(self.theme)
        self.theme_button.setIcon(icon('sun' if self.theme=='dark' else 'moon',c['text']))
        self.refresh_button.setIcon(icon('refresh',c['muted']))
        self.start_action.setIcon(icon('play','#FFFFFF'));self.pause_action.setIcon(icon('play' if self.worker and self.worker.control.pause_event.is_set() else 'pause',c['text']));self.stop_action.setIcon(icon('stop',c['danger']))
        for widget,key in self.stat_icons:widget.setPixmap(icon(key,c['accent'],16).pixmap(16,16))
        for view in (self.activity,self.history_detail):view.theme=self.theme;view.render()
        self.phone.update();self.board.update();self.queue.update();self.indicator.update()
        for widget in self.shadow_cards:
            if self.theme=='light':
                shadow=QGraphicsDropShadowEffect(widget);shadow.setBlurRadius(14);shadow.setOffset(0,2);shadow.setColor(QColor(40,65,110,16));widget.setGraphicsEffect(shadow)
            else:widget.setGraphicsEffect(None)

    def field_values(self):
        values={}
        for key,field in self.fields.items():
            if isinstance(field,QCheckBox):value=field.isChecked()
            elif isinstance(field,QComboBox):value=field.currentData()
            elif isinstance(field,(QSpinBox,QDoubleSpinBox)):value=field.value()
            else:value=field.text()
            values[key]=value
        return values
    def validate_profile(self):
        value=self.fields['profile'].text();path=Path(value);path=path if path.is_absolute() else ROOT/path
        try:
            self.profile_valid=path.suffix.lower()=='.json' and path.is_file()
            if self.profile_valid:load_profile(path)
        except (ValueError,OSError):self.profile_valid=False
        field=self.fields['profile'];field.setProperty('invalid',not self.profile_valid);field.style().unpolish(field);field.style().polish(field)
        self.profile_note.setText(self.t('profile_valid' if self.profile_valid else 'profile_invalid'));self.profile_note.setObjectName('profileValid' if self.profile_valid else 'profileInvalid');self.profile_note.style().unpolish(self.profile_note);self.profile_note.style().polish(self.profile_note)
        return self.profile_valid
    def browse_profile(self):
        if self.session_active or self.closing:return
        path,_=QFileDialog.getOpenFileName(self,self.t('browse_profile'),str(ROOT/'profiles'),self.t('json_files'))
        if path:
            selected=Path(path)
            try:value=selected.relative_to(ROOT).as_posix()
            except ValueError:value=str(selected)
            self.fields['profile'].setText(value)
    def update_dependencies(self):
        history=self.fields['file_logs'].isChecked()
        dependencies={'score_every':self.fields['read_score'].isChecked(),'save_screenshots':history,'max_screenshots':history and self.fields['save_screenshots'].isChecked(),'max_sessions':history,'max_history_mb':history,'max_log_mb':history}
        for key,row in self.setting_rows.items():
            enabled=dependencies.get(key,True);row.setEnabled(enabled)
            if enabled:
                if row.graphicsEffect():row.setGraphicsEffect(None)
                self.row_effects.pop(key,None)
            elif not row.graphicsEffect():
                effect=QGraphicsOpacityEffect(row);effect.setOpacity(.45);row.setGraphicsEffect(effect);self.row_effects[key]=effect
    def mark_settings_dirty(self,*args):
        if self.session_active:return
        self.settings_dirty=any(value!=self.settings[key] for key,value in self.field_values().items())
        self.validate_profile();self.update_dependencies();self.apply_session_state()
    def reset_settings(self):
        if self.session_active or self.closing:return
        category=self.category_keys[self.settings_categories.currentRow()]
        if category=='appearance':
            self.change_language(DEFAULTS['language']);self.change_theme(DEFAULTS['theme'],self.reset_button);return
        for key in self.category_fields[category]:
            field=self.fields[key];value=DEFAULTS[key]
            field.blockSignals(True)
            if isinstance(field,QCheckBox):field.setChecked(value)
            elif isinstance(field,QComboBox):field.setCurrentIndex(field.findData(value))
            elif isinstance(field,(QSpinBox,QDoubleSpinBox)):field.setValue(value)
            else:field.setText(value)
            field.blockSignals(False)
            if isinstance(field,Switch):field.animate_checked(value)
        self.mark_settings_dirty()
    def save_settings(self):
        if self.session_active or self.closing:return False
        if not self.validate_profile():self.save_note.setText(self.t('profile_invalid'));return False
        if not self.settings_dirty:return True
        try:
            candidate=validate(self.settings|self.field_values());save(candidate);self.settings=candidate;self.settings_dirty=False;self.apply_session_state();return True
        except (ValueError,OSError):self.save_note.setText(self.t('save_error'));return False
    def update_settings_note(self):
        self.save_note.setText(self.t('unsaved' if self.settings_dirty else 'saved'));self.settings_banner.setText(self.t('locked' if self.session_active else 'settings_hint'))
    def selected_serial(self):
        serial=self.devices.currentData()
        return serial if serial and serial in self.connected_serials else None
    def update_start_state(self):
        scanning=self.discovery is not None and self.discovery.isRunning()
        self.start_action.setEnabled(bool(self.selected_serial()) and not self.session_active and not self.closing and not scanning and self.profile_valid)
    def apply_session_state(self):
        active=self.session_active;available=not active and not self.closing
        self.settings_editor.setEnabled(available);self.save_button.setEnabled(available and self.settings_dirty and self.profile_valid);self.reset_button.setEnabled(available);self.devices.setEnabled(available)
        scanning=self.discovery is not None and self.discovery.isRunning()
        self.refresh_button.setEnabled(available and not scanning);self.update_start_state();self.pause_action.setEnabled(active and not self.stopping and not self.closing);self.stop_action.setEnabled(active and not self.stopping)
        self.update_dependencies();self.update_settings_note();self.update_device_state()
    def set_status(self,key=None,raw=''):
        self.status_key=key;self.status_reason=raw;self.update_status()
    def update_status(self):
        idle=not self.session_active and self.status_key in ('ready','connect_hint','waiting_adb','phone_unavailable')
        if idle:
            text=self.t('ready' if self.selected_serial() else 'waiting_adb')
        else:
            text=self.t(self.status_key) if self.status_key else reason(self.status_reason,self.lang)
        self.status.setText(text);self.hint.setText(text if self.session_active else self.t('waiting_start'))
        state=getattr(getattr(self.worker,'control',None),'status','idle') if self.session_active else 'idle'
        if self.hint.property('state')!=state:
            self.hint.setProperty('state',state);self.hint.style().unpolish(self.hint);self.hint.style().polish(self.hint)
    def update_stats(self):
        for key,widget in self.metrics.items():
            value=self.stats_data.get(key);widget.setText(f'{value:,}'.replace(',',' ') if value is not None else '—')
        self.tempo.setText(self.t('tempo',rate=self.stats_data.get('moves_per_minute',0),attempts=self.stats_data.get('attempts',0),rejected=self.stats_data.get('rejected',0)))
    def update_device_state(self,*args):
        if not hasattr(self,'phone') or not hasattr(self,'device_note'):return
        connected=bool(self.selected_serial());self.phone.connected=connected;self.phone.update()
        scanning=self.discovery is not None and self.discovery.isRunning()
        if self.session_active or scanning:mode='busy';key='scanning' if scanning else ('pause' if self.worker and self.worker.control.status=='paused' else 'working')
        elif connected:mode='connected';key='phone_ready'
        else:mode='error' if self.device_error else 'off';key='no_phone'
        self.indicator.set_mode(mode);self.indicator.setToolTip(self.t(key));self.device_note.setText(self.t('devices',count=len(self.connected_serials)))
        if self.devices.currentData() is None and self.devices.count()==1:self.devices.setItemText(0,self.t('no_phone'))
        self.phone.setToolTip(self.t('live' if self.session_active else 'last_frame') if self.phone.image is not None else self.t('phone_ready' if connected else 'no_phone'))
        self.update_start_state();self.update_status()
    def discover(self):
        if self.session_active or self.closing or (self.discovery and self.discovery.isRunning()):return
        worker=Discovery();self.discovery=worker
        worker.result.connect(lambda devices,error,w=worker:self.discovered(devices,error) if self.discovery is w and not self.session_active and not self.closing else None)
        worker.finished.connect(self.apply_session_state);worker.start();self.apply_session_state()
    def discovered(self,devices,error):
        if self.session_active or self.closing:return
        previous=self.devices.currentData();self.connected_serials={serial for serial,model in devices};self.devices.blockSignals(True);self.devices.clear();self.device_error=error
        for serial,model in devices:self.devices.addItem(f'{model} · {serial}',serial)
        if not devices:self.devices.addItem(self.t('no_phone'),None)
        elif previous and self.devices.findData(previous)>=0:self.devices.setCurrentIndex(self.devices.findData(previous))
        self.devices.blockSignals(False);self.update_device_state()
    def start_bot(self):
        if self.session_active or self.closing or (self.discovery and self.discovery.isRunning()):return
        serial=self.selected_serial()
        if not serial:self.set_status('waiting_adb');return
        if not self.validate_profile():self.apply_session_state();self.set_status('profile_error');return
        if self.settings_dirty and not self.save_settings():self.set_status('settings_error');return
        try:
            settings=validate(dict(self.settings));settings['save_screenshots']=settings['file_logs'] and settings['save_screenshots'];profile=Path(settings['profile']);profile=profile if profile.is_absolute() else ROOT/profile;load_profile(profile)
        except (ValueError,OSError):self.set_status('profile_error');return
        self.session_active=True;self.stopping=False;self.activity.clear();self.last_preview=None
        worker=BotWorker(serial,settings);self.worker=worker
        worker.event.connect(lambda kind,data,w=worker:self.bot_event(kind,data) if self.worker is w else None);worker.finished.connect(lambda w=worker:self.bot_finished() if self.worker is w else None)
        self.stats_data={'moves':0,'lines':0};self.update_stats();self.board.set_board(0);self.queue.set_pieces({});self.phone.clear_image();self.set_status('connecting');self.apply_session_state()
        try:worker.start()
        except Exception as exc:self.session_active=False;self.worker=None;self.apply_session_state();self.set_status(raw=str(exc))
    def toggle_pause(self):
        if not self.session_active or self.stopping or self.closing or not self.worker:return
        event=self.worker.control.pause_event
        if event.is_set():event.clear()
        else:event.set()
        self.pause_action.setText(self.t('resume' if event.is_set() else 'pause'));self.pause_action.setIcon(icon('play' if event.is_set() else 'pause',colors(self.theme)['text']))
    def stop_bot(self):
        if not self.session_active or not self.worker or self.stopping:return
        self.stopping=True;self.worker.control.stop_event.set();self.set_status('stopping');self.apply_session_state()
    def bot_event(self,kind,data):
        if kind=='activity' and (self.settings['console_logs'] or data['record']['event']=='storage_warning'):self.activity.append_record(data['record'])
        elif kind=='log' and self.settings['console_logs']:
            key=data.get('message')
            if key in ('auto_pace','ocr_unavailable','capture_started','retry_pause','check_pause','retry_other','retry_adjust','gesture_cancelled','capture_fallback'):
                self.activity.append_record({'time':datetime.now().isoformat(),'event':'message','key':key,'params':data.get('params',{})})
        elif kind=='status':
            if self.stopping:return
            if data.get('reason'):self.set_status(raw=data['reason'])
            else:self.set_status({'running':'working','paused':'pause','connecting':'connecting','finished':'finished','error':'error_generic'}.get(data.get('status'),'ready'))
            if data['status']=='paused' and self.worker and self.worker.control.pause_event.is_set():self.pause_action.setText(self.t('resume'))
            self.update_device_state()
        elif kind=='stats':self.stats_data=dict(data);self.update_stats()
    def refresh_ui(self):
        if self.worker:
            c=self.worker.control;frame=c.preview()
            # The live view is a preview, not a second full-rate consumer of the
            # stream.  Re-scaling every decoded frame in the GUI thread made the
            # interface progressively less responsive.
            now=time.monotonic()
            if frame is not None and frame is not self.last_preview and now-self.preview_at>=.12:
                self.phone.set_image(frame);self.last_preview=frame;self.preview_at=now
            if c.board is not None:self.board.set_board(c.board,c.target)
            self.queue.set_pieces(c.pieces)
    def bot_finished(self):
        self.session_active=False;self.stopping=False;self.pause_action.setText(self.t('pause'));self.apply_session_state();self.load_history()
        if self.worker:self.set_status(raw=self.worker.control.reason)
        if self.closing:self.close()
        elif self.discovery_timer.isActive():self.discover()
    def set_debug(self,checked):
        for toggle in (self.debug_toggle,self.history_debug_toggle):
            if toggle.isChecked()!=checked:
                toggle.blockSignals(True);toggle.setChecked(checked);toggle.blockSignals(False);toggle.animate_checked(checked)
        for view in (self.activity,self.history_detail):view.debug=checked;view.render()
        self.filter_history()

    def load_history(self):
        selected=self.selected_history;self.history_data=[]
        for path in sorted((ROOT/'logs').glob('run-*/summary.json'),reverse=True):
            try:
                data=json.loads(path.read_text(encoding='utf-8'));data['_folder']=path.parent
                if not data.get('started_at'):
                    try:data['started_at']=datetime.strptime(path.parent.name[4:],'%Y%m%d-%H%M%S-%f').isoformat()
                    except ValueError:pass
                self.history_data.append(data)
            except (ValueError,OSError):pass
        self.render_history_items();index=next((i for i,d in enumerate(self.history_data) if d['_folder']==selected),0)
        if self.history_data:
            self.history.blockSignals(True);self.history.setCurrentRow(index);self.history.blockSignals(False);self.show_history(index)
        else:
            self.selected_history=None;self.history_events=[];self.history_detail.set_records([]);self.render_history_summary();self.filter_history()
    def render_history_items(self):
        if not hasattr(self,'history'):return
        index=self.history.currentRow();self.history.blockSignals(True);self.history.clear()
        for data in self.history_data:
            score=data.get('score');score='—' if score is None else f'{score:,}'.replace(',',' ')
            item=QListWidgetItem(f'{self.display_date(data.get("started_at"))}\n'+self.t('history_item',score=score,moves=data.get('moves',0),duration=duration(data.get('seconds'))));self.history.addItem(item)
        if 0<=index<len(self.history_data):self.history.setCurrentRow(index)
        self.history.blockSignals(False)
        self.history_notice.setText(self.t('history_count',count=len(self.history_data),limit=self.settings['max_sessions'],mb=self.settings['max_history_mb']))
    def display_date(self,value):
        formatted=date(value)
        return self.t('unknown') if formatted=='Не записано' else formatted
    def show_history(self,index):
        if not 0<=index<len(self.history_data):return
        data=self.history_data[index];folder=data['_folder'];self.selected_history=folder;self.history_events=list(records(folder))
        if not self.history_events:
            from .i18n import legacy_action
            self.history_events=[legacy_action(text) for text in data.get('last_actions',[])]
        if not data.get('ended_at'):
            last=next((e.get('time') for e in reversed(self.history_events) if e.get('event')=='summary'),None)
            if last:data['ended_at']=last
            elif data.get('started_at'):
                try:data['ended_at']=(datetime.fromisoformat(data['started_at'])+timedelta(seconds=data.get('seconds',0))).isoformat()
                except (ValueError,TypeError):pass
        self.history_detail.set_records(self.history_events);self.render_history_summary();self.filter_history()
    def render_history_summary(self):
        index=self.history.currentRow();data=self.history_data[index] if 0<=index<len(self.history_data) else None
        self.history_reason.setText(reason(data.get('reason',''),self.lang) if data else self.t('no_history'))
        self.history_reason.setProperty('severity','error' if data and data.get('reason','').startswith('Ошибка') else 'normal')
        self.history_reason.style().unpolish(self.history_reason);self.history_reason.style().polish(self.history_reason)
        for key,value in self.history_values.items():
            raw=data.get(key) if data else None
            if key in ('started','ended'):text=self.display_date(data.get(key+'_at')) if data else '—'
            elif key=='duration':text=duration(data.get('seconds')) if data else '—'
            else:text=f'{raw:,}'.replace(',',' ') if isinstance(raw,(int,float)) else '—'
            value.setText(text)
    def filter_history(self,*args):
        self.history_detail.query=self.history_search.text();self.history_detail.render();shown,total=self.history_detail.counts;notice=self.t('filtered',shown=shown,total=total)
        if self.selected_history and not (self.selected_history/'timeline.jsonl.gz').exists():notice+=' · '+self.t('archive_old')
        self.history_count.setText(notice)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.reveal:self.reveal.setGeometry(self.rect())
    def closeEvent(self,event):
        self.discovery_timer.stop()
        if self.reveal:self.reveal.animation.stop();self.finish_reveal()
        if self.session_active:self.closing=True;self.stop_bot();self.apply_session_state();event.ignore()
        else:
            if self.discovery and self.discovery.isRunning():self.discovery.wait(9000)
            event.accept()

def main():
    configure_portable()
    app=QApplication(sys.argv)
    app.setStyle('Fusion')
    apply(app,load()['theme']);app.setApplicationName(NAME);app.setOrganizationName(NAME)
    if '--packaging-test' in sys.argv:
        from .bundlecheck import run
        return run(app,Window,Path(sys.argv[sys.argv.index('--packaging-test')+1]))
    if '--self-test' in sys.argv:
        from .adb import ADB
        from .capture import VideoCapture
        from .score import ScoreReader
        from .vision import read
        import shutil
        report={'root':str(ROOT),'tools':{name:shutil.which(name) for name in ('adb','ffmpeg','tesseract')}}
        report_path=Path(sys.argv[sys.argv.index('--self-test')+1])
        adb=ADB();image=adb.screenshot();profile=load_profile(ROOT/'profiles/default.json')
        try:
            state=read(image,profile)
        except (ValueError,OSError) as exc:
            # A menu, ad or animation is not a packaging failure.  Keep the
            # frame next to the report so the state can be inspected.
            report['error']=str(exc);image.save(report_path.with_suffix('.png'))
            report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return 1
        reader=ScoreReader()
        report.update(serial=adb.serial,score=reader.read(image,state.bounds,profile),ocr=reader.available);stream=VideoCapture(adb,image.size)
        try:
            frame=stream.get(timeout=10)
            try:
                report['stream_board_matches']=read(frame,profile).board==state.board
            except ValueError as exc:
                # The first decoded frame may still be a menu/palette
                # transition; the live bot waits for a stable frame instead.
                report['stream_board_matches']=None;report['stream_error']=str(exc)
                frame.save(report_path.with_suffix('.stream.png'))
        finally:stream.close()
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return 0
    smoke='--smoke-test' in sys.argv;window=Window(discover=not smoke);window.show()
    if smoke:
        path=Path(sys.argv[sys.argv.index('--smoke-test')+1]);QTimer.singleShot(700,lambda:(window.grab().save(str(path)),window.close()))
    return app.exec()

if __name__=='__main__':sys.exit(main())

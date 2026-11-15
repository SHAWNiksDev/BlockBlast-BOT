"""Behavioral UI regressions: live locale/theme changes and retained history."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from string import Formatter
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from blockblast.config import DEFAULTS,validate,save,load
from blockblast.i18n import CATALOGS,ROWS,tr,event_text,legacy_action
from blockblast.desktop import Window
from blockblast.desktop_widgets import Switch
from blockblast.session import Session,Stats
from test_desktop_states import Worker

class LocalizationTests(unittest.TestCase):
    def test_every_locale_has_matching_keys_and_format_parameters(self):
        self.assertEqual(len(ROWS),len(CATALOGS['ru']))
        formatter=Formatter()
        for key in CATALOGS['ru']:
            expected={field for _,field,_,_ in formatter.parse(CATALOGS['ru'][key]) if field}
            for locale in CATALOGS:
                self.assertEqual(expected,{field for _,field,_,_ in formatter.parse(CATALOGS[locale][key]) if field},(key,locale))
    def test_structured_history_has_no_raw_system_labels(self):
        events=[dict(event='timing',stage='gesture',seconds=.7),dict(event='resync_after_pause'),dict(event='tray_resync'),dict(event='motion',reason='Положение фигуры проверено по кадру')]
        for language in CATALOGS:
            for event in events:
                text=event_text(event,language);self.assertTrue(text)
                self.assertNotIn('resync_',text);self.assertNotIn('timing',text)
                if language=='en':self.assertFalse(any('\u0400'<=ch<='\u04ff' for ch in text))
    def test_preferences_validate_and_roundtrip(self):
        for values in ({'language':'de'},{'theme':'sepia'}):
            with self.assertRaises(ValueError):validate(values)
        with TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json';save(DEFAULTS|{'language':'uk','theme':'light'},path)
            self.assertEqual(load(path)['language'],'uk');self.assertEqual(load(path)['theme'],'light')
    def test_legacy_summary_is_translatable(self):
        event=legacy_action('Ход 128: Фигура 3 → строка 6, столбец 1; линий 2')
        self.assertIn('Move 128: piece 3',event_text(event,'en'))
    def test_live_structured_events_work_with_disk_logging_disabled(self):
        with TemporaryDirectory() as folder:
            captured=[];session=Session(folder,DEFAULTS|{'file_logs':False},callback=captured.append)
            session.event('move',move=1);session.finish(Stats(),'Завершено')
            self.assertEqual([e['event'] for e in captured],['move','summary'])
            self.assertEqual(list(Path(folder).iterdir()),[])

class RedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.directory=TemporaryDirectory();self.root=Path(self.directory.name);(self.root/'profiles').mkdir();(self.root/'profiles/default.json').write_text('{}')
        self.patches=[patch('blockblast.desktop.ROOT',self.root),patch('blockblast.desktop.load',return_value=dict(DEFAULTS)),patch('blockblast.desktop.save'),patch('blockblast.desktop.BotWorker',side_effect=Worker)]
        self.mocks=[p.start() for p in self.patches];self.window=Window(discover=False);self.window.discovered([('serial','Phone')],'')
    def tearDown(self):
        self.window.session_active=False;self.window.close();self.app.processEvents()
        for p in reversed(self.patches):p.stop()
        self.directory.cleanup()
    def test_locale_retranslates_existing_events_controls_and_status(self):
        w=self.window;w.bot_event('activity',{'record':dict(event='move',move=4,slot=2,row=5,col=0,lines=2)})
        w.set_status(raw='Открыта шторка уведомлений');w.change_language('en')
        self.assertEqual(w.navigation[0].text(),'Game');self.assertEqual(w.status.text(),'Notification shade is open')
        self.assertIn('Move 4: piece 3',w.activity.toPlainText());self.assertEqual(w.language_combo.currentData(),'en')
        w.change_language('uk');self.assertEqual(w.navigation[0].text(),'Гра');self.assertIn('Хід 4',w.activity.toPlainText())
    def test_appearance_remains_available_while_game_settings_are_locked(self):
        w=self.window;w.start_bot();worker=w.worker
        w.change_language('en');w.change_theme('light')
        self.assertFalse(w.settings_editor.isEnabled());self.assertTrue(w.language_combo.isEnabled());self.assertTrue(w.theme_combo.isEnabled())
        self.assertIs(w.worker,worker);self.assertEqual(worker.settings['language'],'ru');self.assertEqual(w.settings['language'],'en')
        self.assertFalse(w.save_settings());self.assertEqual(w.theme,'light')
    def test_appearance_does_not_persist_unsaved_game_fields(self):
        w=self.window;w.fields['max_moves'].setValue(42);w.change_language('uk')
        self.assertEqual(self.mocks[2].call_args.args[0]['max_moves'],0)
        self.assertTrue(w.settings_dirty);w.save_settings();self.assertEqual(self.mocks[2].call_args.args[0]['max_moves'],42)
        self.assertEqual(w.settings['language'],'uk')
    def test_failed_appearance_save_keeps_previous_value(self):
        w=self.window;self.mocks[2].side_effect=OSError('read only')
        w.change_language('en');w.change_theme('light')
        self.assertEqual(w.lang,'ru');self.assertEqual(w.theme,'dark');self.assertEqual(w.language_combo.currentData(),'ru')
    def test_debug_filter_hides_timings_but_translates_when_enabled(self):
        w=self.window;w.bot_event('activity',{'record':dict(event='timing',seconds=.27)});self.assertNotIn('0.27',w.activity.toPlainText())
        w.set_debug(True);w.change_language('en');self.assertIn('Gesture duration: 0.27',w.activity.toPlainText())
    def test_switch_click_and_keyboard_toggle(self):
        switch=self.window.fields['auto_pause'];self.assertIsInstance(switch,Switch)
        switch.show();checked=switch.isChecked();QTest.mouseClick(switch,Qt.MouseButton.LeftButton);self.assertEqual(switch.isChecked(),not checked)
        QTest.keyClick(switch,Qt.Key.Key_Space);self.assertEqual(switch.isChecked(),checked)
        self.assertEqual(switch.text(),'')
    def test_reveal_origin_old_pixels_outside_and_new_pixels_inside(self):
        w=self.window;w.show();QTest.qWait(220);w.tabs.currentWidget().setGraphicsEffect(None);old=w.grab().toImage();center=w.theme_button.mapTo(w,w.theme_button.rect().center())
        w.change_theme('light',w.theme_button);overlay=w.reveal
        self.assertIsNotNone(overlay);self.assertEqual(overlay.center.toPoint(),center);self.assertFalse(w.theme_button.isEnabled())
        overlay.animation.pause();overlay.animation.setCurrentTime(50);self.app.processEvents();during=w.grab().toImage()
        self.assertEqual(during.pixelColor(5,400),old.pixelColor(5,400))
        self.assertNotEqual(during.pixelColor(center+QPoint(0,30)),old.pixelColor(center+QPoint(0,30)))
        overlay.animation.resume();QTest.qWait(550);self.assertIsNone(w.reveal);self.assertTrue(w.theme_button.isEnabled())
        self.assertNotEqual(w.grab().toImage().pixelColor(5,400),old.pixelColor(5,400))
    def test_history_reload_refreshes_same_selected_index_and_empty_counts(self):
        session=Session(self.root,DEFAULTS);session.event('move',move=1);session.finish(Stats(moves=1),'Завершено')
        w=self.window;w.load_history();self.assertEqual(w.history_values['moves'].text(),'1')
        path=session.directory/'summary.json';data=json.loads(path.read_text());data['moves']=8;path.write_text(json.dumps(data))
        w.load_history();self.assertEqual(w.history.currentRow(),0);self.assertEqual(w.history_values['moves'].text(),'8')
        path.unlink();w.load_history();self.assertEqual(w.history_values['moves'].text(),'—');self.assertEqual(w.history_detail.counts,(0,0))
    def test_history_summary_and_search_retranslate_without_losing_selection(self):
        session=Session(self.root,DEFAULTS);session.event('move',move=1,slot=0,row=0,col=0,lines=2);session.event('paused',reason='Открыта шторка уведомлений');session.finish(Stats(score=100,start_score=100,best=120,moves=1),'Достигнут лимит ходов')
        w=self.window;w.load_history();folder=w.selected_history;w.change_language('en');w.history_search.setText('paused')
        self.assertEqual(w.selected_history,folder);self.assertEqual(w.history_values['score'].text(),'100');self.assertEqual(w.history_values['best'].text(),'120');self.assertIn('Move limit reached',w.history_reason.text())
        self.assertIn('Paused: Notification shade',w.history_detail.toPlainText());self.assertNotIn('Move 1',w.history_detail.toPlainText())
        w.change_language('uk');self.assertEqual(w.history_search.text(),'paused');self.assertEqual(w.selected_history,folder)
        w.history_search.clear();self.assertIn('Хід 1',w.history_detail.toPlainText());self.assertEqual(w.history_detail.counts,(3,3))

if __name__=='__main__':unittest.main()

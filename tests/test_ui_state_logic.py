"""UI dependency, device selection and rich-text layout regressions; no real ADB."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextTable,QFontMetricsF
from PySide6.QtTest import QTest
from blockblast.config import DEFAULTS
from blockblast.desktop import Window
from blockblast.desktop_widgets import EventView
from blockblast.desktop_theme import apply
from blockblast.i18n import tr
import test_desktop_states as doubles

class StateLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.directory=TemporaryDirectory();self.root=Path(self.directory.name);(self.root/'profiles').mkdir();(self.root/'profiles/default.json').write_text('{}')
        self.patches=[patch('blockblast.desktop.ROOT',self.root),patch('blockblast.desktop.load',return_value=dict(DEFAULTS)),patch('blockblast.desktop.save'),patch('blockblast.desktop.BotWorker',side_effect=doubles.Worker)]
        self.mocks=[p.start() for p in self.patches];self.window=Window(discover=False)
    def tearDown(self):
        self.window.session_active=False;self.window.close();self.app.processEvents()
        for p in reversed(self.patches):p.stop()
        self.directory.cleanup()
    def connect_phone(self):self.window.discovered([('serial','Phone')],'')
    def test_start_requires_discovered_device_selection_and_idle_state(self):
        w=self.window;self.assertFalse(w.start_action.isEnabled());w.start_bot();self.assertIsNone(w.worker)
        # A nonempty placeholder/foreign serial is not an ADB discovery result.
        w.devices.addItem('Unavailable','stale');w.devices.setCurrentIndex(1);self.assertFalse(w.start_action.isEnabled());w.start_bot();self.assertIsNone(w.worker)
        self.connect_phone();self.assertTrue(w.start_action.isEnabled())
        w.devices.setCurrentIndex(-1);self.assertFalse(w.start_action.isEnabled());w.devices.setCurrentIndex(0);self.assertTrue(w.start_action.isEnabled())
        w.start_bot();self.assertFalse(w.start_action.isEnabled());w.toggle_pause();self.assertFalse(w.start_action.isEnabled())
        w.worker.finish();self.assertTrue(w.start_action.isEnabled());w.discovered([],'No devices');self.assertFalse(w.start_action.isEnabled())
    def test_disconnection_does_not_save_unsaved_fields_or_start_worker(self):
        w=self.window;self.connect_phone();w.fields['max_moves'].setValue(3);w.discovered([],'');w.start_bot()
        self.assertTrue(w.settings_dirty);self.mocks[2].assert_not_called();self.mocks[3].assert_not_called()
    def test_device_refresh_preserves_selection_until_selected_device_disconnects(self):
        w=self.window;w.discovered([('a','First'),('b','Second')],'');w.devices.setCurrentIndex(1)
        w.discovered([('b','Second'),('a','First')],'');self.assertEqual(w.selected_serial(),'b');self.assertTrue(w.start_action.isEnabled())
        w.discovered([],'');self.assertIsNone(w.selected_serial());self.assertFalse(w.start_action.isEnabled())
    def test_clear_button_tracks_semantic_entries_including_after_clear_and_restart(self):
        w=self.window;self.assertFalse(w.clear_button.isEnabled())
        w.bot_event('activity',{'record':{'event':'move','move':1}});self.assertTrue(w.clear_button.isEnabled())
        w.clear_button.click();self.assertFalse(w.clear_button.isEnabled());self.assertEqual(w.activity.counts,(0,0))
        w.bot_event('activity',{'record':{'event':'move','move':2}});self.connect_phone();w.start_bot();self.assertFalse(w.clear_button.isEnabled())
    def test_save_only_activates_for_actual_changes_and_disables_when_reverted(self):
        w=self.window;self.assertFalse(w.save_button.isEnabled());w.fields['max_moves'].setValue(4);self.assertTrue(w.save_button.isEnabled());self.assertEqual(w.save_note.text(),tr('unsaved'))
        w.fields['max_moves'].setValue(DEFAULTS['max_moves']);self.assertFalse(w.settings_dirty);self.assertFalse(w.save_button.isEnabled());self.assertEqual(w.save_note.text(),tr('saved'))
        w.fields['read_score'].setChecked(False);w.fields['read_score'].setChecked(True);self.assertFalse(w.save_button.isEnabled())
        w.fields['max_moves'].setValue(5);w.save_settings();self.assertFalse(w.save_button.isEnabled());self.assertFalse(w.settings_dirty)
        w.save_settings();self.assertEqual(self.mocks[2].call_count,1)
    def test_instant_appearance_changes_never_activate_save(self):
        w=self.window;w.change_language('en');w.change_theme('light');self.assertFalse(w.settings_dirty);self.assertFalse(w.save_button.isEnabled())
        self.assertEqual(self.mocks[2].call_count,2)
        w.fields['beam'].setValue(250);w.change_language('uk');self.assertTrue(w.settings_dirty);self.assertTrue(w.save_button.isEnabled());self.assertEqual(self.mocks[2].call_args.args[0]['beam'],180)
    def test_settings_do_not_nest_opacity_effects_on_enabled_rows(self):
        w=self.window;w.tabs.setCurrentIndex(1);w.settings_categories.setCurrentRow(4)
        self.assertIsNone(w.tabs.widget(1).graphicsEffect())
        for key in ('console_logs','file_logs','show_board'):self.assertIsNone(w.setting_rows[key].graphicsEffect())
        w.fields['file_logs'].setChecked(False);self.assertIsNotNone(w.setting_rows['max_sessions'].graphicsEffect())
        w.fields['file_logs'].setChecked(True);self.assertIsNone(w.setting_rows['max_sessions'].graphicsEffect())
    def test_score_dependency_preserves_value_and_dims_entire_row(self):
        w=self.window;w.fields['score_every'].setValue(7);w.fields['read_score'].setChecked(False)
        self.assertFalse(w.fields['score_every'].isEnabled());self.assertAlmostEqual(w.setting_rows['score_every'].graphicsEffect().opacity(),.45)
        w.fields['read_score'].setChecked(True);self.assertTrue(w.fields['score_every'].isEnabled());self.assertEqual(w.fields['score_every'].value(),7);self.assertIsNone(w.setting_rows['score_every'].graphicsEffect())
    def test_storage_dependencies_and_reenable_preserve_choices(self):
        w=self.window;self.assertFalse(w.fields['max_screenshots'].isEnabled())
        w.fields['save_screenshots'].setChecked(True);self.assertTrue(w.fields['max_screenshots'].isEnabled());w.fields['max_screenshots'].setValue(8)
        w.fields['file_logs'].setChecked(False)
        for key in ('save_screenshots','max_screenshots','max_sessions','max_history_mb','max_log_mb'):
            self.assertFalse(w.fields[key].isEnabled(),key);self.assertAlmostEqual(w.row_effects[key].opacity(),.45)
        w.fields['file_logs'].setChecked(True)
        for key in ('save_screenshots','max_screenshots','max_sessions','max_history_mb','max_log_mb'):self.assertTrue(w.fields[key].isEnabled(),key)
        self.assertEqual(w.fields['max_screenshots'].value(),8);self.assertTrue(w.fields['save_screenshots'].isChecked())
    def test_disabled_history_cannot_write_screenshots_from_latent_preference(self):
        w=self.window;self.connect_phone();w.fields['save_screenshots'].setChecked(True);w.fields['file_logs'].setChecked(False);w.start_bot()
        self.assertFalse(w.worker.settings['file_logs']);self.assertFalse(w.worker.settings['save_screenshots']);self.assertTrue(w.settings['save_screenshots'])
    def test_reset_only_affects_current_game_category(self):
        w=self.window;custom=self.root/'profiles/custom.json';custom.write_text('{}')
        w.fields['profile'].setText('profiles/custom.json');w.fields['beam'].setValue(400);w.fields['max_moves'].setValue(8)
        w.settings_categories.setCurrentRow(1);w.reset_settings()
        self.assertEqual(w.fields['max_moves'].value(),0);self.assertEqual(w.fields['beam'].value(),400);self.assertEqual(w.fields['profile'].text(),'profiles/custom.json');self.assertTrue(w.settings_dirty)
        self.assertIn('только открытую категорию',w.reset_button.toolTip())
        w.settings_categories.setCurrentRow(2);w.reset_settings();self.assertEqual(w.fields['beam'].value(),180);self.assertEqual(w.fields['profile'].text(),'profiles/custom.json')
    def test_appearance_reset_preserves_unsaved_strategy_and_profile(self):
        w=self.window;w.change_language('uk');w.change_theme('light');w.fields['beam'].setValue(350);w.settings_categories.setCurrentRow(0);w.reset_settings()
        self.assertEqual(w.lang,'ru');self.assertEqual(w.theme,'dark');self.assertEqual(w.fields['beam'].value(),350);self.assertTrue(w.settings_dirty);self.assertEqual(self.mocks[2].call_args.args[0]['beam'],180)
    def test_profile_missing_malformed_or_nonobject_blocks_save_and_start(self):
        w=self.window;self.connect_phone()
        for name,text in [('missing.json',None),('bad.json','{'),('array.json','[]'),('plain.txt','{}')]:
            if text is not None:(self.root/'profiles'/name).write_text(text)
            w.fields['profile'].setText('profiles/'+name)
            self.assertFalse(w.profile_valid,name);self.assertFalse(w.start_action.isEnabled());self.assertFalse(w.save_button.isEnabled());self.assertTrue(w.fields['profile'].property('invalid'));self.assertFalse(w.save_settings());w.start_bot()
        self.mocks[2].assert_not_called();self.mocks[3].assert_not_called()
        w.fields['profile'].setText(DEFAULTS['profile']);self.assertTrue(w.profile_valid);self.assertTrue(w.start_action.isEnabled());self.assertFalse(w.settings_dirty)
    def test_browse_profile_stores_project_relative_path_and_validates_json(self):
        w=self.window;custom=self.root/'profiles/another.json';custom.write_text('{"board":[1,2,3,4]}')
        with patch('blockblast.desktop.QFileDialog.getOpenFileName',return_value=(str(custom),'JSON')) as dialog:w.browse_profile()
        self.assertEqual(w.fields['profile'].text(),'profiles/another.json');self.assertTrue(w.profile_valid);self.assertTrue(w.settings_dirty);dialog.assert_called_once()
    def test_profile_deleted_after_edit_is_rechecked_before_start(self):
        w=self.window;self.connect_phone();(self.root/DEFAULTS['profile']).unlink();w.start_bot()
        self.assertFalse(w.start_action.isEnabled());self.assertFalse(w.profile_valid);self.assertIsNone(w.worker)
    def test_history_diagnostics_switch_syncs_both_filters_without_losing_search(self):
        w=self.window;w.history_detail.set_records([dict(event='timing',seconds=.27),dict(event='start')]);w.history_search.setText('0.27')
        self.assertNotIn('0.27',w.history_detail.toPlainText());w.history_debug_toggle.setChecked(True)
        self.assertTrue(w.debug_toggle.isChecked());self.assertTrue(w.activity.debug);self.assertIn('0.27',w.history_detail.toPlainText());self.assertEqual(w.history_search.text(),'0.27')
        w.debug_toggle.setChecked(False);self.assertFalse(w.history_debug_toggle.isChecked());self.assertNotIn('0.27',w.history_detail.toPlainText())
    def test_finished_session_keeps_result_in_status_and_neutral_board_hint(self):
        w=self.window;self.connect_phone();w.start_bot();w.worker.control.reason='Достигнут лимит ходов';w.worker.finish()
        self.assertEqual(w.status.text(),tr('limit_reached'));self.assertEqual(w.hint.text(),tr('waiting_start'))
    def test_offline_status_has_only_short_text_in_both_labels_all_languages(self):
        w=self.window
        for language in ('ru','en','uk'):
            w.change_language(language);w.discovered([],'Подключите телефон и разрешите USB-отладку');w.start_bot()
            self.assertEqual(w.status.text(),tr('waiting_adb',language));self.assertEqual(w.hint.text(),tr('waiting_start',language));self.assertFalse(w.phone.connected)
            self.assertNotIn(tr('connect_hint',language),w.status.text()+w.hint.text()+w.phone.toolTip())

class BadgeLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_badges_fit_one_visual_line_in_every_locale_and_theme(self):
        view=EventView();view.resize(430,450);view.debug=True;view.show()
        try:
            for theme in ('dark','light'):
                apply(self.app,theme);view.theme=theme
                for language in ('ru','en','uk'):
                    view.lang=language;view.set_records([dict(event=kind,time='2026-10-30T23:00:01') for kind in ('start','attempt','move','paused','error','rejected','timing')]);self.app.processEvents();view.document().documentLayout().documentSize()
                    table=next(f for f in view.document().rootFrame().childFrames() if isinstance(f,QTextTable))
                    self.assertGreaterEqual(table.format().columnWidthConstraints()[1].rawValue(),106)
                    for row in range(table.rows()):
                        block=table.cellAt(row,1).firstCursorPosition().block()
                        self.assertTrue(block.blockFormat().nonBreakableLines());self.assertEqual(block.layout().lineCount(),1,(theme,language,row,block.text()))
        finally:view.close()

if __name__=='__main__':unittest.main()

"""Platform boundaries: native Windows lease and quiet child processes."""
import os
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from blockblast.runtime import DeviceLease, process_options, tool_env
from blockblast.score import ScoreReader
from blockblast.config import DEFAULTS
from blockblast.session import Session,Stats
from PIL import Image


class ProcessOptionsTests(unittest.TestCase):
    def test_windows_tesseract_version_with_v_prefix_is_accepted(self):
        from types import SimpleNamespace
        results=[SimpleNamespace(returncode=0,stdout=b'tesseract v5.4.0.20240606'),
                 SimpleNamespace(returncode=0,stdout=b'List of available languages (1):\nafr\n')]
        with patch('blockblast.score.shutil.which',return_value='tesseract.exe'), \
             patch('blockblast.score.subprocess.run',side_effect=results):
            reader=ScoreReader()
        self.assertTrue(reader.available)
        self.assertEqual(reader.language,'afr')

    def test_windows_helpers_have_no_console(self):
        with patch('blockblast.runtime.sys.platform','win32'), \
             patch.object(subprocess,'CREATE_NO_WINDOW',0x08000000,create=True):
            options=process_options({'EXAMPLE':'value'})
        self.assertEqual(options,{'env':{'EXAMPLE':'value'},'creationflags':0x08000000})

    def test_linux_helpers_keep_default_creation_flags(self):
        with patch('blockblast.runtime.sys.platform','linux'):
            self.assertEqual(process_options({'EXAMPLE':'value'}),{'env':{'EXAMPLE':'value'}})

    def test_windows_frozen_tools_do_not_get_linux_library_path(self):
        with patch('blockblast.runtime.sys.platform','win32'), \
             patch.object(sys,'frozen',True,create=True), \
             patch.dict(os.environ,{},clear=True):
            self.assertNotIn('LD_LIBRARY_PATH',tool_env())


class CoarseClockTests(unittest.TestCase):
    pass


@unittest.skipUnless(sys.platform=='win32','Windows named-object implementation')
class WindowsLeaseTests(unittest.TestCase):
    def test_second_controller_is_rejected_and_close_allows_restart(self):
        with DeviceLease('windows-test-phone'):
            with self.assertRaisesRegex(RuntimeError,'другим экземпляром'):
                DeviceLease('windows-test-phone')
            with DeviceLease('windows-other-phone'):
                pass
        with DeviceLease('windows-test-phone'):
            pass

    def test_lease_is_shared_with_child_process(self):
        code="from blockblast.runtime import DeviceLease; DeviceLease('windows-process-test')"
        with DeviceLease('windows-process-test'):
            child=subprocess.run([sys.executable,'-c',code],capture_output=True,timeout=15)
        self.assertNotEqual(child.returncode,0)
        child=subprocess.run([sys.executable,'-c',code],capture_output=True,timeout=15)
        self.assertEqual(child.returncode,0,child.stderr.decode(errors='replace'))

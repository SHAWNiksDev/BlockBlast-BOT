"""Verify the audit fixes offline; no device input or writes to user settings."""
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parent.parent
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromName('test_audit_fixes')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

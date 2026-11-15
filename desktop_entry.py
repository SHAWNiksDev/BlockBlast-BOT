"""Desktop entry point, with startup diagnostics for packaged validation."""
import sys

try:
    from blockblast.desktop import main
    result=main()
except Exception:
    if '--packaging-test' not in sys.argv:
        raise
    import json
    from pathlib import Path
    import traceback
    report=Path(sys.argv[sys.argv.index('--packaging-test')+1])
    report.write_text(json.dumps({'ok':False,'error':traceback.format_exc()},ensure_ascii=False),encoding='utf-8')
    result=1

raise SystemExit(result)

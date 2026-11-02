#!/usr/bin/env python3
"""Targz Converter'ı doğrudan çalıştırmak için tek satırlık giriş noktası.

    python3 targz2app.py                       arayüzü açar
    python3 targz2app.py --donustur --ac x.tar  kurar ve açar
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from targz_converter.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

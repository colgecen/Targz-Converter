#!/usr/bin/env python3
"""Targz Converter'ı sisteme kuran betik.

    python3 install.py              kurar (menü + sağ tık menüleri)
    python3 install.py --masaustune  masaüstüne de kısayol ekler
    python3 install.py --listele    hangi dosyaların nereye yazılacağını gösterir
    python3 install.py --kaldir     kurulumu geri alır
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from targz_converter.install import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

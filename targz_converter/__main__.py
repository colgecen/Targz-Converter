"""Komut satırı ve arayüz giriş noktası.

Kullanım örnekleri:
    targz-converter                             arayüzü açar
    targz-converter indirilen/uygulama.tar.gz   dosyayı arayüzde hazır getirir
    targz-converter --donustur a.tar.gz         arayüz olmadan kurar (sağ tık böyle çalışır)
    targz-converter --donustur --ac a.tar.gz    kurar ve uygulamayı hemen açar
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, core, desktop
from .install import APP_ID


def default_base() -> Path:
    """Uygulamaların açılacağı yer: ~/.local/share/Applications."""
    from os import environ  # noqa: PLC0415 (sadece burada gerekiyor)

    root = Path(environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return Path(environ.get("TARGZ_CONVERTER_DIR", root / "Applications"))


def parser() -> argparse.ArgumentParser:
    arg = argparse.ArgumentParser(
        prog=APP_ID,
        description="Sıkıştırılmış arşivleri tek adımda Linux uygulamasına çevirir.",
    )
    arg.add_argument("dosya", nargs="*", help="dönüştürülecek .tar.gz / .AppImage dosyaları")
    arg.add_argument("--donustur", "--convert", dest="headless", action="store_true",
                     help="arayüzü açmadan hemen dönüştür (sağ tık menüsü bunu kullanır)")
    arg.add_argument("--ac", "--launch", dest="launch", action="store_true",
                     help="dönüşümden sonra uygulamayı başlat")
    arg.add_argument("--masaustune", dest="desktop", action="store_true", default=None,
                     help="masaüstüne kısayol ekle")
    arg.add_argument("--masaustune-yok", dest="desktop", action="store_false",
                     help="masaüstüne kısayol ekleme")
    arg.add_argument("--baslangicta", dest="autostart", action="store_true",
                     help="oturum açılınca uygulamanın kendiliğinden çalışmasını sağla")
    arg.add_argument("--hedef", type=Path, default=None,
                     help="kurulum klasörü (varsayılan: ~/.local/share/Applications)")
    arg.add_argument("--ad", dest="name", default="", help="uygulama adı")
    arg.add_argument("--kur-ara", dest="install_tool", action="store_true",
                     help="Targz Converter'ın kendisini sisteme kur")
    arg.add_argument("--surum", "--version", action="version", version=f"%(prog)s {__version__}")
    return arg


def convert_headless(files: list[Path], base: Path, options: argparse.Namespace) -> int:
    """Arayüz olmadan dönüşüm: sağ tık menüsü ve betikler için hızlı yol."""
    make_desktop = True if options.desktop is None else options.desktop
    failures = 0
    for archive in files:
        try:
            app = core.convert(archive, base, options.name)
        except Exception as exc:
            print(f"olmadı: {exc}", file=sys.stderr)
            failures += 1
            continue
        written = desktop.install(app, desktop=make_desktop, autostart=options.autostart)
        print(desktop.summary(app, written))
        if options.launch:
            desktop.launch(app)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    options = parser().parse_args(argv)

    if options.install_tool:
        from .install import main as install_main  # noqa: PLC0415

        return install_main(["--masaustune"] if options.desktop else [])

    base = (options.hedef or default_base()).expanduser()
    files = [Path(item).expanduser() for item in options.dosya]
    for path in files:
        if not path.is_file():
            print(f"dosya bulunamadı: {path}", file=sys.stderr)
            return 2

    if options.headless:
        if not files:
            print("hangi dosya? örnek: targz-converter --donustur uygulama.tar.gz",
                  file=sys.stderr)
            return 2
        return convert_headless(files, base, options)

    return open_interface(base, files)


def open_interface(base: Path, files: list[Path]) -> int:
    """PySide6 varsa Qt arayüzü, yoksa tkinter arayüzü."""
    try:
        from . import ui_qt  # noqa: PLC0415

        return ui_qt.run(base, files)
    except ImportError:
        from . import ui_tk  # noqa: PLC0415

        return ui_tk.run(base, files)


if __name__ == "__main__":
    sys.exit(main())

"""Aracın kendisini sisteme kurar: çalıştırıcı, menü kısayolu, simge, sağ tık.

Kurulum tamamıyla kullanıcı dizinlerinedir, root gerekmez:

    ~/.local/share/targz-converter/     programın kopyası (kütüphaneleriyle)
    ~/.local/bin/targz-converter        komut satırı çalıştırıcısı
    ~/.local/share/applications/        Uygulamalar menüsü kısayolu
    ~/.local/share/icons/hicolor/       simge
    ~/.local/share/kio/servicemenus/    Dolphin sağ tık menüsü (KDE)
    ~/.local/share/nautilus/scripts/    Nautilus betiği (GNOME)

Çalıştırmak için:  python3 install.py     ya da      python3 install.py --kaldir
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .core import log
from .desktop import APP_DIR, AUTOSTART_DIR, ICON_DIR, Shortcut, refresh_caches, write_desktop

APP_ID = "com.github.colgecen.TargzConverter"
DATA_DIR = APP_DIR / "targz-converter"
BIN_DIR = Path.home() / ".local" / "bin"
PACKAGE = "targz_converter"
LAUNCHER = "targz-converter"
SHELL_LAUNCHER = "targz-converter-hazir-ac"
DESKTOP_FALLBACK = Path.home() / "Masaüstü"
SERVICE_MIME = ("application/gzip;application/x-compressed-tar;application/x-tar;"
                "application/x-xz-compressed-tar;application/x-bzip2-compressed-tar;"
                "application/x-zstd-compressed-tar;application/x-appimage;")


def source_root() -> Path:
    """Depo kökü; kurulu kopyadan çalıştırıldığında da doğru yolu bulur."""
    here = Path(__file__).resolve().parent
    for candidate in (here.parent, DATA_DIR):
        if (candidate / PACKAGE / "core.py").is_file():
            return candidate
    return here.parent


def _copy_package() -> Path:
    """Programı ~/.local/share/targz-converter içine kopyalar (kendini yeterli kılar)."""
    origin = source_root()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / PACKAGE
    if origin.resolve() == DATA_DIR.resolve():
        return target
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(origin / PACKAGE, target,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for script in ("targz2app.py", "install.py"):
        source = origin / script
        if source.is_file():
            shutil.copy2(source, DATA_DIR / script)
    return target


def _write_launcher() -> Path:
    """Arşivden gelen dosyaları bekleyen tek satırlık giriş noktasını yazar."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    launcher = BIN_DIR / LAUNCHER
    launcher.write_text(
        "#!/bin/sh\n"
        "# Targz Converter giriş noktası (install.py üretir)\n"
        'for root in "$HOME/.local/share/targz-converter" '
        '"$HOME/Belgeler/Repolar/Targz-Converter" "$HOME/Belgeleri/Repolar/Targz-Converter"; do\n'
        '    [ -d "$root/targz_converter" ] && exec python3 "$root/targz2app.py" "$@"\n'
        "done\n"
        'echo "Targz Converter bulunamadı" >&2\nexit 1\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    return launcher


def _app_icon() -> str:
    """Aracın kendi simgesini temaya koyar; yoksa arşiv simgesini kullanır."""
    source = source_root() / "assets" / "targz-converter.svg"
    if not source.is_file():
        return "application-x-compressed-tar"
    folder = ICON_DIR / "scalable" / "apps"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, folder / f"{APP_ID}.svg")
    return APP_ID


def converter_shortcut(launcher: Path) -> Shortcut:
    return Shortcut(
        id=APP_ID,
        name="Targz Converter",
        exec_line=f"{launcher} %F",
        comment="Sıkıştırılmış arşivleri tek sürüklemede uygulamaya çevirir",
        generic="Arşivden uygulama kurucu",
        icon=_app_icon(),
        categories="Utility;Core;PackageManagement;",
        keywords="tar.gz;tgz;arşiv;appimage;kısayol;desktop;kur;çevir",
    )


def service_menu(launcher: Path) -> Path:
    """Dolphin'in (KDE) sağ tık menüsüne çevirme komutunu ekler.

    İki eylem vardır: biri arayüzü açar, diğeri ('çevir ve aç') işi bitirip
    uygulamayı hemen başlatır.
    """
    quick = launcher.parent / SHELL_LAUNCHER
    quick.write_text(
        "#!/bin/sh\n"
        "# Seçili arşivi sessizce dönüştürür ve uygulamayı açar\n"
        f'exec "{launcher}" --donustur --ac "%f"\n',
        encoding="utf-8",
    )
    quick.chmod(0o755)

    folder = APP_DIR / "kio" / "servicemenus"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{APP_ID}.desktop"
    target.write_text(
        "[Desktop Entry]\n"
        "Type=Service\n"
        "MimeType=" + SERVICE_MIME + "\n"
        "ServiceTypes=KonqPopupMenu/Plugin\n"
        "Actions=openTargz;convertAndLaunch;\n"
        "X-KDE-Priority=TopLevel\n"
        "\n"
        "[Desktop Action openTargz]\n"
        "Name=Convert to application...\n"
        "Name[tr]=Targz Converter ile uygulamaya çevir...\n"
        "Icon=application-x-compressed-tar\n"
        f'Exec={launcher} "%f"\n'
        "\n"
        "[Desktop Action convertAndLaunch]\n"
        "Name=Convert and launch\n"
        "Name[tr]=Çevir ve uygulamayı aç\n"
        "Icon=system-run\n"
        f"Exec={quick} %f\n",
        encoding="utf-8",
    )
    return target


def nautilus_script(launcher: Path) -> Path:
    """Nautilus'un (GNOME) Scripts menüsüne aynı komutu ekler."""
    folder = APP_DIR / "nautilus" / "scripts"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "Targz Converter ile uygulamaya cevir"
    target.write_text(
        "#!/bin/sh\n"
        "# Nautilus betiği: seçili arşivi Targz Converter ile açar\n"
        'IFS="\n"\n'
        'for dosya in $NAUTILUS_SCRIPT_SELECTED_FILE_PATHS; do\n'
        '    [ -f "$dosya" ] && "$LAUNCHER" "$dosya" &\n'
        "done\n".replace("$LAUNCHER", str(launcher)),
        encoding="utf-8",
    )
    target.chmod(0o755)
    return target


def converter_shortcuts(desktop: bool = False, autostart: bool = False) -> dict[str, Path]:
    """Aracı uygulamalar menüsüne, isterse masaüstüne ekler."""
    entry = converter_shortcut(_write_launcher())
    written = {"menü": write_desktop(entry, APP_DIR / "applications", trust=False)}
    if desktop:
        written["masaüstü"] = write_desktop(entry, DESKTOP_FALLBACK)
    if autostart:
        written["otomatik"] = write_desktop(entry, AUTOSTART_DIR, trust=False)
    return written


def installer_files(desktop: bool = False, autostart: bool = False) -> dict[str, Path]:
    """Kurulumda üretilen her şey: çalıştırıcı, kısayollar, sağ tık menüleri."""
    launcher = _write_launcher()
    files = {
        "çalıştırıcı": launcher,
        "çevir-ve-aç çalıştırıcısı": launcher.parent / SHELL_LAUNCHER,
    }
    files.update(converter_shortcuts(desktop=desktop, autostart=autostart))
    files["sağ tık (Dolphin)"] = service_menu(launcher)
    files["sağ tık (Nautilus)"] = nautilus_script(launcher)
    return files


def install(desktop: bool = False, autostart: bool = False) -> list[Path]:
    """Her şeyi kurar ve oluşturulan dosyaların listesini döndürür."""
    log("Targz Converter kuruluyor...")
    log(f"  program kopyası: {_copy_package()}")
    written = list(installer_files(desktop=desktop, autostart=autostart).values())
    refresh_caches()
    for path in written:
        log(f"  eklendi: {path}")
    log("Bitti. Dolphin'de bir .tar.gz dosyasına sağ tıklayıp menüde görebilirsin.")
    return written


def uninstall() -> list[str]:
    """Kurulumun geride bıraktıklarını temizler."""
    removed: list[str] = []
    targets = [
        DATA_DIR,
        BIN_DIR / LAUNCHER,
        BIN_DIR / SHELL_LAUNCHER,
        APP_DIR / "applications" / f"{APP_ID}.desktop",
        APP_DIR / "kio" / "servicemenus" / f"{APP_ID}.desktop",
        APP_DIR / "nautilus" / "scripts" / "Targz Converter ile uygulamaya cevir",
        ICON_DIR / "scalable" / "apps" / f"{APP_ID}.svg",
        DESKTOP_FALLBACK / "Targz Converter.desktop",
    ]
    for target in targets:
        try:
            if target.is_dir():
                shutil.rmtree(target)
            elif not target.exists():
                continue
            else:
                target.unlink()
            removed.append(str(target))
        except OSError as exc:
            log(f"  silinemedi ({target}): {exc}")
    refresh_caches()
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install", description="Targz Converter kurulumu")
    parser.add_argument("--kaldir", "--uninstall", dest="remove", action="store_true",
                        help="kurulumu geri alır")
    parser.add_argument("--masaustune", dest="desktop", action="store_true",
                        help="aracın kendisi için de masaüstü kısayolu oluşturur")
    parser.add_argument("--baslangicta", dest="autostart", action="store_true",
                        help="aracı oturum açılınca çalıştırır (genellikle gerekmez)")
    parser.add_argument("--listele", action="store_true", help="kurulan dosyaları listeler")
    args = parser.parse_args(argv)

    if args.remove:
        for path in uninstall():
            log(f"  silindi: {path}")
        log("Kaldırma tamam.")
        return 0
    if args.listele:
        for label, path in installer_files().items():
            print(f"{label}: {path}")
        return 0
    install(desktop=args.desktop, autostart=args.autostart)
    return 0


if __name__ == "__main__":
    sys.exit(main())

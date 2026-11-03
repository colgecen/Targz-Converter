"""``.desktop`` üretimi ve masaüstüne / uygulamalar menüsüne kurulum.

Linux'ta "uygulama" demek aslında bir ``.desktop`` dosyası demek. Bu modül o
dosyayı yazar, simgeyi temaya yerleştirir ve üç yere kurulum yapar:

    ~/.local/share/applications   Uygulama başlatıcı (Kickoff) menüsü
    ~/Masaüstü                    masaüstü kısayolu (kullanıcı isterse)
    ~/.config/autostart           oturum açılınca kendiliğinden çalışma
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import i18n
from .core import App, human_size

APP_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
AUTOSTART_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart"
ICON_DIR = APP_DIR / "icons" / "hicolor"


def xdg_dir(kind: str) -> str:
    """Sistem ayarından klasör adı öğrenir (`DESKTOP`, `DOWNLOAD`...)."""
    if not shutil.which("xdg-user-dir"):
        return ""
    try:
        done = subprocess.run(["xdg-user-dir", kind], capture_output=True, text=True,
                              timeout=5)
        return done.stdout.strip() if done.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def desktop_dir() -> Path:
    """Masaüstü klasörü. Kurulum dili İngilizceyse ~/Desktop, Türkçeyse ~/Masaüstü.

    Ad hiçbir yerde sabit yazılmıyor: önce sistemden sorulur, olmazsa ev dizininde
    dolaşan bilinen adlardan hangisi varsa o kullanılır.
    """
    found = xdg_dir("DESKTOP")
    if found:
        return Path(found)
    for name in ("Masaüstü", "Desktop", "Masaustu", "Área de trabalho", "Área de trabajo"):
        candidate = Path.home() / name
        if candidate.is_dir():
            return candidate
    return Path.home() / "Desktop"


DESKTOP_DIR = desktop_dir()


@dataclass
class Shortcut:
    """Küçük bir kısayol tanımı (ana uygulamanınki dahil)."""

    id: str
    name: str
    exec_line: str
    comment: str = ""
    generic: str = ""
    icon: str = "application-x-executable"
    categories: str = "Utility;"
    path: str = ""
    terminal: bool = False
    wm_class: str = ""
    keywords: str = ""
    mime: str = ""
    no_display: bool = False


def _value(text: str) -> str:
    return text.replace("%", "%%").replace("\n", " ")


def build(entry: Shortcut) -> str:
    """Shortcut kaydını .desktop metnine çevirir."""
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Version=1.0",
        f"Name={_value(entry.name)}",
        f"GenericName={_value(entry.generic or entry.name)}",
        f"Comment={_value(entry.comment)}",
        f"Exec={entry.exec_line}",
        f"Icon={entry.icon}",
        "Terminal=true" if entry.terminal else "Terminal=false",
        f"Categories={entry.categories}",
        "StartupNotify=true",
    ]
    if entry.path:
        lines.append(f"Path={entry.path}")
    if entry.wm_class:
        lines.append(f"StartupWMClass={entry.wm_class}")
    if entry.keywords:
        lines.append(f"Keywords={entry.keywords};")
    if entry.mime:
        lines.append(f"MimeType={entry.mime}")
    if entry.no_display:
        lines.append("NoDisplay=true")
    return "\n".join(line for line in lines if not line.endswith("=")) + "\n"


def write_desktop(entry: Shortcut, folder: Path, trust: bool = True) -> Path:
    """Bir kısayolu diske yazar ve Plasma'nın açabileceği hâle getirir."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{entry.id}.desktop"
    target.write_text(build(entry), encoding="utf-8")
    target.chmod(0o755)
    if trust:
        trust_file(target)
    return target


def trust_file(path: Path) -> None:
    """Masaüstü simgelerinde Plasma'nın tek seferlik 'güven' sorusunu atlar.

    Plasma, kullanıcı tarafından oluşturulmuş .desktop dosyalarını çalıştırmadan
    önce doğrulamak ister. Masaüstü ortamının okuyabileceği etiketlerden elimizde
    ne varsa yazılır; hiçbiri tutmazsa pencere bir kez sorar, kullanıcı "Güven"
    dedikten sonra bir daha sormaz.
    """
    path.chmod(path.stat().st_mode | 0o755)
    for name in ("user.metadata.trusted", "user.org.kde.dolphin.Trusted"):
        _setxattr(path, name, b"true")
    _gio_metadata(path, "trusted", "true")


def _setxattr(path: Path, name: str, value: bytes) -> None:
    try:
        os.setxattr(path, name, value, follow_symlinks=False)
    except OSError:
        pass  # dosya sistemi desteklemiyor olabilir, sorun değil


def _gio_metadata(path: Path, key: str, value: str) -> None:
    """GNOME tarafının metadata:: anahtarını da dene; kütüphane yoksa sessizce geç."""
    try:
        import gi  # noqa: PLC0415  (isteğe bağlı, sadece GNOME'da kurulu gelir)

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio  # noqa: E402, PLC0415
    except Exception:
        return
    try:
        Gio.File.new_for_path(str(path)).set_attribute_string(
            f"metadata::{key}", value, Gio.FileQueryInfoFlags.NONE, None)
    except Exception:
        pass


def install_icon(source: Path | None, slug: str) -> str:
    """Uygulama simgesini temaya kopyalar ve adını döndürür.

    .ico dosyaları PIL varsa PNG'ye çevrilir (bazı temalarda .ico okunmaz).
    Simge bulunamazsa genel çalıştırılabilir simgesi kullanılır.
    """
    fallback = "application-x-executable"
    if source is None or not source.is_file():
        return fallback
    name = f"{slug}.png"
    if source.suffix.lower() == ".svg":
        name = f"{slug}.svg"
    elif source.suffix.lower() in (".ico", ".xpm"):
        converted = _to_png(source, ICON_DIR / "256x256" / "apps" / name)
        return slug if converted else fallback

    folder = ICON_DIR / ("scalable" if name.endswith(".svg") else "256x256") / "apps"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, folder / name)
        return slug
    except OSError:
        return fallback


def _to_png(source: Path, target: Path) -> bool:
    try:
        from PIL import Image  # noqa: PLC0415  (kolayca bulunabilir bir iyileştirme)

        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            image.load()
            image.convert("RGBA").save(target, "PNG")
        return True
    except Exception:
        return False


def refresh_caches() -> None:
    """Uygulama listesini ve simge önbelleğini tazele (hata olursa yoksayar)."""
    commands = (["update-desktop-database", str(APP_DIR / "applications")],
                ["gtk-update-icon-cache", "-qtf", str(ICON_DIR)],
                ["kbuildsycoca6"], ["kbuildsycoca5"])
    for cmd in commands:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, capture_output=True, timeout=60)
            except (OSError, subprocess.TimeoutExpired):
                pass


def install(app: App, desktop: bool = False, autostart: bool = False) -> dict[str, Path]:
    """Uygulamayı sistem menüsüne ve istenirse masaüstüne/otomatik başlatmaya kurar."""
    icon = install_icon(app.icon, app.slug)
    entry = Shortcut(
        id=app.slug,
        name=app.name,
        exec_line=str(app.exe),
        comment=f"{app.name} ({app.archive.name}) - Targz Converter ile kuruldu",
        icon=icon,
        categories=app.categories,
        path=str(app.exe.parent),
        wm_class=app.wm_class,
        keywords=app.slug.replace("-", ";"),
    )
    written = {"menü": write_desktop(entry, APP_DIR / "applications", trust=False)}
    if desktop:
        written["masaüstü"] = write_desktop(entry, DESKTOP_DIR)
    if autostart:
        written["otomatik"] = write_desktop(entry, AUTOSTART_DIR, trust=False)
    refresh_caches()
    return written


def launch(app: App) -> None:
    """Uygulamayı kısayol üzerinden başlat (kapalı konsolda, beklenmeden)."""
    environment = dict(os.environ)
    environment.pop("TZ", None)
    try:
        subprocess.Popen(  # noqa: S603  (yol bizim kurduğumuz dosyadan geliyor)
            ["setsid", str(app.exe)],
            cwd=str(app.exe.parent), env=environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        print(f"başlatılamadı: {exc}")


def summary(app: App, written: dict[str, Path]) -> str:
    """Kullanıcıya gösterilecek kısa özet satırları."""
    lines = [i18n.t("msg_ready", name=app.name, size=human_size(app.size), seconds=f"{app.seconds:.1f}")]
    lines += [f"  {label}: {path}" for label, path in written.items()]
    lines.append(f"  program: {app.exe}")
    return "\n".join(lines)

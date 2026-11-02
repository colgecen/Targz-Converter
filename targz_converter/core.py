"""Arşiv tarama, açma, çalıştırılabilir ve ikon bulma işlemleri.

Hız buradaki iki karardan gelir:
  1. Tarama akışlıdır (``r|*``): arşiv bir kez okunur, baştan sona tekrar
     açılmaz. Yalnızca çalıştırılabilir adaylarının ilk 4 baytı okunur.
  2. Açma işi mümkünse sistem ``tar`` komutuna devredilir; ``pigz`` varsa
     paralel açılır. Python'un ``tarfile`` motoru yalnızca yedek olarak kalır.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path

# Çalıştırılabilir aramak için ilgilenmediğimiz yardımcı dizinler. Bir Linux
# uygulamasının kütüphane/plugın çöplüğü burada biter; buradan aşağısına inmeyiz.
SKIP_DIRS = frozenset(
    {
        "lib", "lib32", "lib64", "libs", "libexec", "share", "doc", "docs", "man",
        "locales", "localization", "lang", "resources", "resource", "plugins",
        "plugin", "extensions", "platforms", "sqldrivers", "imageformats",
        "styles", "printsupport", "networkinformation", "tls", "xcbglintegrations",
        "iconengines", "bearer", "virtualkeyboard", "qml", "rtlib", "node_modules",
        "site-packages", "venv", "env", "test", "tests", "samples", "examples",
        "extra", "data", "res", "usr", "etc", "var", "tmp", "cache", "logfiles",
        "crashpad", "scripts", "tools", "bin64", "bin32", "browser", "contents",
        "game", "meta", "drivers", "firmware", "fonts",
    }
)

# Dosya adının sonunda duran çöp sözcükler (uygulama adı üretilirken atılır).
NOISE_WORDS = frozenset(
    {
        "linux", "linux64", "linux_x64", "linux-x64", "x64", "x86_64", "x86-64",
        "amd64", "i386", "i686", "arm64", "aarch64", "portable", "setup", "install",
        "installer", "bin", "bundle", "release", "final", "stable", "nightly",
        "beta", "alpha", "turkish", "tux", "pc", "appimage", "tar", "gz", "tgz",
        "zip", "xz", "bz2", "zst", "run",
    }
)

KEEP_WORDS = frozenset(
    {"code", "studio", "ide", "editor", "player", "browser", "viewer", "server",
     "hub", "lab", "pro", "max", "os", "3d", "cad", "gis", "ai", "vs"}
)

ACRONYMS = {"ai", "cad", "cam", "cli", "gis", "ide", "pdf", "rpg", "tv", "ui", "vr",
            "3d", "64", "id", "it", "os", "pc", "rps", "ux", "vpn", "xml", "apk"}

ARCHIVE_SUFFIXES = (".tar", ".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst", ".tar.lz4",
                    ".tgz", ".txz", ".tbz2", ".tzst")
BARE_SUFFIXES = (".gz", ".xz", ".bz2", ".zst")
SINGLE_FILE_SUFFIXES = (".appimage", ".run", ".bin", ".sh", ".x86_64")

# Uygulama adı benzerliğinden kategori çıkarmak için küçük eşleme.
CATEGORY_HINTS = (
    (r"remote|teamviewer|rustdesk|anydesk|vnc|ssh", "RemoteAccess;Network;"),
    (r"steam|game|lutris|heroic|epic|minecraft", "Game;"),
    (r"editor|code|studio|ide|idea|pycharm|webstorm|goland|clion|devel", "Development;"),
    (r"cad|freecad|blender|mesh|slice|cura|prusaslicer|3d|print", "3DGraphics;Graphics;"),
    (r"gimp|krita|photo|image|paint|inkscape|inkscape|darktable", "Graphics;"),
    (r"vlc|mpv|music|spotify|radio|podcast|audio", "AudioVideo;Audio;"),
    (r"firefox|chrom|browser|brave|opera", "Network;WebBrowser;"),
    (r"libre|office|writer|calc|impress|pdf", "Office;"),
    (r"terminal|konsole|alacritty|kitty|shell", "System;TerminalEmulator;"),
)

_ELF = b"\x7fELF"
_PNG = b"\x89PNG"
_ICO_MAGIC = b"\x00\x00\x01\x00"
_VER = re.compile(r"^\d[\d.+-]*$")
_VER_TAIL = re.compile(r"[-_.]v?\d[\w.+-]*$")


# --------------------------------------------------------------------------- #
# Yardımcılar
# --------------------------------------------------------------------------- #

def log(message: str) -> None:
    print(message, flush=True)


def slugify(text: str) -> str:
    """Dosya/desktop adı için güvenli, kısa bir ad üretir."""
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return re.sub(r"-{2,}", "-", text)[:64] or "uygulama"


def archive_stem(path: Path) -> str:
    """teamviewer_qs.tar.gz -> teamviewer_qs,/foo/MyApp-1.2.3 -> MyApp."""
    name = path.name
    low = name.lower()
    for suffix in ARCHIVE_SUFFIXES:
        if low.endswith(suffix):
            return name[: -len(suffix)]
    return os.path.splitext(name)[0]


def _clean_tokens(stem: str) -> list[str]:
    tokens = re.split(r"[-_.\s]+", stem)
    cleaned: list[str] = []
    for token in tokens:
        if not token or _VER.match(token) or _VER.match(token.lstrip("v")):
            continue
        token = _VER_TAIL.sub("", token)
        if not token or token.lower() in NOISE_WORDS:
            continue
        cleaned.append(token)
    return cleaned


def pretty_name(stem: str, exe_name: str = "") -> str:
    """Arşiv/ad veya ikili adından okunabilir uygulama adı üretir."""
    for source in (exe_name, stem):
        if not source:
            continue
        tokens = _clean_tokens(source)
        if tokens:
            words = [t.upper() if t.lower() in ACRONYMS
                     else (t if t.isupper() and len(t) <= 4 else t.capitalize())
                     for t in tokens[:4]
                     if len(t) > 1 or t.lower() in KEEP_WORDS]
            if words:
                return " ".join(words)
    return stem[:1].upper() + stem[1:]


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for entry in files:
            try:
                total += os.lstat(os.path.join(root, entry)).st_size
            except OSError:
                pass
    return total


def free_bytes(path: Path) -> int:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        return shutil.disk_usage(probe).free
    except OSError:
        return 10**15


def download_dir() -> Path:
    """Kullanıcının indirilenler klasörü; ad dile göre değiştiği için tahmin edilmez."""
    if shutil.which("xdg-user-dir"):
        try:
            done = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True,
                                  text=True, timeout=5)
            found = done.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            found = ""
        if found and Path(found).is_dir():
            return Path(found)
    for name in ("İndirilenler", "Downloads", "Indirilenler", "İndirilenlerim"):
        candidate = Path.home() / name
        if candidate.is_dir():
            return candidate
    return Path.home()


SUPPORTED_SUFFIXES = (ARCHIVE_SUFFIXES + BARE_SUFFIXES +
                      (".zip", ".7z", ".appimage", ".run", ".bin", ".sh", ".x86_64",
                       ".rpm", ".deb", ".src.rpm", ".flatpakref", ".flatpak"))


def has_suffix(path: Path, suffixes: tuple[str, ...]) -> bool:
    """Dosya adının sonunda belirtilen soneklerden biri var mı? (çok parçalı sonekler dahil)"""
    low = path.name.lower()
    return any(low.endswith(suffix) for suffix in suffixes)


def is_supported(path: Path) -> bool:
    """Tahmini bir uygulama dosyası mı? (arşiv + tek dosyalık + paketler)"""
    return has_suffix(path, SUPPORTED_SUFFIXES)


def is_single_file_app(path: Path) -> bool:
    return has_suffix(path, SINGLE_FILE_SUFFIXES)


# --------------------------------------------------------------------------- #
# Sonuç yapıları
# --------------------------------------------------------------------------- #

@dataclass
class Candidate:
    path: str
    size: int
    score: int


@dataclass
class Scan:
    """Tek geçişli taramanın çıktısı."""

    root: str = ""
    size_total: int = 0
    file_count: int = 0
    names: set[str] = field(default_factory=set)
    exes: list[Candidate] = field(default_factory=list)
    icons: list[Candidate] = field(default_factory=list)
    preferred_root: str = ""


@dataclass
class App:
    """Kurulmaya hazır uygulama."""

    archive: Path
    install_dir: Path
    exe: Path
    name: str
    slug: str
    icon: Path | None = None
    categories: str = "Utility;"
    single_file: bool = False
    size: int = 0
    seconds: float = 0.0

    @property
    def wm_class(self) -> str:
        return self.exe.name


# --------------------------------------------------------------------------- #
# 1. Tarama
# --------------------------------------------------------------------------- #

def scan(archive: Path) -> Scan:
    """Arşivi tek seferde okur; çalıştırılabilir ve ikon adaylarını toplar."""
    result = Scan()
    roots: dict[str, int] = {}
    with tarfile.open(archive, "r|*") as tar:
        for member in tar:
            name = member.name
            result.names.add(Path(name).name.lower())
            if member.isdir():
                top = name.split("/", 1)[0].strip("/")
                if top and top != ".":
                    roots[top] = roots.get(top, 0) + 1
                continue
            if not member.isfile():
                continue

            result.file_count += 1
            result.size_total += member.size

            parts = [p for p in name.split("/") if p not in ("", ".")]
            if any(p.lower() in SKIP_DIRS for p in parts[:-1]):
                continue
            depth = len(parts) - 1
            if depth > 3:
                continue

            score = 0
            if member.mode & 0o111:
                score = 120 - depth * 10
            elif depth <= 1 and Path(name).suffix.lower() in (".appimage", ".run"):
                score = 70  # izin biti kaybolmuş olabilir, sonra düzeltilir
            if score:
                blob = _head(tar, member, 4)
                if blob.startswith(_ELF):
                    score += 60
                elif blob.startswith(b"#!"):
                    score += 25
                elif not blob.startswith(_PNG):
                    score -= 90
                if score > 0:
                    result.exes.append(Candidate(name, member.size, score))

            icon_score = _icon_score(parts, member.size)
            if icon_score:
                result.icons.append(Candidate(name, member.size, icon_score))

    if len(roots) == 1:
        result.root = next(iter(roots))
    elif roots:
        result.root = max(roots, key=lambda key: (roots[key], len(key)))
    return result


def _head(tar: tarfile.TarFile, member: tarfile.TarInfo, count: int) -> bytes:
    try:
        handle = tar.extractfile(member)
        if handle is None:
            return b""
        with handle:
            return handle.read(count) or b""
    except Exception:
        return b""


def _icon_score(parts: list[str], size: int) -> int:
    if not 32 < size < 4_000_000:
        return 0
    name = parts[-1]
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext not in (".png", ".svg", ".ico", ".xpm"):
        return 0
    low = stem.lower()
    score = 40
    if ext in (".svg", ".png"):
        score = 60
    if ext == ".ico":
        score = 50
    if any(token in low for token in ("logo", "icon", "app", "icon_256", "master")):
        score += 15
    if any(part.lower() in ("hicolor", "icons", "icon") for part in parts[:-1]):
        score += 10
    if len(parts) <= 2:
        score += 8
    if low in ("favicon", "splash", "loading", "spinner", "arrow", "check"):
        score -= 60
    return score


# --------------------------------------------------------------------------- #
# 2. Seçim (en iyi adayları bulma)
# --------------------------------------------------------------------------- #

def wanted_tokens(stem: str, root: str = "") -> set[str]:
    """Arşiv ve üst klasör adından çıkan sözcükler: doğru ikiliyi seçerken
    bu sözcükler puanı yükseltir."""
    wanted = {token.lower() for token in _clean_tokens(stem)}
    wanted |= {token.lower() for token in _clean_tokens(root)}
    return wanted - {""}


def pick_exe(scan_result: Scan, wanted: set[str], prefer_bin: bool = False) -> Candidate | None:
    if not scan_result.exes:
        return None
    pool = scan_result.exes
    if prefer_bin:
        # RPM/DEB gibi paketlerde /usr/bin/... altında gerçek ikili vardır; önce onu tercih et.
        bin_pool = [c for c in scan_result.exes
                    if any(part.lower() in ("bin", "sbin") for part in c.path.split("/")[:-1])]
        if bin_pool:
            pool = bin_pool
    best = max(pool,
               key=lambda c: (c.score + _name_bonus(Path(c.path).name, wanted), c.size))
    return best


def _name_bonus(filename: str, wanted: set[str]) -> int:
    stem = os.path.splitext(filename)[0].lower()
    bonus = 0
    if stem in wanted:
        bonus += 80
    elif any(word in stem for word in wanted):
        bonus += 30
    if stem.endswith(("gui", "-gui", "qt5", "qt6")):
        bonus -= 15
    if stem.startswith(("tv_", "setup", "unins", "crashpad")) or "crashpad" in stem:
        bonus -= 100
    return bonus


def pick_icon(scan_result: Scan, wanted: set[str]) -> Candidate | None:
    if not scan_result.icons:
        return None
    return max(scan_result.icons,
               key=lambda c: (c.score + _name_bonus(Path(c.path).name, wanted), c.size))


def guess_categories(*texts: str) -> str:
    blob = " ".join(text.lower() for text in texts if text)
    for pattern, categories in CATEGORY_HINTS:
        if re.search(pattern, blob):
            return categories
    return "Utility;"


# --------------------------------------------------------------------------- #
# 3. Açma
# --------------------------------------------------------------------------- #

def unpack(archive: Path, dest: Path, progress=None) -> str:
    """Arşivi açar ve içine girilecek kök klasörü döndürür."""
    dest.mkdir(parents=True, exist_ok=True)
    used = "tarfile"
    if has_suffix(archive, (".zip",)):
        unzip = shutil.which("unzip")
        if not unzip:
            raise RuntimeError("ZIP açmak için unzip gerekli (apt: unzip).")
        done = subprocess.run([unzip, "-o", "-q", str(archive), "-d", str(dest)],
                               capture_output=True, text=True, timeout=3600)
        if done.returncode != 0:
            raise RuntimeError(f"ZIP açılamadı: {(done.stderr or done.stdout).strip()[:300]}")
        used = "unzip"
    elif has_suffix(archive, (".7z",)):
        seven = shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
        if not seven:
            raise RuntimeError("7z açmak için 7z/p7zip gerekli (apt: p7zip-full).")
        done = subprocess.run([seven, "x", "-y", str(archive), f"-o{dest}"],
                               capture_output=True, text=True, timeout=3600)
        if done.returncode != 0:
            raise RuntimeError(f"7z açılamadı: {(done.stderr or done.stdout).strip()[:300]}")
        used = "7z"
    elif shutil.which("tar"):
        cmd = ["tar", "-xf", str(archive), "-C", str(dest)]
        if shutil.which("pigz") and archive.name.lower().endswith((".tar.gz", ".tgz")):
            cmd[1:1] = ["--use-compress-program", "pigz -dc"]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if done.returncode == 0:
                used = "pigz+tar" if "pigz" in " ".join(cmd) else "tar"
            else:
                log(f"tar başarısız, Python motoruna dönülüyor: {done.stderr.strip()[:200]}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            log(f"tar çalıştırılamadı ({exc}), Python motoruna dönülüyor")
    if used == "tarfile":
        with tarfile.open(archive, "r:*") as tar:
            members = list(tar)
            step = max(1, len(members) // 100)
            for index, member in enumerate(members, 1):
                if progress and index % step == 0:
                    progress(min(1.0, index / len(members)))
            tar.extractall(dest, filter="data")

    root = _root_dir(dest)
    _relax_exec(root)
    if progress:
        progress(1.0)
    return used


def _root_dir(dest: Path) -> Path:
    """Tek bir üst klasör varsa ona girer (çoğu arşiv böyle paketlenir)."""
    try:
        entries = [p for p in dest.iterdir() if not p.name.startswith(".")]
    except OSError:
        return dest
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return dest


def _relax_exec(root: Path) -> None:
    """İzin biti kaybolmuş ikilileri ve AppImage'ları yeniden çalıştırılabilir yapar."""
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for filename in filenames:
            if filename.lower().endswith((".appimage", ".run")):
                target = Path(dirpath) / filename
                try:
                    target.chmod(target.stat().st_mode | 0o755)
                except OSError:
                    pass


BIN_PARENTS = {"bin", "sbin", "appbin", "bin64", "cmd", "usr/bin", "usr/sbin",
                "usr/local/bin", "local/bin", "sbin64", "bin32"}


def scan_directory(base: Path) -> Scan:
    """Çıkarılan bir klasör ağacını tarlar (RPM/DEB akışı için).

    Adaylar `base`'e göre görelidir ve kök adı boşturulur: aday yolu uygulamanın
    kendi yoludur. `parts` dizisi dosya yolundaki bölümlerden oluşur
    ("./usr/bin/x" -> ["usr", "bin", "x"]).
    """
    result = Scan()
    if not base.is_dir():
        raise NotADirectoryError(str(base))
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        rel_dir = Path(dirpath).relative_to(base).as_posix()
        parts = [] if rel_dir == "." else rel_dir.split("/")
        parent_dir = parts[-2].lower() if len(parts) >= 2 else ""
        if len(parts) > 3:
            dirnames[:] = [d for d in dirnames if not (d.lower() in SKIP_DIRS or d.startswith("."))]
            continue
        helper_hit = any(part.lower() in SKIP_DIRS for part in parts[1:])
        if helper_hit and parent_dir not in BIN_PARENTS and len(parts) > 1:
            dirnames[:] = [d for d in dirnames if not (d.lower() in SKIP_DIRS or d.startswith("."))]
            continue
        for filename in sorted(filenames):
            if len(parts) > 3:
                continue
            path = Path(dirpath) / filename
            low = filename.lower()
            if low.startswith(("tv_", "setup", "unins", "crashpad")) or "crashpad" in low:
                continue
            try:
                size = path.stat().st_size
                executable = bool(path.stat().st_mode & 0o111) or parent_dir in BIN_PARENTS
            except OSError:
                continue
            if not size:
                continue
            score = (120 - len(parts) * 10) if executable else 0
            magic = b""
            try:
                with path.open("rb") as handle:
                    magic = handle.read(4)
            except OSError:
                magic = b""
            if magic.startswith(_ELF):
                score += 60
            elif magic.startswith(b"#!"):
                score += 25
            elif not magic.startswith(_PNG):
                score -= 90
            if score <= 0:
                continue
            candidate_path = path.relative_to(base).as_posix()
            result.exes.append(Candidate(candidate_path, size, score))
            icon_score = _icon_score(parts + [filename], size)
            if icon_score:
                result.icons.append(Candidate(candidate_path, size, icon_score))
    return result


def _unpack_rpm(archive: Path, dest: Path, progress=None) -> str:
    """rpm2cpio | cpio -idm ile RPM paketini açar."""
    dest.mkdir(parents=True, exist_ok=True)
    rpm2cpio = shutil.which("rpm2cpio")
    cpio = shutil.which("cpio")
    if not rpm2cpio or not cpio:
        raise RuntimeError("RPM açmak için rpm2cpio ve cpio gerekli "
                           "(apt: rpm2cpio cpio | dnf: rpm2cpio cpio).")
    done = subprocess.run(["sh", "-c", f"{rpm2cpio} {archive} | {cpio} -idm"],
                           cwd=str(dest), capture_output=True, text=True, timeout=3600)
    if progress:
        progress(1.0)
    return "rpm2cpio+cpio"


def _unpack_deb(archive: Path, dest: Path, progress=None) -> str:
    """dpkg-deb -x ile DEB paketini açar."""
    dest.mkdir(parents=True, exist_ok=True)
    dpkg_deb = shutil.which("dpkg-deb")
    if not dpkg_deb:
        raise RuntimeError("DEB açmak için dpkg-deb gerekli (apt: dpkg).")
    done = subprocess.run(["dpkg-deb", "-x", str(archive), str(dest)],
                           capture_output=True, text=True, timeout=3600)
    if done.returncode != 0:
        raise RuntimeError(f"DEB açılamadı: {(done.stderr or done.stdout).strip()[:300]}")
    if progress:
        progress(1.0)
    return "dpkg-deb"


# --------------------------------------------------------------------------- #
# 4. Uçtan uca dönüşüm
# --------------------------------------------------------------------------- #

def convert(archive: Path, base: Path, name: str = "", progress=None,
            message=log) -> App:
    """Arşivi kurulum klasörüne açar ve kurulmaya hazır App nesnesi döndürür."""
    started = time.time()
    archive = archive.expanduser().resolve()
    if not archive.is_file():
        raise FileNotFoundError(f"dosya bulunamadı: {archive}")
    stem = archive_stem(archive)

    if has_suffix(archive, BARE_SUFFIXES) and not has_suffix(archive, ARCHIVE_SUFFIXES):
        # Tek dosya sıkıştırılmış (.gz/.xz/.bz2/.zst): önce sök, sonra tek dosya gibi kur.
        started = time.time()
        bare_dir = _install_dir(base, slugify(archive_stem(archive)))
        bare_exe = _decompress_bare(archive, bare_dir)
        bare_exe.chmod(bare_exe.stat().st_mode | 0o755)
        bare_name = name or pretty_name(archive_stem(archive), bare_exe.stem)
        return App(archive=archive, install_dir=bare_dir, exe=bare_exe, name=bare_name,
                   slug=slugify(bare_name), categories=guess_categories(archive_stem(archive), bare_name),
                   single_file=True, size=bare_exe.stat().st_size, seconds=time.time() - started)

    if is_single_file_app(archive):
        # Tek dosyalık uygulama (AppImage/.run): açmaya gerek yok, şak diye biter.
        target = _install_dir(base, slugify(stem))
        target.mkdir(parents=True, exist_ok=True)
        exe = target / archive.name
        if progress:
            progress(0.2)
        shutil.copy2(archive, exe)
        exe.chmod(exe.stat().st_mode | 0o755)
        app_name = name or pretty_name(stem, exe.stem)
        if progress:
            progress(1.0)
        return App(archive=archive, install_dir=target, exe=exe, name=app_name,
                   slug=slugify(app_name), categories=guess_categories(stem, app_name),
                   single_file=True, size=exe.stat().st_size,
                   seconds=time.time() - started)

    if has_suffix(archive, (".flatpak", ".flatpakref")):
        # Flatpak: .flatpak tek dosya (commit) tutar, .flatpakref ise remote referansıdır.
        started = time.time()
        if has_suffix(archive, (".flatpakref",)):
            raise RuntimeError(f"'{archive.name}' bir Flatpak uygulama paketi/değil (flatpakref, remote referansı).")
        flat_dir = _install_dir(base, slugify(archive_stem(archive)))
        flat_exe = flat_dir / archive.name
        flat_exe.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive, flat_exe)
        flat_exe.chmod(flat_exe.stat().st_mode | 0o755)
        flat_name = name or pretty_name(archive_stem(archive), archive.stem)
        return App(archive=archive, install_dir=flat_dir, exe=flat_exe, name=flat_name,
                   slug=slugify(flat_name), categories=guess_categories(archive_stem(archive), flat_name),
                   single_file=True, size=flat_exe.stat().st_size, seconds=time.time() - started)

    if has_suffix(archive, (".rpm", ".deb", ".src.rpm", ".zip", ".7z")):
        # RPM/DEB/ZIP/7Z: arşiv motoru yok; paket kutusundaki içerik aynı akışta açılır.
        started = time.time()
        target = _install_dir(base, slugify(stem))
        if has_suffix(archive, (".rpm", ".src.rpm")):
            engine = _unpack_rpm(archive, target, progress)
        elif has_suffix(archive, (".deb",)):
            engine = _unpack_deb(archive, target, progress)
        else:
            engine = unpack(archive, target, progress)
        scan_base = _root_dir(target)
        if progress:
            progress(1.0)
        info = scan_directory(scan_base)
        wanted = wanted_tokens(stem, info.root)
        exe_candidate = pick_exe(info, wanted, prefer_bin=True)
        icon_candidate = pick_icon(info, wanted)
        app_name = name or pretty_name(stem, Path(exe_candidate.path).name)
        slug = slugify(app_name)
        exe = scan_base / exe_candidate.path
        exe.chmod(exe.stat().st_mode | 0o755)
        icon: Path | None = None
        if icon_candidate is not None:
            icon = scan_base / icon_candidate.path
            if not icon.is_file():
                icon = _locate(scan_base, Path(icon_candidate.path).name)
        return App(archive=archive, install_dir=target, exe=exe, name=app_name,
                   slug=slug, icon=icon, categories=guess_categories(stem, app_name, info.root),
                   size=dir_size(scan_base), seconds=time.time() - started)

    message(f"[1/3] {archive.name} taranıyor...")
    info = scan(archive)
    if not info.exes:
        raise LookupError("arşivde çalıştırılabilir bir uygulama bulunamadı")

    free = free_bytes(base)
    if info.size_total * 2 > free:
        raise OSError(f"yeterli boş alan yok: gereken ~{human_size(info.size_total * 2)}")

    exe_candidate = pick_exe(info, wanted_tokens(stem, info.root))
    icon_candidate = pick_icon(info, wanted_tokens(stem, info.root))
    guess = exe_candidate.path[len(info.root) + 1:] if info.root else exe_candidate.path
    message(f"[1/3] çalıştırılabilir bulundu: {guess} "
            f"({info.file_count} dosya, ~{human_size(info.size_total)})")

    app_name = name or pretty_name(stem, Path(exe_candidate.path).name)
    slug = slugify(app_name)
    target = _install_dir(base, slug)
    message(f"[2/3] {target} içine açılıyor...")

    def _progress(value: float) -> None:
        if progress:
            progress(0.15 + 0.8 * value)

    engine = unpack(archive, target, _progress)
    root = target if info.root == "" else target / info.root.split("/")[0]
    if not root.is_dir():
        root = _root_dir(target)

    exe = root / exe_candidate.path[len(info.root) + 1:] if info.root else root / exe_candidate.path
    if not exe.is_file():
        found = _locate(root, Path(exe_candidate.path).name)
        if found is None:
            raise FileNotFoundError("açma sonrası çalıştırılabilir bulunamadı")
        exe = found
    exe.chmod(exe.stat().st_mode | 0o755)

    icon: Path | None = None
    if icon_candidate is not None:
        relative = icon_candidate.path[len(info.root) + 1:] if info.root else icon_candidate.path
        icon = root / relative
        if not icon.is_file():
            icon = _locate(root, Path(icon_candidate.path).name)

    message(f"[3/3] tamam ({engine} motoru)")
    return App(archive=archive, install_dir=target, exe=exe, name=app_name, slug=slug,
               icon=icon, categories=guess_categories(stem, app_name, info.root),
               size=dir_size(target), seconds=time.time() - started)


def _install_dir(base: Path, slug: str) -> Path:
    """Aynı addan ikinci bir sürüm varsa -2, -3 ekler."""
    candidate = base / slug
    if not candidate.exists():
        return candidate
    for index in range(2, 100):
        other = base / f"{slug}-{index}"
        if not other.exists():
            return other
    return base / f"{slug}-{int(time.time())}"


def _locate(root: Path, filename: str) -> Path | None:
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        if filename in filenames:
            found = Path(dirpath) / filename
            if not any(part.lower() in SKIP_DIRS for part in found.parts):
                return found
    return None


def _decompress_bare(archive: Path, dest: Path) -> Path:
    """Tek dosya sıkıştırılmış (.gz/.xz/.bz2/.zst) dosyayı çözer ve hedefe yazar."""
    dest.mkdir(parents=True, exist_ok=True)
    suffix = archive.suffix.lower()
    program_map = {".gz": ("gzip", "-dc"), ".xz": ("xz", "-dc"), ".bz2": ("bunzip2", "-c"),
                   ".zst": ("unzstd", "-c")}
    program, flag = program_map[suffix]
    program_path = shutil.which(program)
    if not program_path:
        raise RuntimeError(f"'{suffix}' açmak için {program} gerekli.")
    target = dest / archive.name
    with open(target, "wb") as handle:
        done = subprocess.run([program_path, flag, str(archive)], check=False,
                               stdout=handle, stderr=subprocess.PIPE, timeout=1800)
    if done.returncode != 0:
        raise RuntimeError(f"'{archive.name}' açılamadı: {(done.stderr or b'').decode(errors='replace').strip()[:300]}")
    return target

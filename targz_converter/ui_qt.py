"""Qt (PySide6) arayüzü: sürükle-bırak penceresi ve işlem sonu seçimi.

Sistemde PySide6 varsa bu arayüz kullanılır; yoksa ui_tk.py devreye girer.
İşler ayrı iş parçacığında (Thread) yürür, pencere hiç beklemez.
"""

from __future__ import annotations

import time

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QTextEdit,
    QVBoxLayout, QWidget,
)

from . import core, desktop

WINDOW_TITLE = "Targz Converter — arşivi sürükle, uygulama olsun"


def _app_icon_path() -> Path | None:
    """Kendi ikonumuzu bul: önce repo/assets, sonra kurulu ikon dizinleri."""
    candidates: list[Path] = []
    candidates.append(Path(__file__).resolve().parents[2] / "assets" / "targz-converter.png")
    data = Path.home() / ".local" / "share" / "targz-converter"
    candidates.append(data / "assets" / "targz-converter.png")
    for size in ("256x256", "512x512", "scalable"):
        candidates.append(Path.home() / ".local" / "share" / "icons" / "hicolor" / size / "apps" / "com.github.colgecen.TargzConverter.png")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None

def _is_supported(path: Path) -> bool:
    return core.is_supported(path)


class Worker(QThread):
    """Dönüşümü arka planda yürütür; arayüz akıcı kalır."""

    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, archive: Path, base: Path, name: str) -> None:
        super().__init__()
        self.archive, self.base, self.name = archive, base, name

    def run(self) -> None:  # noqa: D102 (QThread arayüzü)
        try:
            app = core.convert(
                self.archive, self.base, self.name,
                progress=lambda value: self.progress.emit(int(value * 100), ""),
                message=lambda text: self.progress.emit(0, text),
            )
            self.finished.emit(app)
        except Exception as exc:  # kullanıcıya kısa ve anlaşılır mesaj yeter
            self.failed.emit(str(exc) or exc.__class__.__name__)


class ResultDialog(QDialog):
    """İşlem bitince çıkan son pencere: iki seçenek ve TAMAM."""

    def __init__(self, parent: QWidget, app: core.App) -> None:
        super().__init__(parent)
        self.app = app
        self.written: dict[str, Path] = {}
        self._shown_at: float = 0.0
        self.setWindowTitle(f"{app.name} hazır")
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        info = QLabel(f"<b>{app.name}</b> hazır<br/>"
                      f"<span style='color:#7f8c8d'>{core.human_size(app.size)} · "
                      f"{app.seconds:.1f} sn · {app.exe}</span>")
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setWordWrap(True)
        layout.addWidget(info)

        self.autostart = QCheckBox("Başlangıçta çalıştır (oturum açınca kendiliğinden açılsın)")
        self.desktop = QCheckBox("Masaüstüne kısayol oluştur")
        self.desktop.setChecked(True)
        layout.addWidget(self.autostart)
        layout.addWidget(self.desktop)

        note = QLabel("İkisi de seçilmezse uygulama yalnızca Uygulamalar menüsünde görünür.")
        note.setStyleSheet("color:#7f8c8d;")
        layout.addWidget(note)

        buttons = QHBoxLayout()
        self.run_now = QPushButton("Şimdi Çalıştır")
        self.close_button = QPushButton("TAMAM")
        self.close_button.setDefault(True)
        buttons.addStretch(1)
        buttons.addWidget(self.run_now)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.run_now.clicked.connect(lambda: self._finish(launch=True))
        self.close_button.clicked.connect(lambda: self._finish(launch=False))

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self._shown_at = time.monotonic()
        # Pencere açılır açılmaz farenin eski tıklaması yanlışlıkla
        # düğmeye basmasın diye düğmeleri kısa bir süre devre dışı bırak.
        self.run_now.setEnabled(False)
        self.close_button.setEnabled(False)
        QTimer.singleShot(300, self._enable_buttons)

    def _enable_buttons(self) -> None:
        self.run_now.setEnabled(True)
        self.close_button.setEnabled(True)

    def _finish(self, launch: bool = False) -> None:
        """Seçilen kısayolları yazar, istenirse uygulamayı başlatır."""
        # Pencere açılır açılmaz oluşan sahte tıklamayı yoksay.
        if time.monotonic() - getattr(self, "_shown_at", 0.0) < 0.4:
            return
        self.written = desktop.install(
            self.app, desktop=self.desktop.isChecked(),
            autostart=self.autostart.isChecked())
        if launch:
            desktop.launch(self.app)
        self.accept()



class MultiWorker(QThread):
    """Birden fazla arşivi sırayla dönüştürür."""

    progress = Signal(int, str)
    app_ready = Signal(int, object)
    app_failed = Signal(int, str)
    all_done = Signal(list, list)

    def __init__(self, archives: list[Path], base: Path, name: str) -> None:
        super().__init__()
        self.archives, self.base, self.name = archives, base, name

    def run(self) -> None:  # noqa: D102
        apps: list[core.App] = []
        failures: list[tuple[str, str]] = []
        total = len(self.archives)
        for index, archive in enumerate(self.archives):
            prefix = f"{index + 1}/{total}"
            self.progress.emit(index, f"{prefix}: {archive.name} hazırlanıyor…")
            try:
                app = core.convert(
                    archive, self.base, self.name,
                    progress=lambda value, i=index, a=archive, p=prefix:
                        self.progress.emit(i, f"{p}: {a.name} … {int(value * 100)}%"),
                    message=lambda text, i=index, p=prefix:
                        self.progress.emit(i, f"{p}: {text}"),
                )
                apps.append(app)
                self.app_ready.emit(index, app)
            except Exception as exc:  # noqa: BLE001
                failures.append((archive.name, str(exc)))
                self.app_failed.emit(index, str(exc))
        self.all_done.emit(apps, failures)


class Window(QWidget):
    """Tek satırlık sürükle-bırak alanı, ilerleme çubuğu ve günlük."""

    def __init__(self, base: Path) -> None:
        super().__init__()
        self.base = base
        self.worker: Worker | None = None
        self.multi_worker: MultiWorker | None = None
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(640, 300)
        self.setAcceptDrops(True)
        icon_path = _app_icon_path()
        if icon_path is not None:
            self.setWindowIcon(QIcon(str(icon_path)))

        layout = QVBoxLayout(self)
        self.drop = QLabel("Buraya bir .tar.gz dosyası bırak\n"
                           "veya buraya tıklayıp kendin seç")
        self.drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop.setMinimumHeight(140)
        self.drop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.drop.setStyleSheet(
            "QLabel{border: 2px dashed #4a90d9; border-radius: 12px;"
            "background:#f4f8fd; color:#2c3e50; font-size: 15px; padding: 12px;}"
            "QLabel:hover{background:#e8f1fb; border-color:#2c6faf;}")
        self.drop.mousePressEvent = lambda _event: self._choose()
        layout.addWidget(self.drop)

        row = QHBoxLayout()
        self.pick = QPushButton("Dosya seç…")
        self.pick.clicked.connect(self._choose)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Uygulama adı (boş bırakırsan kendimiz buluruz)")
        row.addWidget(self.pick)
        row.addWidget(self.name, 1)
        layout.addLayout(row)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)

        self.status = QLabel("Hazır.")
        self.status.setStyleSheet("color:#7f8c8d;")
        layout.addWidget(self.status)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(90)
        self.log.setPlaceholderText("İşlem kaydı burada görünür")
        layout.addWidget(self.log)

    # ---------------- sürükle-bırak ---------------- #

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt imzası)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop.setStyleSheet(self.drop.styleSheet() +
                                    "QLabel{border-color:#27ae60; background:#eafaf1;}")

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.drop.setStyleSheet(self.drop.styleSheet())

    def dropEvent(self, event) -> None:  # noqa: N802
        self.dragLeaveEvent(event)
        paths = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if _is_supported(path):
                paths.append(path)
        if len(paths) == 1:
            self.convert(paths[0])
        elif len(paths) > 1:
            self.convert_many(paths)
        elif paths == [] and event.mimeData().urls():
            # desteklenmeyen dosya bırakıldı
            path = Path(event.mimeData().urls()[0].toLocalFile())
            self.status.setText(f"{path.name} desteklenmiyor "
                                f"(.tar.gz, .tgz, .tar.xz, .AppImage olur)")

    def _on_multi_progress(self, _index: int, message: str) -> None:
        self.log.setPlainText(message)
        self.status.setText(message)

    def _on_multi_failed(self, _index: int, message: str) -> None:
        self.log.setPlainText(f"✗ {message}")

    def _on_multi_done(self, apps: list, failures: list) -> None:
        self.bar.setRange(0, 100)
        self.bar.setValue(100)
        self.status.setText(f"{len(apps)} uygulama hazır")
        self.log.clear()
        dialog = MultiResultDialog(self, apps, failures)
        dialog.exec()
        self.log.clear()
        self.bar.setValue(0)
        self.status.setText("Hazır — yeni bir arşiv sürükle veya seç.")
        self.multi_worker = None

    def _choose(self) -> None:
        patterns = " ".join(f"*.{suffix.lstrip('.')}" for suffix in sorted(set(core.SUPPORTED_SUFFIXES)))
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Arşivleri seç", str(core.download_dir()),
            f"Sıkıştırılmış uygulamalar ({patterns})",
        )
        paths = [Path(name) for name in filenames if _is_supported(Path(name))]
        if not paths:
            return
        if len(paths) == 1:
            self.convert(paths[0])
        else:
            self.convert_many(paths)

    # ---------------- iş akışı ---------------- #

    def convert(self, archive: Path) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.status.setText("Bir iş zaten sürüyor, birazdan sıraya girsin.")
            return
        self.status.setText(f"{archive.name} hazırlanıyor…")
        self.bar.setRange(0, 0)
        self.log.setPlainText(f"→ {archive.name}")
        self.worker = Worker(archive, self.base, self.name.text().strip())
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def convert_many(self, archives: list[Path]) -> None:
        if (self.worker is not None and self.worker.isRunning()) or \
                (self.multi_worker is not None and self.multi_worker.isRunning()):
            self.status.setText("Bir iş zaten sürüyor, birazdan sıraya girsin.")
            return
        if not archives:
            return
        if len(archives) == 1:
            self.convert(archives[0])
            return
        self.status.setText(f"{len(archives)} uygulama hazırlanıyor…")
        self.bar.setRange(0, 0)
        self.log.setPlainText(f"{len(archives)} uygulama hazırlanıyor…")
        self.multi_worker = MultiWorker(archives, self.base, self.name.text().strip())
        self.multi_worker.progress.connect(self._on_multi_progress)
        self.multi_worker.app_failed.connect(self._on_multi_failed)
        self.multi_worker.all_done.connect(self._on_multi_done)
        self.multi_worker.start()

    def _on_progress(self, percent: int, message: str) -> None:
        if message:
            # Her adımı aynı satırda güncelleyelim (1/3, 2/3, 3/3 → ✓).
            self.log.setPlainText(message)
            self.status.setText(message)
        elif percent:
            self.bar.setRange(0, 100)
            self.bar.setValue(percent)

    def _on_finished(self, app: core.App) -> None:
        self.bar.setRange(0, 100)
        self.bar.setValue(100)
        self.status.setText(f"{app.name} hazır ({app.seconds:.1f} sn)")
        self.log.setPlainText(f"✓ {app.name} → {app.exe}")
        dialog = ResultDialog(self, app)
        dialog.exec()
        for label, path in dialog.written.items():
            self.log.append(f"  {label}: {path}")
        self.name.clear()
        # Sonuç penceresi kapandıktan sonra durum ve günlük sıfırlansın.
        self.log.clear()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.status.setText("Hazır — yeni bir arşiv sürükle veya seç.")

    def _on_failed(self, message: str) -> None:
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.status.setText("Olmadı.")
        self.log.setPlainText(f"✗ hata: {message}")



class MultiResultDialog(QDialog):
    """Birden fazla dönüştürme bittikten sonra toplu seçim ekranı."""

    def __init__(self, parent: QWidget, apps: list, failures: list) -> None:
        super().__init__(parent)
        self.apps = apps
        self.failures = failures
        self.index = 0
        self._states: dict[int, dict[str, bool]] = {}
        self._shown_at: float = 0.0
        self.setWindowTitle("Toplu dönüşüm sonucu")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        if failures:
            fail_text = "Yüklenemeyenler:\n" + "\n".join(
                f"  • {name}: {err}" for name, err in failures)
            fail_label = QLabel(fail_text)
            fail_label.setStyleSheet("color:#c0392b;")
            fail_label.setWordWrap(True)
            layout.addWidget(fail_label)

        self.info = QLabel()
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        self.desktop_cb = QCheckBox("Masaüstüne kısayol oluştur")
        self.desktop_cb.setChecked(True)
        self.autostart_cb = QCheckBox("Başlangıçta çalıştır")
        self.run_cb = QCheckBox("Şimdi çalıştır")
        layout.addWidget(self.desktop_cb)
        layout.addWidget(self.autostart_cb)
        layout.addWidget(self.run_cb)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Geri")
        self.next_btn = QPushButton("İleri ▶")
        self.all_btn = QPushButton("Hepsini kısayol oluştur")
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        nav.addWidget(self.all_btn)
        layout.addLayout(nav)

        bottom = QHBoxLayout()
        self.ok_btn = QPushButton("TAMAM")
        self.ok_btn.setDefault(True)
        bottom.addStretch(1)
        bottom.addWidget(self.ok_btn)
        layout.addLayout(bottom)

        self.prev_btn.clicked.connect(self._prev)
        self.next_btn.clicked.connect(self._next)
        self.all_btn.clicked.connect(self._all_shortcuts)
        self.ok_btn.clicked.connect(self._finish)

        self._update_view()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self._shown_at = time.monotonic()

    def _save_state(self) -> None:
        self._states[self.index] = {
            "desktop": self.desktop_cb.isChecked(),
            "autostart": self.autostart_cb.isChecked(),
            "run": self.run_cb.isChecked(),
        }

    def _update_view(self) -> None:
        if not self.apps:
            self.info.setText("Başarılı uygulama yok.")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.all_btn.setEnabled(False)
            self.ok_btn.setEnabled(False)
            return
        app = self.apps[self.index]
        self.info.setText(
            f"<b>{app.name}</b>  ({self.index + 1}/{len(self.apps)})<br/>"
            f"<span style='color:#7f8c8d'>{app.exe}</span>")
        self.prev_btn.setEnabled(self.index > 0)
        self.next_btn.setEnabled(self.index < len(self.apps) - 1)
        state = self._states.get(self.index, {
            "desktop": True, "autostart": False, "run": False})
        self.desktop_cb.setChecked(state["desktop"])
        self.autostart_cb.setChecked(state["autostart"])
        self.run_cb.setChecked(state["run"])

    def _prev(self) -> None:
        self._save_state()
        if self.index > 0:
            self.index -= 1
            self._update_view()

    def _next(self) -> None:
        self._save_state()
        if self.index < len(self.apps) - 1:
            self.index += 1
            self._update_view()

    def _all_shortcuts(self) -> None:
        if time.monotonic() - self._shown_at < 0.4:
            return
        reply = QMessageBox.question(
            self, "Onay", "Tüm uygulamalar için kısayol oluşturulsun mu?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        for app in self.apps:
            desktop.install(app, desktop=True, autostart=False)
        self.accept()

    def _finish(self) -> None:
        if time.monotonic() - self._shown_at < 0.4:
            return
        self._save_state()
        for i, app in enumerate(self.apps):
            state = self._states.get(i, {
                "desktop": True, "autostart": False, "run": False})
            written = desktop.install(
                app, desktop=state["desktop"], autostart=state["autostart"])
            if state["run"]:
                desktop.launch(app)
        self.accept()



def run(base: Path, files: list[Path] | None = None) -> int:
    """Pencereyi açar; dosya verildiyse açılışta hemen dönüştürür."""
    application = QApplication.instance() or QApplication([])
    window = Window(base)
    window.show()
    for path in files or []:
        if _is_supported(path):
            window.convert(path)
    return application.exec()

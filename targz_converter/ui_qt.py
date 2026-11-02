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
    QLineEdit, QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget,
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


class Window(QWidget):
    """Tek satırlık sürükle-bırak alanı, ilerleme çubuğu ve günlük."""

    def __init__(self, base: Path) -> None:
        super().__init__()
        self.base = base
        self.worker: Worker | None = None
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(640, 300)
        self.setAcceptDrops(True)
        icon_path = _app_icon_path()
        if icon_path is not None:
            self.setWindowIcon(QIcon(str(icon_path)))

        layout = QVBoxLayout(self)
        self.drop = QLabel("Buraya bir .tar.gz dosyası bırak\n"
                           "veya aşağıdan kendin seç")
        self.drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop.setMinimumHeight(140)
        self.drop.setStyleSheet(
            "QLabel{border: 2px dashed #4a90d9; border-radius: 12px;"
            "background:#f4f8fd; color:#2c3e50; font-size: 15px; padding: 12px;}"
            "QLabel:hover{background:#e8f1fb; border-color:#2c6faf;}")
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
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if _is_supported(path):
                self.convert(path)
            else:
                self.status.setText(f"{path.name} desteklenmiyor "
                                    f"(.tar.gz, .tgz, .tar.xz, .AppImage olur)")

    def _choose(self) -> None:
        patterns = " ".join(f"*.{suffix.lstrip('.')}" for suffix in sorted(set(core.SUPPORTED_SUFFIXES)))
        filename, _ = QFileDialog.getOpenFileName(
            self, "Arşivi seç", str(core.download_dir()),
            f"Sıkıştırılmış uygulamalar ({patterns})",
        )
        if filename:
            self.convert(Path(filename))

    # ---------------- iş akışı ---------------- #

    def convert(self, archive: Path) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.status.setText("Bir iş zaten sürüyor, birazdan sıraya girsin.")
            return
        self.status.setText(f"{archive.name} hazırlanıyor…")
        self.bar.setRange(0, 0)
        self.log.append(f"→ {archive.name}")
        self.worker = Worker(archive, self.base, self.name.text().strip())
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_progress(self, percent: int, message: str) -> None:
        if message:
            self.log.append(message)
            self.status.setText(message)
        elif percent:
            self.bar.setRange(0, 100)
            self.bar.setValue(percent)

    def _on_finished(self, app: core.App) -> None:
        self.bar.setRange(0, 100)
        self.bar.setValue(100)
        self.status.setText(f"{app.name} hazır ({app.seconds:.1f} sn)")
        self.log.append(f"✓ {app.name} → {app.exe}")
        dialog = ResultDialog(self, app)
        dialog.exec()
        for label, path in dialog.written.items():
            self.log.append(f"  {label}: {path}")
        self.name.clear()

    def _on_failed(self, message: str) -> None:
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.status.setText("Olmadı.")
        self.log.append(f"✗ hata: {message}")


def run(base: Path, files: list[Path] | None = None) -> int:
    """Pencereyi açar; dosya verildiyse açılışta hemen dönüştürür."""
    application = QApplication.instance() or QApplication([])
    window = Window(base)
    window.show()
    for path in files or []:
        if _is_supported(path):
            window.convert(path)
    return application.exec()

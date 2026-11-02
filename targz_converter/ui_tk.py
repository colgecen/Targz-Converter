"""Yedek arayüz: PySide6 bulunmazsa tkinter devreye girer (standart kütüphane).

Sürükle-bırak Tk'de ek bir eklenti (tkdnd) istediği için burada dosya düğmesi
kullanılır; sağ tık menüsü ve komut satırı zaten aynı işi görür.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from . import core, desktop

ACCEPTED: list[tuple[str, str]] = [
    ("Sıkıştırılmış uygulamalar", f"*.{suffix.lstrip('.')}")
    for suffix in sorted(set(core.SUPPORTED_SUFFIXES))
]


class Window:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.jobs: queue.Queue = queue.Queue()
        self.events: queue.Queue = queue.Queue()
        self.busy = False

        self.root = tk.Tk()
        self.root.title("Targz Converter — arşivi seç, uygulama olsun")
        self.root.geometry("560x290")
        self.root.minsize(480, 250)

        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)

        banner = ttk.Label(frame, text=".tar.gz arşivini seç ya da pencereye bırakmak\n"
                                      "için sağ tık menüsünü kullan",
                           font=("Sans", 12, "bold"), justify="center", anchor="center")
        banner.pack(fill="x", pady=(0, 10))

        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Button(row, text="Dosya seç…", command=self.choose).pack(side="left")
        self.name = ttk.Entry(row)
        self.name.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.name.insert(0, "")

        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(14, 6))

        self.status = ttk.Label(frame, text="Hazır.")
        self.status.pack(fill="x")

        self.log = tk.Text(frame, height=5, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, pady=(8, 0))

        self.root.after(120, self._pump)

    # ---------------- iş akışı ---------------- #

    def choose(self) -> None:
        filename = filedialog.askopenfilename(
            title="Arşivi seç", initialdir=str(core.download_dir()),
            filetypes=ACCEPTED)
        if filename:
            self.convert(Path(filename))

    def convert(self, archive: Path) -> None:
        self.jobs.put(archive)
        self._pump()

    def _pump(self) -> None:
        """Kuyruktaki işleri ve iş parçacığından gelen mesajları işler."""
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind, payload = event
            if kind == "log":
                self._write(payload)
            elif kind == "status":
                self.status.config(text=payload)
            elif kind == "progress":
                self.progress.config(value=payload)
            elif kind == "done":
                self.busy = False
                self.progress.config(value=100)
                ResultDialog(self.root, payload, self._write)
            elif kind == "fail":
                self.busy = False
                self.progress.config(value=0)
                self.status.config(text="Olmadı.")
                self._write(f"hata: {payload}")

        if not self.busy:
            try:
                archive = self.jobs.get_nowait()
            except queue.Empty:
                pass
            else:
                self.busy = True
                self.progress.config(value=0)
                self.status.config(text=f"{archive.name} hazırlanıyor…")
                self._write(f"→ {archive.name}")
                threading.Thread(target=self._work, args=(archive,), daemon=True).start()

        self.root.after(120, self._pump)

    def _work(self, archive: Path) -> None:
        try:
            app = core.convert(
                archive, self.base, self.name.get().strip(),
                progress=lambda value: self.events.put(("progress", value * 100)),
                message=lambda text: self.events.put(("log", text)),
            )
            self.events.put(("status", f"{app.name} hazır ({app.seconds:.1f} sn)"))
            self.events.put(("done", app))
        except Exception as exc:
            self.events.put(("fail", str(exc) or exc.__class__.__name__))

    def _write(self, text: str) -> None:
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def run(self) -> int:
        self.root.mainloop()
        return 0


class ResultDialog(tk.Toplevel):
    """İşlem sonundaki iki seçenekli pencere (Qt arayüzüyle aynı davranış)."""

    def __init__(self, parent, app: core.App, report) -> None:
        super().__init__(parent)
        self.app, self.report = app, report
        self.title(f"{app.name} hazır")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grab_set()

        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"{app.name} hazır", font=("Sans", 12, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{core.human_size(app.size)} · {app.seconds:.1f} sn\n{app.exe}"
                ).pack(anchor="w", pady=(0, 10))

        self.autostart = tk.BooleanVar(value=False)
        self.desktop = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Başlangıçta çalıştır", variable=self.autostart).pack(anchor="w")
        ttk.Checkbutton(frame, text="Masaüstüne kısayol oluştur", variable=self.desktop).pack(anchor="w")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Şimdi Çalıştır",
                   command=lambda: self.finish(run=True)).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="TAMAM",
                   command=lambda: self.finish(run=False)).pack(side="right")

        self.wait_window()

    def finish(self, run: bool = False) -> None:
        written = desktop.install(self.app, desktop=self.desktop.get(),
                                  autostart=self.autostart.get())
        for label, path in written.items():
            self.report(f"  {label}: {path}")
        if run:
            desktop.launch(self.app)
        self.destroy()


def run(base: Path, files: list[Path] | None = None) -> int:
    window = Window(base)
    for path in files or []:
        window.convert(path)
    return window.run()

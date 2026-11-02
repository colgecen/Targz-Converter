"""Targz Converter: sıkıştırılmış arşivleri tek sürüklemede Linux uygulamasına çevirir.

Paket üç katmana ayrılır:
    core      arşivi tek geçişte tarar, açar, çalıştırılabilir ve ikon bulur
    desktop   .desktop dosyası üretir, masaüstü / uygulamalar menüsüne kurar
    install   aracın kendisini sisteme kurar (çalıştırıcı, simge, sağ tık menüsü)
    ui        Qt (PySide6) sürükle-bırak arayüzü ve tkinter yedeği

Harici bağımlılık yoktur: çekirdek yalnızca Python standart kütüphanesini
kullanır. Arayüz için PySide6 varsa o, yoksa tkinter devreye girer.
"""

__version__ = "1.0.0"
__all__ = ["core", "desktop", "install", "ui"]

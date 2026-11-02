# Targz Converter

Linux'ta `.tar.gz` olarak dağıtılan programların kurulumu yoktur: açarsın, klasörün
içinde ne yapıştıracağını bilemezsin, masaüstünde de bir kısayol olmaz. Bu araç o
adımı tek harekete indirir: **arşivi pencereye sürüklersin, program uygulama
olur.**

Arşiv `~/.local/share/Applications` altına açılır, içindeki gerçek
çalıştırılabilir bulunur, simgesi temaya yerleştirilir ve Linux'un standart
`.desktop` kısayolu yazılır. İşin sonunda iki seçenek sorulur — *başlangıçta
çalıştır* ve *masaüstüne kısayol oluştur* — **TAMAM** dediğinde iş biter.

## Ne yapıyor

| Adım | Nasıl |
| --- | --- |
| Arşivi bul | Sürükle-bırak, `Dosya seç…`, sağ tık menüsü veya komut satırı |
| İçindekileri öğren | Akışlı tarama (`tarfile` `r|*`): arşiv **bir kez** okunur |
| Aç | Mümkünse sistem `tar`ı, `pigz` varsa paralel açma; yoksa Python motoru |
| Programı bul | İzin biti + `ELF` imzası + ad benzerliğine göre puanlama |
| Simgesini bul | `.svg` / `.png` / `.ico` adayları; `.ico` gerekirse PNG'ye çevrilir |
| Kısayolu yaz | `~/.local/share/applications`, isterse masaüstü ve `~/.config/autostart` |

Hız için üç karar: arşivi iki kere okumamak (tarama ve seçim tek geçişte),
açma işini mümkünse `tar`/`pigz`e devretmek ve `.desktop` dosyasını
olduğu gibi bırakmak (Python'un kendi `tarfile` döngüsü sadece yedek).
Küçük arşivler milisaniyede, 35 MB'lık TeamViewer arşivi ~0,1 saniyede biter.

## Kurulum

```bash
git clone https://github.com/colgecen/Targz-Converter.git
cd Targz-Converter
python3 install.py            # istersen --masaustune ile kendi kısayolunu da ekle
```

Root gerekmez; her şey senin kullanıcı dizinlerine yazılır:

```text
~/.local/share/targz-converter/       programın kopyası
~/.local/bin/targz-converter          komut satırı giriş
~/.local/share/applications/          Uygulamalar menüsü kısayolu
~/.local/share/icons/hicolor/         simge
~/.local/share/kio/servicemenus/      Dolphin sağ tık menüsü (KDE)
~/.local/share/nautilus/scripts/      Nautilus betiği (GNOME)
```

Geri almak için: `python3 install.py --kaldir`

## Kullanım

**Arayüz.** `targz-converter` komutunu çalıştır ya da uygulamalar menüsünden aç;
`.tar.gz`, `.tgz`, `.tar.xz`, `.tar.zst`, `.tar.bz2`, `.tar`, `.AppImage`, `.rpm` veya
`.deb` dosyasını pencereye bırak. İstersen dönüşmeden önce adını değiştirebilirsin.

**Sağ tık.** Dolphin'de arşive sağ tık → **Targz Converter ile uygulamaya
çevir…** (arayüzü açar) veya **Çevir ve uygulamayı aç** (sormadan kurar, açar).
GNOME/Nautilus'ta aynı komut *Scripts* menüsündedir.

**Komut satırı.**

```bash
targz-converter                              # arayüzü aç
targz-converter indirilen/uygulama.tar.gz    # arayüzde dosya hazır gelsin
targz-converter --donustur uygulama.tar.gz   # arayüz yok, hemen kurar
targz-converter --donustur --ac uygulama.tgz # kurar ve açar
targz-converter --donustur --masaustune-yok x.tar.gz   # kısayol masaüstüne düşmesin
targz-converter --donustur --baslangicta x.tar.gz      # oturum açılınca çalışsın
targz-converter --hedef ~/Applications --ad "Stüdyo" x.tar.gz
```

## Nereye ne yazılıyor

| Konum | İçin |
| --- | --- |
| `~/.local/share/Applications/<ad>/` | Programın açıldığı yer |
| `~/.local/share/applications/<ad>.desktop` | Uygulamalar menüsü |
| `~/Masaüstü/<ad>.desktop` | Masaüstü kısayolu (seçersen) |
| `~/.config/autostart/<ad>.desktop` | Otomatik başlatma (seçersen) |
| `~/.local/share/icons/hicolor/…` | Uygulamanın simgesi |

Aynı adda bir şey zaten varsa `--2`, `--3` eklenir; hiçbir şeyin üstüne yazılmaz.
Masaüstüne yazılan kısayola Plasma'nın "güven" etiketi de verilir; yine de tek
seferlik bir onay çıkarsa **Güven** demek yeterlidir.

## Gereksinimler

- Python 3.9+ ve `tar` (her Linux'ta var). `pigz` varsa otomatik kullanılır.
- Arayüz için **PySide6** tercih edilir; yoksa otomatik olarak standart
  kütüphanedeki **tkinter** arayüzüne düşer. Ek bir `pip install` gerekmez.
- Simge dönüşümünde (`.ico` → `.png`) Pillow varsa kullanılır, yoksa genel
  simge kullanılır.

## Depo düzeni

```text
targz2app.py            giriş noktası (python3 targz2app.py)
install.py              sisteme kurma betiği
assets/                 araç simgesi
targz_converter/
    core.py             tarama, açma, çalıştırılabilir ve ikon bulma
    desktop.py          .desktop üretimi, masaüstü/menü/otomatik başlatma
    install.py          kendini kurma, sağ tık menüleri, kaldırma
    ui_qt.py            Qt sürükle-bırak arayüzü ve seçim penceresi
    ui_tk.py            tkinter yedeği
    __main__.py         komut satırı ve arayüz seçimi
```

## Lisans

[MIT](LICENSE)

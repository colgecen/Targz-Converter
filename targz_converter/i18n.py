"""Çok dilli destek: sistem dilini algılar ve çeviri döndürür."""

from __future__ import annotations

import os
from typing import Any

SUPPORTED = ("tr", "en", "es", "it", "fr", "ar", "pt")


def detect_language() -> str:
    """LANG/LC_ALL üzerinden sistem dilini algılar."""
    raw = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    code = raw.split(".")[0].replace("_", "-").lower()
    short = code.split("-")[0]
    if short in SUPPORTED:
        return short
    # Bazı dağıtımlar tr_TR, en_US gibi; eşleştir.
    for lang in SUPPORTED:
        if code.startswith(lang):
            return lang
    return "en"


_CURRENT = detect_language()


def set_language(lang: str) -> None:
    global _CURRENT
    if lang in SUPPORTED:
        _CURRENT = lang


def get_language() -> str:
    return _CURRENT


def t(key: str, **kwargs: Any) -> str:
    """Çeviri döndürür; bulunamazsa anahtarın kendisi."""
    value = STRINGS.get(key, {}).get(_CURRENT)
    if value is None:
        value = STRINGS.get(key, {}).get("en", key)
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value
    return value


STRINGS: dict[str, dict[str, str]] = {
    # --- UI ---
    "app_title": {
        "tr": "Targz Converter", "en": "Targz Converter", "es": "Targz Converter",
        "it": "Targz Converter", "fr": "Targz Converter", "ar": "Targz Converter",
        "pt": "Targz Converter",
    },
    "drop_label": {
        "tr": "Buraya bir .tar.gz dosyası bırak\nveya buraya tıklayıp kendin seç",
        "en": "Drop a .tar.gz file here\nor click here to choose one",
        "es": "Suelta un archivo .tar.gz aquí\no haz clic para elegir uno",
        "it": "Trascina qui un file .tar.gz\no clicca per sceglierne uno",
        "fr": "Déposez un fichier .tar.gz ici\nou cliquez pour en choisir un",
        "ar": "اسحب ملف .tar.gz هنا\nأو انقر لاختيار ملف",
        "pt": "Solte um arquivo .tar.gz aqui\nou clique para escolher um",
    },
    "pick_button": {
        "tr": "Dosya seç…", "en": "Choose file…", "es": "Elegir archivo…",
        "it": "Scegli file…", "fr": "Choisir un fichier…", "ar": "اختر ملف…",
        "pt": "Escolher arquivo…",
    },
    "name_placeholder": {
        "tr": "Uygulama adı (boş bırakırsan kendimiz buluruz)",
        "en": "App name (leave empty to auto-detect)",
        "es": "Nombre de la app (vacío = detectar automáticamente)",
        "it": "Nome app (vuoto = rilevamento automatico)",
        "fr": "Nom de l'app (vide = détection automatique)",
        "ar": "اسم التطبيق (فارغ = اكتشاف تلقائي)",
        "pt": "Nome do app (vazio = detectar automaticamente)",
    },
    "status_ready": {
        "tr": "Hazır — yeni bir arşiv sürükle veya seç.",
        "en": "Ready — drop or choose an archive.",
        "es": "Listo — arrastra o elige un archivo.",
        "it": "Pronto — trascina o scegli un archivio.",
        "fr": "Prêt — déposez ou choisissez une archive.",
        "ar": "جاهز — اسحب أو اختر أرشيفاً.",
        "pt": "Pronto — solte ou escolha um arquivo.",
    },
    "status_busy": {
        "tr": "Bir iş zaten sürüyor, birazdan sıraya girsin.",
        "en": "A job is already running, please wait.",
        "es": "Ya hay un trabajo en curso, espera un momento.",
        "it": "C'è già un lavoro in corso, attendi.",
        "fr": "Un travail est déjà en cours, patientez.",
        "ar": "هناك مهمة قيد التشغيل، انتظر.",
        "pt": "Já há um trabalho em andamento, aguarde.",
    },
    "status_failed": {
        "tr": "Olmadı.", "en": "Failed.", "es": "Falló.", "it": "Fallito.",
        "fr": "Échec.", "ar": "فشل.", "pt": "Falhou.",
    },
    "log_start": {
        "tr": "→ {name}", "en": "→ {name}", "es": "→ {name}", "it": "→ {name}",
        "fr": "→ {name}", "ar": "→ {name}", "pt": "→ {name}",
    },
    "log_done": {
        "tr": "✓ {name} → {exe}", "en": "✓ {name} → {exe}", "es": "✓ {name} → {exe}",
        "it": "✓ {name} → {exe}", "fr": "✓ {name} → {exe}", "ar": "✓ {name} → {exe}",
        "pt": "✓ {name} → {exe}",
    },
    "log_error": {
        "tr": "✗ hata: {msg}", "en": "✗ error: {msg}", "es": "✗ error: {msg}",
        "it": "✗ errore: {msg}", "fr": "✗ erreur : {msg}", "ar": "✗ خطأ: {msg}",
        "pt": "✗ erro: {msg}",
    },
    "unsupported": {
        "tr": "{name} desteklenmiyor (.tar.gz, .tgz, .tar.xz, .AppImage olur)",
        "en": "{name} is not supported (.tar.gz, .tgz, .tar.xz, .AppImage)",
        "es": "{name} no es compatible (.tar.gz, .tgz, .tar.xz, .AppImage)",
        "it": "{name} non è supportato (.tar.gz, .tgz, .tar.xz, .AppImage)",
        "fr": "{name} n'est pas pris en charge (.tar.gz, .tgz, .tar.xz, .AppImage)",
        "ar": "{name} غير مدعوم (.tar.gz, .tgz, .tar.xz, .AppImage)",
        "pt": "{name} não é suportado (.tar.gz, .tgz, .tar.xz, .AppImage)",
    },
    "converting": {
        "tr": "{name} hazırlanıyor…", "en": "{name} is being prepared…",
        "es": "{name} se está preparando…", "it": "{name} in preparazione…",
        "fr": "{name} en préparation…", "ar": "جارٍ تجهيز {name}…",
        "pt": "{name} sendo preparado…",
    },
    "file_dialog_title": {
        "tr": "Arşivleri seç", "en": "Choose archives", "es": "Elegir archivos",
        "it": "Scegli archivi", "fr": "Choisir des archives", "ar": "اختر أرشيفات",
        "pt": "Escolher arquivos",
    },
    "file_filter": {
        "tr": "Sıkıştırılmış uygulamalar ({patterns})",
        "en": "Compressed applications ({patterns})",
        "es": "Aplicaciones comprimidas ({patterns})",
        "it": "Applicazioni compresse ({patterns})",
        "fr": "Applications compressées ({patterns})",
        "ar": "تطبيقات مضغوطة ({patterns})",
        "pt": "Aplicativos compactados ({patterns})",
    },
    "result_title": {
        "tr": "{name} hazır", "en": "{name} is ready", "es": "{name} está listo",
        "it": "{name} è pronto", "fr": "{name} est prêt", "ar": "{name} جاهز",
        "pt": "{name} está pronto",
    },
    "result_info": {
        "tr": "{name} hazır\n{size} · {seconds} sn · {exe}",
        "en": "{name} is ready\n{size} · {seconds} s · {exe}",
        "es": "{name} está listo\n{size} · {seconds} s · {exe}",
        "it": "{name} è pronto\n{size} · {seconds} s · {exe}",
        "fr": "{name} est prêt\n{size} · {seconds} s · {exe}",
        "ar": "{name} جاهز\n{size} · {seconds} ث · {exe}",
        "pt": "{name} está pronto\n{size} · {seconds} s · {exe}",
    },
    "autostart_cb": {
        "tr": "Başlangıçta çalıştır (oturum açınca kendiliğinden açılsın)",
        "en": "Launch at startup (start automatically on login)",
        "es": "Iniciar al arrancar (abrir automáticamente al iniciar sesión)",
        "it": "Avvia all'avvio (apri automaticamente al login)",
        "fr": "Lancer au démarrage (ouvrir automatiquement à la connexion)",
        "ar": "تشغيل عند البدء (فتح تلقائي عند تسجيل الدخول)",
        "pt": "Iniciar na inicialização (abrir automaticamente ao entrar)",
    },
    "desktop_cb": {
        "tr": "Masaüstüne kısayol oluştur", "en": "Create desktop shortcut",
        "es": "Crear acceso directo en el escritorio",
        "it": "Crea scorciatoia sul desktop", "fr": "Créer un raccourci sur le bureau",
        "ar": "إنشاء اختصار على سطح المكتب", "pt": "Criar atalho na área de trabalho",
    },
    "result_note": {
        "tr": "İkisi de seçilmezse uygulama yalnızca Uygulamalar menüsünde görünür.",
        "en": "If neither is selected, the app appears only in the application menu.",
        "es": "Si no se selecciona ninguno, la app aparece solo en el menú de aplicaciones.",
        "it": "Se nessuno è selezionato, l'app appare solo nel menu delle applicazioni.",
        "fr": "Si aucun n'est sélectionné, l'app apparaît uniquement dans le menu des applications.",
        "ar": "إذا لم يتم تحديد أي منهما، فسيظهر التطبيق فقط في قائمة التطبيقات.",
        "pt": "Se nenhum for selecionado, o app aparece apenas no menu de aplicativos.",
    },
    "run_now": {
        "tr": "Şimdi Çalıştır", "en": "Run now", "es": "Ejecutar ahora", "it": "Esegui ora",
        "fr": "Lancer maintenant", "ar": "تشغيل الآن", "pt": "Executar agora",
    },
    "ok": {
        "tr": "TAMAM", "en": "OK", "es": "ACEPTAR", "it": "OK", "fr": "OK",
        "ar": "موافق", "pt": "OK",
    },
    "multi_title": {
        "tr": "Toplu dönüşüm sonucu", "en": "Batch conversion result",
        "es": "Resultado de conversión por lotes", "it": "Risultato conversione batch",
        "fr": "Résultat de la conversion par lot", "ar": "نتيجة التحويل المجمع",
        "pt": "Resultado da conversão em lote",
    },
    "multi_failed": {
        "tr": "Yüklenemeyenler:", "en": "Failed to load:", "es": "No se pudieron cargar:",
        "it": "Impossibile caricare:", "fr": "Échec du chargement :",
        "ar": "فشل التحميل:", "pt": "Falha ao carregar:",
    },
    "nav_prev": {
        "tr": "◀ Geri", "en": "◀ Back", "es": "◀ Atrás", "it": "◀ Indietro",
        "fr": "◀ Retour", "ar": "◀ رجوع", "pt": "◀ Voltar",
    },
    "nav_next": {
        "tr": "İleri ▶", "en": "Next ▶", "es": "Siguiente ▶", "it": "Avanti ▶",
        "fr": "Suivant ▶", "ar": "التالي ▶", "pt": "Próximo ▶",
    },
    "all_shortcuts": {
        "tr": "Hepsini kısayol oluştur", "en": "Create shortcuts for all",
        "es": "Crear accesos directos para todos",
        "it": "Crea scorciatoie per tutti", "fr": "Créer des raccourcis pour tous",
        "ar": "إنشاء اختصارات للجميع", "pt": "Criar atalhos para todos",
    },
    "confirm_all": {
        "tr": "Tüm uygulamalar için kısayol oluşturulsun mu?",
        "en": "Create shortcuts for all applications?",
        "es": "¿Crear accesos directos para todas las aplicaciones?",
        "it": "Creare scorciatoie per tutte le applicazioni?",
        "fr": "Créer des raccourcis pour toutes les applications ?",
        "ar": "إنشاء اختصارات لجميع التطبيقات؟",
        "pt": "Criar atalhos para todos os aplicativos?",
    },
    "status_multi_ready": {
        "tr": "{n} uygulama hazırlanıyor…", "en": "{n} apps are being prepared…",
        "es": "Preparando {n} aplicaciones…", "it": "Preparazione di {n} app…",
        "fr": "Préparation de {n} applications…", "ar": "جارٍ تجهيز {n} تطبيق…",
        "pt": "Preparando {n} aplicativos…",
    },
    "status_multi_done": {
        "tr": "{n} uygulama hazır", "en": "{n} apps ready", "es": "{n} apps listas",
        "it": "{n} app pronte", "fr": "{n} apps prêtes", "ar": "{n} تطبيق جاهز",
        "pt": "{n} apps prontos",
    },
    "status_reset": {
        "tr": "Hazır — yeni bir arşiv sürükle veya seç.",
        "en": "Ready — drop or choose an archive.",
        "es": "Listo — arrastra o elige un archivo.",
        "it": "Pronto — trascina o scegli un archivio.",
        "fr": "Prêt — déposez ou choisissez une archive.",
        "ar": "جاهز — اسحب أو اختر أرشيفاً.",
        "pt": "Pronto — solte ou escolha um arquivo.",
    },
    "drag_unsupported": {
        "tr": "{name} desteklenmiyor (.tar.gz, .tgz, .tar.xz, .AppImage olur)",
        "en": "{name} is not supported (.tar.gz, .tgz, .tar.xz, .AppImage)",
        "es": "{name} no es compatible (.tar.gz, .tgz, .tar.xz, .AppImage)",
        "it": "{name} non è supportato (.tar.gz, .tgz, .tar.xz, .AppImage)",
        "fr": "{name} n'est pas pris en charge (.tar.gz, .tgz, .tar.xz, .AppImage)",
        "ar": "{name} غير مدعوم (.tar.gz, .tgz, .tar.xz, .AppImage)",
        "pt": "{name} não é suportado (.tar.gz, .tgz, .tar.xz, .AppImage)",
    },
    # --- Core ---
    "err_zip_unzip": {
        "tr": "ZIP açmak için unzip gerekli (apt: unzip).",
        "en": "unzip is required to open ZIP files (apt: unzip).",
        "es": "se requiere unzip para abrir archivos ZIP (apt: unzip).",
        "it": "unzip è richiesto per aprire i file ZIP (apt: unzip).",
        "fr": "unzip est requis pour ouvrir les fichiers ZIP (apt: unzip).",
        "ar": "unzip مطلوب لفتح ملفات ZIP (apt: unzip).",
        "pt": "unzip é necessário para abrir arquivos ZIP (apt: unzip).",
    },
    "err_7z_missing": {
        "tr": "7z açmak için 7z/p7zip gerekli (apt: p7zip-full).",
        "en": "7z/p7zip is required to open 7z files (apt: p7zip-full).",
        "es": "7z/p7zip es necesario para abrir archivos 7z (apt: p7zip-full).",
        "it": "7z/p7zip è richiesto per aprire i file 7z (apt: p7zip-full).",
        "fr": "7z/p7zip est requis pour ouvrir les fichiers 7z (apt: p7zip-full).",
        "ar": "7z/p7zip مطلوب لفتح ملفات 7z (apt: p7zip-full).",
        "pt": "7z/p7zip é necessário para abrir arquivos 7z (apt: p7zip-full).",
    },
    "err_rpm_missing": {
        "tr": "RPM açmak için rpm2cpio ve cpio gerekli (apt: rpm2cpio cpio).",
        "en": "rpm2cpio and cpio are required to open RPM files (apt: rpm2cpio cpio).",
        "es": "rpm2cpio y cpio son necesarios para abrir archivos RPM (apt: rpm2cpio cpio).",
        "it": "rpm2cpio e cpio sono richiesti per aprire file RPM (apt: rpm2cpio cpio).",
        "fr": "rpm2cpio et cpio sont requis pour ouvrir les fichiers RPM (apt: rpm2cpio cpio).",
        "ar": "rpm2cpio و cpio مطلوبان لفتح ملفات RPM (apt: rpm2cpio cpio).",
        "pt": "rpm2cpio e cpio são necessários para abrir arquivos RPM (apt: rpm2cpio cpio).",
    },
    "err_deb_missing": {
        "tr": "DEB açmak için dpkg-deb gerekli (apt: dpkg).",
        "en": "dpkg-deb is required to open DEB files (apt: dpkg).",
        "es": "dpkg-deb es necesario para abrir archivos DEB (apt: dpkg).",
        "it": "dpkg-deb è richiesto per aprire file DEB (apt: dpkg).",
        "fr": "dpkg-deb est requis pour ouvrir les fichiers DEB (apt: dpkg).",
        "ar": "dpkg-deb مطلوب لفتح ملفات DEB (apt: dpkg).",
        "pt": "dpkg-deb é necessário para abrir arquivos DEB (apt: dpkg).",
    },
    "err_not_found_file": {
        "tr": "dosya bulunamadı: {path}",
        "en": "file not found: {path}",
        "es": "archivo no encontrado: {path}",
        "it": "file non trovato: {path}",
        "fr": "fichier introuvable : {path}",
        "ar": "الملف غير موجود: {path}",
        "pt": "arquivo não encontrado: {path}",
    },
    "err_no_exe": {
        "tr": "arşivde çalıştırılabilir bir uygulama bulunamadı",
        "en": "no runnable application found in the archive",
        "es": "no se encontró una aplicación ejecutable en el archivo",
        "it": "nessuna applicazione eseguibile trovata nell'archivio",
        "fr": "aucune application exécutable trouvée dans l'archive",
        "ar": "لم يتم العثور على تطبيق قابل للتشغيل في الأرشيف",
        "pt": "nenhum aplicativo executável encontrado no arquivo",
    },
    "err_no_space": {
        "tr": "yeterli boş alan yok: gereken ~{size}",
        "en": "not enough free space: ~{size} required",
        "es": "espacio libre insuficiente: se requieren ~{size}",
        "it": "spazio libero insufficiente: richiesti ~{size}",
        "fr": "espace libre insuffisant : ~{size} requis",
        "ar": "مساحة حرة غير كافية: ~{size} مطلوبة",
        "pt": "espaço livre insuficiente: ~{size} necessários",
    },
    "err_no_exe_after": {
        "tr": "açma sonrası çalıştırılabilir bulunamadı",
        "en": "no executable found after extraction",
        "es": "no se encontró ejecutable tras la extracción",
        "it": "nessun eseguibile trovato dopo l'estrazione",
        "fr": "aucun exécutable trouvé après extraction",
        "ar": "لم يتم العثور على ملف قابل للتنفيذ بعد الاستخراج",
        "pt": "nenhum executável encontrado após a extração",
    },
    "err_suffix_missing": {
        "tr": "'{suffix}' açmak için {program} gerekli.",
        "en": "{program} is required to open '{suffix}'.",
        "es": "se requiere {program} para abrir '{suffix}'.",
        "it": "{program} è richiesto per aprire '{suffix}'.",
        "fr": "{program} est requis pour ouvrir '{suffix}'.",
        "ar": "{program} مطلوب لفتح '{suffix}'.",
        "pt": "{program} é necessário para abrir '{suffix}'.",
    },
    "err_flatpak": {
        "tr": "'{name}' bir Flatpak uygulama paketi/değil (flatpakref, remote referansı).",
        "en": "'{name}' is not a Flatpak app package (flatpakref is a remote reference).",
        "es": "'{name}' no es un paquete de app Flatpak (flatpakref es una referencia remota).",
        "it": "'{name}' non è un pacchetto app Flatpak (flatpakref è un riferimento remoto).",
        "fr": "'{name}' n'est pas un paquet d'app Flatpak (flatpakref est une référence distante).",
        "ar": "'{name}' ليس حزمة تطبيق Flatpak (flatpakref مرجع بعيد).",
        "pt": "'{name}' não é um pacote de app Flatpak (flatpakref é uma referência remota).",
    },
    "msg_scan": {
        "tr": "[1/3] {name} taranıyor...", "en": "[1/3] scanning {name}...",
        "es": "[1/3] escaneando {name}...", "it": "[1/3] scansione di {name}...",
        "fr": "[1/3] analyse de {name}...", "ar": "[1/3] جارٍ فحص {name}...",
        "pt": "[1/3] escaneando {name}...",
    },
    "msg_found": {
        "tr": "[1/3] çalıştırılabilir bulundu: {guess} ({count} dosya, ~{size})",
        "en": "[1/3] executable found: {guess} ({count} files, ~{size})",
        "es": "[1/3] ejecutable encontrado: {guess} ({count} archivos, ~{size})",
        "it": "[1/3] eseguibile trovato: {guess} ({count} file, ~{size})",
        "fr": "[1/3] exécutable trouvé : {guess} ({count} fichiers, ~{size})",
        "ar": "[1/3] تم العثور على ملف تنفيذي: {guess} ({count} ملف، ~{size})",
        "pt": "[1/3] executável encontrado: {guess} ({count} arquivos, ~{size})",
    },
    "msg_extract": {
        "tr": "[2/3] {target} içine açılıyor...",
        "en": "[2/3] extracting into {target}...",
        "es": "[2/3] extrayendo en {target}...",
        "it": "[2/3] estrazione in {target}...",
        "fr": "[2/3] extraction dans {target}...",
        "ar": "[2/3] استخراج في {target}...",
        "pt": "[2/3] extraindo em {target}...",
    },
    "msg_done_engine": {
        "tr": "[3/3] tamam ({engine} motoru)",
        "en": "[3/3] done ({engine} engine)",
        "es": "[3/3] listo ({engine})",
        "it": "[3/3] fatto ({engine})",
        "fr": "[3/3] terminé ({engine})",
        "ar": "[3/3] تم ({engine})",
        "pt": "[3/3] concluído ({engine})",
    },
    "msg_ready": {
        "tr": "{name} hazır — {size}, {seconds} saniye",
        "en": "{name} ready — {size}, {seconds} seconds",
        "es": "{name} listo — {size}, {seconds} segundos",
        "it": "{name} pronto — {size}, {seconds} secondi",
        "fr": "{name} prêt — {size}, {seconds} secondes",
        "ar": "{name} جاهز — {size}، {seconds} ثانية",
        "pt": "{name} pronto — {size}, {seconds} segundos",
    },
}

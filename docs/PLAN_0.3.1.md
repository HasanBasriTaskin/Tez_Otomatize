# Plan — Literatür Kayıt Asistanı v0.3.1: Excel uyumu, Zotero şablonları, PDF arşivi, teslim kontrolü

## Bağlam
CEN401 Literatür Kılavuzu v1.2 (Kısım I / Teams Ö2) dört teslim dosyası istiyor:
- Üç sekmeli `OEC-1017_O2_LiteraturMatrisi.xlsx`
- `AramaEkranlari.pdf`
- `kaynaklar.bib`
- `Literatur_PDF` arşivi

Kullanıcı aramaları elle yapacak (otomatik tarama sorunlu), notlarını Zotero'da tutacak. Programın mevcut Excel'inde kılavuzla şu farklar var:
- **Arama_Kaydi:** Elle aramada "Dışa aktarılan kayıt sayısı" hep boş. "İşlemi yapan" sütunu yok (değer `search_runs.operator`'da var).
- **Matris:**
  - ID = Zotero anahtarı (L001 değil).
  - Yayın türü İngilizce `itemType`; derleme/ön baskı ayrımı yok.
  - Bulunma yolu her makale için elle bağlanıyor.
- **Hariç:**
  - "Aşama" sütununa "Okuma düzeyi" yazılıyor (hata, `storage.py::_export_papers`).
  - Gerekçe kodu, Arama ID, Karar veren sütunları yok.
  - Başlık-özet ve tam metin dışlamaları ayrılamıyor.
- **Not şablonu:**
  - Yalnız yönetim ekranında.
  - Tanımsız `Alan:` satırları önceki alana yapışıyor (`zotero.py::parse_note`).
- **PDF:** Arşiv adlandırması (`L001_Yazar_Yil_KisaBaslik.pdf`) için araç yok.

**Hedef:** Kullanıcı yalnızca **arama + Ctrl+M + Zotero'da koleksiyona sürükleme + not doldurma** yapar. Excel, PDF arşivi, PRISMA sayıları ve eksik listesi programdan çıkar. Ek bir uygulama yazılmaz; her şey mevcut programa eklenir. Otomatik tarama koduna dokunulmaz.

## Kullanıcı kararları (bu oturumda)
- Aktarılan kayıt sayısı Excel'e elle yazılmayacak; **Zotero'daki S-koleksiyonundan sayılacak**.
- Aramaları **Hasan Basri Taşkın** yapacak. Ayarlar'daki "Kaydı yapan kişi" bu isimle doldurulur ve Excel'de "İşlemi yapan" sütunu olur.
- PDF adlandırma için ayrı uygulama yok; programa **"Literatur_PDF arşivini oluştur"** eklenecek.
- Hariç tasarımı onaylandı:
  - Başlık-özet dışlamaları yalnız koleksiyonla.
  - Tam metin dışlamaları 6 satırlık hariç notuyla.
- Deneme dosyaları silinebilir.

## Çalışma düzeni (git)
- Depo buluta klonlanır (bağlı klasördeki git kilit dosyası sorunu nedeniyle).
- `origin/feature/otomatize` → yeni dal **`feature/matris-haric-sablon`**. Sürüm 0.3.0 → 0.3.1.
- Her adım test ve commit ile kapanır; dal push edilir; sonunda `feature/otomatize`'ye PR açılır.
- Commit sırası:
  1. `docs: v0.3.1 plan`
  2. `feat(search): Zotero ve elle aktarım sayısı, işlemi yapan sütunu`
  3. `feat(zotero): okuma/hariç şablonları ve güvenli not ayrıştırma`
  4. `feat(zotero): S-koleksiyonlarından bulunma yolu, başlık-özet hariç rolü`
  5. `fix(excel): Matris ID/yayın türü, Hariç sütunları ve Aşama hatası`
  6. `feat(pdf): Literatur_PDF arşivi ve standart dosya adları`
  7. `feat(check): teslim kontrolü ve PRISMA sayıları`
  8. `feat(extension): eklenti penceresinde şablon düğmeleri, yönetim ekranı`
  9. `docs: kullanım kılavuzu ve 0.3.1 sürüm notu`

## Adım 0 — Deneme dosyalarının temizliği (kod dışı, kullanıcı onaylı)
Ön koşul: Kullanıcı tepsideki uygulamadan **Çıkış** yapar. SQLite açıkken silinmez.

Silme izni istenip `D:\...\Tez\OEC-1017_O2` altından silinecekler:
- `03_Calisma/OEC-1017_O2_LiteraturMatrisi*.xlsx`
- `03_Calisma/sorgu-paketi.json`
- `03_Calisma/Veri/` (SQLite + wal/shm + `gecici/`)
- `02_Ekranlar/S001–S004`
- `Yedekler/` (eski kurulumlar, exe, zip)

`Uygulama/` klasörü ve proje klasör iskeleti korunur. Bu klasörlere ait `.git` içindeki `stale-maintenance-lock-claude` de silinir.

## Adım 1 — Arama_Kaydi: aktarım sayısı ve işlemi yapan
- `literature/storage.py`
  - SCHEMA'ya ek tablo:
    `CREATE TABLE IF NOT EXISTS search_run_exports(run_id TEXT PRIMARY KEY REFERENCES search_runs(id), manual_count INTEGER, export_files TEXT, zotero_count INTEGER, zotero_checked_at TEXT, updated_at TEXT)`.
    `user_version` 2 kalır.
  - `update_run()` şunları kabul eder: `notes`, `manual_count` (≥0 tam sayı ya da boş), `export_files` (≤2000 karakter). Kanıt alanları (sorgu, sayı, filtre) değiştirilemez. Audit kaydı yazılır.
  - `export_excel()` sütun 9 öncelik sırası:
    1. Otomatik RIS toplamı
    2. Zotero S-koleksiyon sayısı
    3. Elle girilen sayı
    4. Boş

    Hangisinden geldiği Açıklama'ya kısa not olarak eklenir (ör. "Zotero S004: 248").
  - `SEARCH_HEADERS`'a iki yeni sütun: **Export dosyaları**, **İşlemi yapan** (`run['operator']`). `_format_excel_sheet` genişlikleri güncellenir.
- `literature/zotero.py::import_items` → `^S\d{3}` adlı her koleksiyondaki üst kayıt sayısı (not/ek/anotasyon hariç) aynı `display_id`'li aramanın `zotero_count` alanına yazılır.
- `application.py` → `update_run`/`get_run` yeni alanları taşır.
- `manager.ts/html` → arama ayrıntısında şunlar gösterilir:
  - "Zotero'daki kayıt sayısı (otomatik)"
  - "Elle aktarılan sayı (isteğe bağlı)"
  - "Export dosya adları"

## Adım 2 — İki not şablonu ve güvenli ayrıştırma
- `literature/zotero.py`
  - `NOTE_FIELDS`'a eklenir: `Matris ID`, `Karar`, `Yayın türü`, `Aşama`, `Gerekçe kodu`, `Karar veren`, `Karar tarihi`. `Açıklama` alias'ı `Dahil/hariç gerekçesi`'ne bağlanır.
  - **OKUMA_TEMPLATE:**
    - Baştaki satırlar: `Matris ID:`, `Karar: Dahil`, `Yayın türü: (Dergi / Konferans bildirisi / Ön baskı / Derleme)`
    - Ardından mevcut 24 alan, Excel sütun sırasına yakın düzenlenir. Seçenekli alanlarda parantez içi ipucu bulunur.
  - **HARIC_TEMPLATE:**
    - `Karar: Hariç`
    - `Aşama: Tam metin`
    - `Gerekçe kodu: (H1–H6)`
    - `Açıklama:`
    - `Karar veren:`
    - `Karar tarihi:`
  - Parantez içi ipucu metni değiştirilmeden bırakılırsa boş sayılır.
  - `parse_note`:
    - Tanımsız ama `Alan: değer` görünümlü satır önceki alana yapıştırılmaz. `_bilinmeyen` listesine gider ve raporda uyarı olur.
    - Eski notlar aynen okunur (geri uyumluluk).
- `application.py::status` → `note_templates: {okuma, haric}`.

## Adım 3 — S-koleksiyonları ve başlık-özet hariç rolü
- `application.py::zotero_sync` → `all('collections')` da okunur, `import_items`'a `{key: name}` haritası geçirilir.
- `import_items`:
  - Kaydın üyesi olduğu `^S\d{3}` koleksiyonları için eşleşen arama varsa `search_paper_links`'e **ekler**; elle bağlantıları silmez.
  - Eşleşmeyen S kodu raporda uyarı olur.
- Yeni isteğe bağlı rol **`excluded_title`** ("Başlık-özet hariç"):
  - Excel'e yazılmaz, yalnız PRISMA'ya sayılır.
  - Durum önceliği: `conflict` > `included` > `excluded` > `excluded_title` > `title_passed` > `candidate`.
  - `title_passed` = mevcut "Başlık-özet" rolü, PRISMA için ayrı sayılır.
- `manager.ts` rol listesine eklenir.
- Önerilen Zotero düzeni (belgeye yazılır):
  - `00_AramaKayitlari/S00x`
  - `01_Aday`
  - `02_BaslikOzet_Gecen`
  - `03_TamMetin_Dahil`
  - `04_Haric_TamMetin`
  - `05_Haric_BaslikOzet`

## Adım 4 — Excel Matris ve Hariç
`storage.py::_export_papers`:
- **Matris:**
  - `ID` = notun `Matris ID`'si. Boşsa Zotero anahtarı yazılır ve raporda uyarı çıkar.
  - Satırlar Matris ID'ye göre sıralanır.
  - `Yayın türü` = nottan. Boşsa Türkçe karşılık: `journalArticle` → Dergi makalesi, `conferencePaper` → Konferans bildirisi, `preprint` → Ön baskı.
  - `Bulunma yolu` = tüm bağlı S kodları.
  - `Yerel PDF dosyası` = nottaki ad. Boşsa Adım 5'in ürettiği standart ad.
- **Hariç:** `EXCLUDED_HEADERS` şöyle olur:
  - `Aday / Zotero anahtarı`
  - `Başlık`
  - `DOI veya bağlantı`
  - `Arama ID`
  - `Aşama` (nottan; yoksa "Tam metin")
  - `Gerekçe kodu`
  - `Açıklama`
  - `Karar veren`
  - `Karar tarihi` (nottan; yoksa okuma zamanı)

  "Okuma düzeyi → Aşama" hatası giderilir.

## Adım 5 — Literatur_PDF arşivi (dosya adı standardı)
- Ayar: **Zotero veri klasörü**. Varsayılan `%USERPROFILE%\Zotero`; Zotero → Settings → Advanced → Files and Folders'daki yol girilebilir. `storage/` alt klasörü doğrulanır.
- `zotero.py::import_items` → ek kayıtlar (`itemType=attachment`, `contentType=application/pdf`, `linkMode` `imported_file`/`imported_url`) üst kayda bağlanıp saklanır: anahtar, `filename`.
- Yeni `literature/pdf_archive.py::build_archive(store)`:
  - Her **dahil** kayıt için `<veri klasörü>/storage/<ekAnahtarı>/<filename>` bulunur.
  - Dosya proje kökündeki `Literatur_PDF/` klasörüne **kopyalanır**; Zotero'daki asıl dosyaya dokunulmaz.
  - Ad `L001_Yazar_Yil_KisaBaslik.pdf`:
    - Türkçe harfler ASCII'ye çevrilir.
    - Kısa başlık en fazla 4 anlamlı kelime ve CamelCase.
    - Nottaki `Yerel PDF` doluysa o ad kullanılır.
  - Matris ID yoksa o kayıt atlanır ve raporlanır.
  - Aynı ad ve aynı hash varsa atlanır. Farklı hash varsa üzerine yazılmaz; `_v2` önerilir.
  - Birden çok PDF eki varsa ilk PDF kullanılır, uyarı verilir.
  - Arşivde matriste karşılığı olmayan dosya varsa listelenir; silinmez.
  - Sonuç: kopyalanan / atlanan / eksik PDF listesi.
- Yönetim ekranında "Çıktılar ve yedek" altına **"Literatur_PDF arşivini oluştur"** düğmesi eklenir.
- Not: Zotero vurguları asıl PDF'e yazılmaz. Vurgulu kopya isteniyorsa Zotero'da *File → Export PDF* kullanılır (belgeye yazılır).

## Adım 6 — Teslim kontrolü ve PRISMA
- `exports.py::check_project` genişletilir. Yeni RPC `check_project` → `{counts, prisma, issues}`.
- Yönetim ekranına **"Teslim kontrolünü çalıştır"** düğmesi eklenir.
- **PRISMA sayıları** (kılavuz s. 11–12):
  - D = Arama_Kaydi'ndeki aktarım toplamı (yalnız konu sorguları)
  - Çıkarılan tekrar = D − Zotero'daki benzersiz aday
  - Başlık-özet hariç = `excluded_title` sayısı
  - Tam metni değerlendirilen
  - Tam metin hariç (H koduna göre dağılım)
  - Dahil

  Tutarsız aritmetik uyarı olur.
- **Kılavuz sınırları:**
  - Dahil ≥ 80.
  - Çekirdek (Evet ve Okuma düzeyi 3) ≥ 20.
  - Ön baskı ≤ 8, derleme ≤ 10.
  - 2024 öncesi ≤ 8, notta gerekçe zorunlu.
  - Q1–Q2 / CORE A*–A ≥ %50.
  - Okuyan kişiye göre dağılım.
- **Alan kontrolleri:**
  - Matris'in zorunlu alanları dolu mu?
  - "Temel bulgu"da sayfa/tablo izi var mı?
  - Matris ID biçimi `L\d{3}` mü, tekrar var mı?
  - Arşivde PDF var mı?
  - Hariç kayıtta `H[1-6]` kodu var mı?
  - Notta tanımsız alan var mı?
  - Arama kaydında "İşlemi yapan" boş mu?
- Yalnız okur; hiçbir şeyi değiştirmez.

## Adım 7 — Eklenti
- `extension/public/popup.html` + `src/popup.ts` → "Kayıtlar ve ayarlar" altına iki düğme: **Okuma şablonunu kopyala**, **Hariç şablonunu kopyala**.
  - Şablon worker → Windows uygulaması `status` üzerinden alınır; tek kaynak Python.
  - Bağlantı yoksa anlaşılır mesaj gösterilir.
- `manager.html/ts`:
  - Eski tek şablon düğmesi bu ikisiyle değiştirilir.
  - Adım 1, 3, 5 ve 6'nın arayüzleri eklenir.

## Adım 8 — Belgeler ve sürüm
- `README.md` / `docs/KILAVUZ.md` → "Elle çalışma akışı":
  1. Ctrl+M
  2. Export → RIS
  3. Zotero'da `00_AramaKayitlari/S00x` ve `01_Aday` koleksiyonlarına aktarma
  4. Tekrar birleştirme
  5. Başlık-özet elemesi (koleksiyon)
  6. Tam metin (PDF + not)
  7. Zotero'dan oku
  8. Excel'i güncelle
  9. PDF arşivi
  10. Teslim kontrolü
- Zotero'nun "Find Available PDF" özelliği için uyarı: tek tek veya küçük gruplar halinde kullanılmalı; kılavuz s. 10 toplu otomatik indirmeyi yasaklıyor.
- `package.json` 0.3.1, `docs/releases/0.3.1.md`.

## Dokunulmayacaklar
- Otomatik tarama: `workflow.py`, `workflow-browser.ts`, `automation-dom.ts`, `zotero_writer.py`.
- Yakalama ve yıl daraltma akışı. Kanıt alanlarının değiştirilemezliği.

## Doğrulama
1. Her commit öncesi bulutta:
   - `python -m unittest discover -s tests -v` (Windows'a özgü testler atlanır).
   - `npm ci && npm run typecheck && npm test`.
2. Yeni ve güncellenen testler:
   - `test_storage.py`: aktarım sayısı önceliği, İşlemi yapan, Hariç sütunları ve Aşama regresyonu, Matris ID sıralaması.
   - `test_zotero_notes.py` (yeni):
     - Eski ve yeni şablon ayrıştırma.
     - İpucu metninin boş sayılması.
     - Tanımsız alanın yapışmaması.
     - S-koleksiyonu bağlantısı ve sayımı.
     - `excluded_title` rolü.
   - `test_pdf_archive.py` (yeni):
     - Sahte `storage/KEY/x.pdf` ile kopyalama.
     - ASCII ad üretimi (ör. "Köse" → "Kose").
     - Çakışma ve eksik PDF raporu.
   - `test_outputs.py`: teslim kontrolü sınırları ve PRISMA aritmetiği.
3. Örnek veriyle üretilen Excel'in üç sekmesi açılıp başlık ve satırlar kontrol edilir.
4. Kullanıcı Windows'ta:
   1. Dalı çeker, `build.bat` çalıştırır.
   2. Kurulum.exe ile temizlenmiş proje klasörünü seçer, eklentiyi yeniler.
   3. Ayarlar'a "Hasan Basri Taşkın" yazar.
   4. Scopus'ta S001 araması + Ctrl+M yapar.
   5. Zotero'da 1 dahil + 1 hariç örnek not hazırlar → Zotero'dan oku → Excel'i güncelle → PDF arşivi → Teslim kontrolü.

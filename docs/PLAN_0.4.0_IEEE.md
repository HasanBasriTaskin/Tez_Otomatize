# Plan — Literatür Kayıt Asistanı v0.4.0: IEEE Xplore'u Scopus düzeyine getirmek

Dal: `feature/ieee-otomasyon` (0.3.6 = `fix/proje-klasoru-secimi` üzerine). Durum: **plan — kod yazılmadı.** Kullanıcı onaylayınca başlanır.

## Bağlam (16.10.2026, Deneme klasöründe canlı deneme)

IEEE Xplore'da Ctrl+M ekran görüntüsünü doğru alıyor, ama program sayfadan **hiçbir alanı okuyamadı**: sorgu, sayı, filtre ve aranan alan boş kaldı. Bunun nedeni, programda Scopus'a özel bir okuyucu (`adapters.ts::scopusPublications`) olması; IEEE'de yalnız genel kalıplar aranıyor.

Kullanıcı sağ tık ile alanları elle eşleyince durum şöyle oldu:
- Sorgu ve sayı okundu: `( ("Abstract":… "low-resource"))`, 194.
- Filtrelerden yalnız "Filters Applied:" etiketi geldi. Conferences ve Journals ayrı kutucuklarda olduğu için okunmadı.
- Yıl yalnız soldaki giriş kutularında yazıyor; eşleme bunları okuyamıyor.
- Aranan alan sayfada ayrı bir metin olarak yok.

Scopus'ta ise bunların hepsi var:

| Özellik | Scopus (0.3.6) | IEEE (bugün) |
|---|---|---|
| Sorgu / sayı | Özel okuyucu | Yok (elle eşleme ile var) |
| Aranan alan | Sorgu başından (`TITLE-ABS-KEY`) | Yok |
| Filtreler | DOCTYPE + yıl, sorgudan ve panelden | Yok |
| Proje yıl penceresi önerisi | Var (`refinement.py::propose`, yalnız Scopus) | Yok |
| Öneriyi tek tıkla uygulama | Yıl kutuları + Apply (`refinement-dom.ts`) | Yok |
| Daraltma zinciri (S00x devamı) | Sorgudaki `PUBYEAR`'dan | Yok (IEEE'de yıl sorguda değil, filtrede) |

## Hedef

IEEE'de kullanıcı yalnız şunları yapar: **Command Search'e sorguyu yapıştır → Search → Ctrl+M → "Uygula ve ara" → Ctrl+M → Export.** Yıl penceresi ve yayın türü filtresi (Conferences + Journals) program tarafından önerilir ve tek tıkla uygulanır. Sorgu, sayı, filtreler ve aranan alan kendiliğinden kayda geçer, Eksik kayıtlar'a düşmez.

ACM Digital Library aynı yaklaşımla **ikinci aşamada** yapılır (bölüm 7).

## 1. Önce toplanacak gerçek sayfalar (kullanıcı, Deneme klasöründe)

Okuyucu tahminle yazılmaz. Repodaki Scopus testleri gibi, gerçek sayfalardan alınmış ve kişisel bilgisi temizlenmiş test dosyalarıyla yazılır.

Chrome'da **Ctrl+S → "Web Sayfası, Tek Dosya (.mhtml)"** ile `Tez\Deneme\ieee_sayfalar\` klasörüne kaydedilecekler:
1. Filtresiz sonuç sayfası (Q01: 195 sonuç).
2. Conferences + Journals uygulanmış sonuç sayfası (194).
3. Sonuçları 2024'ten **eski** yıllara uzanan bir sorgunun sayfası. Yıl kutusunun 2024'ten küçük bir değerle başladığı durum için; Q04 ya da Q03 IEEE karşılığı olabilir. Önce filtresiz, sonra 2024–2026 uygulanmış hali.
4. Export penceresi açıkken sayfa. Ayrıca Export → Citations sekmesinin ekran görüntüsü.

"HTML only" değil MHTML seçilmeli: IEEE sayfası tarayıcıda sonradan oluşturuluyor, "HTML only" boş iskeleti kaydeder.

Claude bu dosyalardan proxy adını, oturum kimliklerini ve e-posta alanlarını temizleyip `extension/tests/fixtures/ieee-*.html` olarak ekler. Ham dosyalar repoya girmez.

## 2. IEEE okuyucusu (`adapters.ts::ieeeResults`)

- **Sayfa tanıma:** yol `/search/searchresult.jsp` olmalı. Doğrudan `ieeexplore.ieee.org` veya başlıkta "IEEE Xplore" geçen proxy adresi (vetisonline) olabilir.
- **Sorgu:** "Showing … results for" satırındaki çalıştırılmış sorgu metni.
  - Doğrulama: adres çubuğundaki `queryText` parametresiyle aynı mı? (Scopus'taki `query_verified` karşılığı.)
  - Arama kutusunda başka bir metin varsa uyarı.
- **Sayı:** "Showing 1-25 of N results" → N, `exact`. Binlik ayıracı (1,234) desteklenir.
- **Aranan alan:** sorgudaki `"Alan":` önekleri.
  - Hepsi aynıysa o alan (`Abstract`).
  - Karışıksa sıralı liste (`Abstract; Document Title`).
  - Önek yoksa `All Metadata`.
- **Filtreler:** "Filters Applied" bölümündeki her kutucuk ayrı bir filtre (`Conferences`, `Journals`).
  - Yıl: adres çubuğundaki `ranges=YYYY_YYYY_Year` uygulanmışsa `Yıl: 2024–2026`.
  - Uygulanmamışsa ve soldaki yıl kutusu sonuç aralığının tamamını gösteriyorsa `Yıl (sonuç aralığı): 2024–2026` diye ayrıca kaydedilir. Bu, bugünkü Q01 durumu: Apply pasif, çünkü bütün sonuçlar zaten pencerede.
- **Bekleyen seçim:** Panelde işaretlenmiş ama uygulanmamış bir seçim varsa uyarı ("filtre henüz uygulanmamış"), Scopus'taki `pending` gibi.
- **Kaynak etiketi:** `ieee-searchresult-0.1.0`. Kullanıcının elle eşlemesi varsa yine öncelikli.

## 3. Proje yıl penceresi ve filtre önerisi (IEEE)

- **Öneri koşulu (`refinement.py`):** IEEE kaydında proje penceresi biliniyorsa (`project_window`, bugün 2024–2026) ve şunlardan biri doğruysa, tek bir öneri:
  - kayıtta yıl filtresi yok ve sonuç aralığı pencereyi aşıyor, ya da
  - yayın türü filtresi eksik.

  Öneri metni: **"IEEE filtrelerini uygula: Yıl 2024–2026, Conferences, Journals"**. Gerekçede pencerenin hangi Scopus zinciriyle belirlendiği yazar ("S002 → S003").
- **Sonuçlar zaten pencere içindeyse:** Yıl için öneri yapılmaz; yalnız eksik türler önerilir. Hiçbir şey eksik değilse öneri yoktur.
- **Pencere henüz belirlenmemişse:** IEEE'de öneri yapılmaz. Kılavuz pencereyi ilk Scopus sorgusuna göre belirler; IEEE'de ayrı eşik zinciri kurulmaz.
- **Zincir bağlama:** IEEE'de yıl sorguda değil filtrede. Çocuk kayıt şu koşullarla öncekine bağlanır: aynı sekme ve oturum (Scopus'taki kural) + aynı sorgu metni + yeni filtrelerde istenen yıl ve türler. Not: `S020 devamı: IEEE filtreleri uygulandı (2024–2026, Conferences, Journals)`.
- **Teslim kontrolü:** `_window_start` değişmez (Scopus zincirinden okunur).

## 4. Öneriyi tek tıkla uygulama (`refinement-dom.ts`)

İki yol var; gerçek sayfalarla hangisinin güvenilir olduğu seçilecek:
- **(a) Panel:** "Conferences" ve "Journals" kutucuklarını işaretle, yıl kutularına 2024 / 2026 yaz, IEEE'nin Apply düğmelerine bas. Scopus'taki gibi değerler yeniden okunur; bir değer kendiliğinden değişirse (Scopus 2022 → 2023 vakası) arama çalıştırılmaz.
- **(b) Adres:** Aynı sekmede sorgu adresine `ranges=2024_2026_Year` ve `refinements=ContentType:Conferences` / `ContentType:Journals` parametreleri eklenerek açılır. Daha az kırılgan, ama parametre adları gerçek sayfayla doğrulanmalı.

Her iki yolda:
- Sorgu veya sayı değiştiyse dokunulmaz ("Yeni sayfada Ctrl+M yapın").
- İşlem bitince "Sonuçlar yüklenince Ctrl+M yapın" denir.
- Başarısızlıkta "Filtreleri elle uygula" metni ve hangi filtrelerin seçileceği gösterilir.

## 5. Dışa aktarma (IEEE RIS)

Gerçek pencere (16.10.2026, ekran görüntüsü): Export → **Citations** sekmesi önce kayıt seçilmesini istiyor ("Please select at least one result for download"). Scopus'taki "bütün sonuçlar" seçeneği bu ekranda yok. Format: Plain Text / BibTeX / **RIS** / RefWorks. Include: Citation Only / **Citation and Abstract**.

Elle kullanım (bu sürümde de geçerli):
- **Items Per Page → 100** → **Select All on Page** → Export → Citations → RIS + Citation and Abstract → Download.
- Her sayfa için ayrı dosya: `S021_IEEE_001-100.ris`, `S021_IEEE_101-194.ris`.
- Seçimin sayfa değişince kalkıp kalkmadığı canlı denemede doğrulanacak.

Programın katkısı (bu sürüm):
- Kayıt ayrıntısında "IEEE RIS: kaç sayfa, hangi dosya adları" önerisi. Örneğin 194 kayıt → 2 dosya ve adları.
- Zotero okumasında aynı S koduyla başlayan parçalı dosyaların tek koleksiyonda toplam sayıya eşitliği kontrol edilir; eksik ya da tekrarlı kayıt uyarısı verilir.
- Zotero'da koleksiyon adı `S021_IEEE`; program sayıyı oradan okur (0.3.1'den beri var).

Otomatik dışa aktarma bu sürümün kapsamında değil; gerekirse sonra.

### 5.1 Toplu dışa aktarma bulguları (16.10.2026)

- Kaydedilen Export sayfası: "You have selected 25 citations for download". Citations yalnız **seçili** kayıtları indiriyor. Örnek RIS: 25 kayıt, hepsinde AB, DO, PY var.
- IEEE yardım sayfası: "Download citations for all or selected search results".
- Zotero forumu (2014): Export → **Results** sekmesi en çok 2.000 sonucu **CSV** olarak indiriyor; Zotero CSV'yi doğrudan içe alamıyor. Güncel sınır ve sütunlar gerçek pencereden doğrulanacak (Results sekmesi açıkken ekran görüntüsü ya da sayfa kaydı).
- **Seçenek A (bugün):** Items Per Page 100 → Select All on Page → RIS, sayfa başına dosya. Bizim sorgularda 1–6 dosya. 2.000 sonuçta 20 dosya olur, pratik değil.
- **Seçenek B (0.4.0 adayı):** Results → CSV (tek dosya, ≤2.000) → program **IEEE CSV → RIS** dönüştürür (`ris.py` yanında `ieee_csv.py`):
  - Eşlenen alanlar: başlık, yazarlar, yayın adı, yıl, cilt/sayı/sayfa, özet, DOI, ISSN/ISBN, yazar anahtar kelimeleri, belge türü (Conference/Journal).
  - Kayıt sayısı ekrandaki sayıyla karşılaştırılır. Dönüştürülen dosya `S0xx_IEEE.ris`, özgün CSV `01_HamExport`'ta saklanır.
  - Gerçek bir CSV örneğiyle test edilir.
- Araştırma (16.10.2026): IEEE yardım sayfası ve kütüphane rehberleri (UCL, NJIT, Rayyan) yalnız "seç → Export → Citations → RIS" yolunu anlatıyor; tek adımda tüm sonuçları RIS olarak indirmeyi ya da bir kayıt sınırını belgeleyen kaynak yok. UCL: Results sekmesi CSV indirir. IEEE Metadata API (anahtar gerekli, istek başına ≤200 kayıt) bu proje için uygun değil.
- **Canlı test (kullanıcı):** (1) 1. sayfada Select All on Page → 2. sayfa → Select All on Page → Export → Citations: "You have selected N" 194 mü? Evetse tek RIS dosyası yeterli (Seçenek A', sayfa sayısı kadar tık, tek dosya). (2) Results sekmesi → CSV → sınır ve sütunlar.
- Yanlış örnek: `ieee_sayfalar/yıl1936.html` arama sonucu değil, "Browse Conferences by Title" sayfası; testlerde kullanılmaz.

## 6. Arayüz ve Excel

- **Excel Arama_Kaydi:**
  - Veritabanı = `IEEE Xplore`
  - Alan = `Abstract`
  - Filtre = `Yıl: 2024–2026; Conferences; Journals`
  - Açıklama = zincir notu.
- **Öneri penceresi:** Scopus'takiyle aynı; başlık "Filtreleri uygulayalım mı?", altında uygulanacak filtrelerin listesi.
- **Eksik kayıtlar formu:** IEEE için "Aranan alan" ve "Filtreler" ipuçları ("Abstract", "Yıl: …; Conferences; Journals").
- **Kılavuz:** "IEEE'de her arama" bölümü.

## 7. İkinci aşama: ACM Digital Library (0.4.x)

Aynı yöntemle, ayrı commit dizisi olarak:
- Gerçek sayfalar: Advanced Search sonuçları ve "Edit Query / View Query Syntax".
- Okuyucu: sorgu `[[Abstract: …]]` sözdiziminden, alan sorgudan, sayı "… Results", tarih filtresi `E-Publication Date`.
- Yıl önerisi ve uygulama (form tarih alanları ya da adres).
- Dışa aktarma: Export Citations → **BibTeX** (kılavuz böyle diyor), dosya `S0xx_ACM.bib`.

## 8. Testler ve kabul

- **Otomatik:**
  - Temizlenmiş IEEE sayfalarıyla okuyucu testleri: sorgu, sayı, alan, filtreler, bekleyen seçim.
  - Öneri kuralları: pencere içi, pencere dışı, tür eksik, pencere bilinmiyor.
  - Zincir bağlama: aynı sekme, farklı sekme, sorgu değişmiş.
  - Panel/adres uygulama testleri; değer kendiliğinden değişince çalıştırmama.
  - Mevcut 142 Python ve 80 eklenti testi geçmeye devam etmeli.
- **Canlı kabul (kullanıcı, Deneme klasöründe):**
  - IEEE Q01: Ctrl+M → öneri → Uygula → Ctrl+M → kayıt tam (Eksik kayıtlar boş). Excel'de Alan ve Filtre dolu.
  - Pencere dışına uzanan bir sorguda yıl önerisi gelir ve uygulanır.
  - Export → RIS → Zotero'ya `S0xx_IEEE` aktarımı (yalnız Deneme projesinde; TEZ grubuna değil ya da ayrı bir deneme koleksiyonuna).
- Kabul geçince sürüm 0.4.0. Kullanıcı onayıyla önce `fix/proje-klasoru-secimi`, sonra bu dal `main`'e birleştirilir; `feature/matris-haric-sablon` korunur.

## Kapsam dışı

- Otomatik IEEE/ACM taraması (Scopus otomasyonu gibi), PDF indirme, bilimsel eleme.
- Web of Science.

## Kullanıcı kararları (16.10.2026)

- **Yıl:** IEEE'nin varsayılan olarak gösterdiği yıl aralığı kullanılır; zorla ayrıca uygulanmaz. Program o aralığı doğru okuyup Excel'e doğru yazmalı:
  - Uygulanmışsa `Yıl: 2024–2026`.
  - Sonuçların doğal aralığıysa `Yıl (sonuç aralığı): 2024–2026`.

  Sonuç aralığı proje penceresini aşıyorsa öneri yine yapılır (bölüm 3).
- **Kılavuz sınırları IEEE'de de uygulanır (onaylı, Scopus gibi):**
  - Proje penceresi belliyse (Scopus eşik zinciri: 2024–2026) ve IEEE sonuçları pencerenin dışına taşıyorsa, Ctrl+M'den sonra "Aramayı daraltalım mı?" penceresi çıkar. "Uygula ve ara" yıl kutularını doldurup Apply'a basar; sonra yeniden Ctrl+M.
  - Pencere henüz belli değilse (IEEE projenin ilk araması olursa) Tablo 4 kuralı IEEE sonucuna uygulanır: >300 → 2022–2026; ilk sonuç >1.000 ve 5 yıllık sonuç >500 → 2024–2026.
  - Konu sorguları Scopus'taki gibi tek adımda pencereye iner; ikinci bir daraltma yapılmaz.
  - Sonuçlar zaten pencere içindeyse yıl için öneri çıkmaz.
- **Yayın türü:** Aynı onay penceresinde, eksikse Conferences + Journals önerilir (açık soru 1).
- **Öncelik:** Excel'e yazılan verinin doğruluğu ve hatasızlık. Okunamayan alan tahmin edilmez; Eksik kayıtlar'a düşer.

## Açık sorular (kullanıcıya)

1. Yayın türü filtresi IEEE'de yalnız **Conferences + Journals** mı olsun? Early Access makaleler Journals altında görünüyor olabilir; gerçek sayfada kontrol edilecek.

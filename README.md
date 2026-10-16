# Literatür Kayıt Asistanı

Literatür taramasında hangi sorgunun, hangi filtrelerle ve kaç sonuçla çalıştırıldığını kayıt altına alan Windows uygulaması ve Chrome eklentisidir. Windows uygulaması monitörün gerçek görüntüsünü alır; eklenti aktif sekmedeki arama bilgilerini okur. Görseller ve kayıtlar seçilen proje klasöründe tutulur, Excel'e aktarılır.

Uygulama ile:

- **Ctrl+M** üzerinden sorgu, filtre, sonuç sayısı ve ekran kanıtı birlikte kaydedilebilir.
- Scopus sonuçlarına göre yıl daraltması önerilebilir; önceki arama ve yeni sonuç birbirine bağlanır.
- Düzenlenebilir sorgu paketiyle otomatik tarama, RIS indirme ve Zotero aday havuzuna aktarım başlatılabilir.
- Zotero notlarından matris, kaynak listesi, BibTeX ve ekran kanıtları PDF'si hazırlanabilir; proje yedeği alınabilir.

**Sürüm kapsamı:** 0.2.1 manuel kayıt ve onaylı daraltma sürümüdür. Sorgu düzenleyicisi ve otomatik tarama 0.3.0 ile eklenmiştir. 0.3.1, elle tarama akışını kılavuzun teslim dosyalarıyla eşleştirir: Zotero'dan otomatik aktarım sayısı ve bulunma yolu, okuma/hariç not şablonları (eklenti penceresinden kopyalanır), L001 kimlikli Matris, 9 sütunlu Hariç, Literatur_PDF arşivi ve teslim kontrolü (PRISMA ve sınırlar). Ayrıntılar: [elle çalışma akışı](docs/KILAVUZ.md#elle-çalışma-akışı-031--arama-zotero-ve-teslim). 0.3.2, eşik sorgusuyla belirlenen yıl penceresini (ör. 2024–2026) sonraki konu sorgularına tek adımda önerir ve Scopus yıl kutusu sonuçlara göre kısıtlandığında tam sorguyu panoya kopyalar. Otomatik Scopus → RIS → Zotero zinciri ön sürümdür; canlı kabulü henüz tamamlanmamıştır. PDF okuma ve bilimsel kaynak seçimi otomatik yapılmaz. IEEE/ACM otomasyonu sonraki aşamadır. Kapsam ve bekleyen işler: [otomasyon planı](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/AUTOMATION_PLAN.md).

[Son kullanıcı: kullanım](#son-kullanıcı-kullanım) · [Releases üzerinden kurulum](#releases-üzerinden-kurulum) · [Geliştirici: build](#geliştirici-build-ve-dağıtım)

## Son kullanıcı: kullanım

### Manuel arama kaydı

Kurulumdan sonra günlük kullanım için Başlat menüsünden **Literatür Kayıt Asistanı** açılır. Uygulama sistem tepsisinde çalışır; ayrı bir ana Windows penceresi açılması gerekmez. Yönetim ekranı Chrome eklentisindeki **Kayıtlar ve ayarlar** düğmesidir.

1. Chrome'da kendi sorgunuzu çalıştırın ve sonuçların yüklenmesini bekleyin.
2. Sorgu, sonuç sayısı, adres çubuğu ve Windows görev çubuğundaki saat/tarih görünürken **Ctrl+M** yapın. Yakalama sırasında sekme değiştirmeyin.
3. Kaydı **Arama kayıtları** bölümünde kontrol edin. PNG `02_Ekranlar/S001/` gibi bir klasöre, Excel `03_Calisma` altına kaydedilir. Aynı aramanın ek görüntüleri birlikte tutulur.
4. Yıl daraltma önerisi çıkarsa **Uygula ve ara** seçilebilir. Yeni sonuçlar yüklenince yeniden **Ctrl+M** yapın; yeni kayıt önceki adıma bağlanır.
5. Sonraki sorguyu kendiniz yazın. Manuel kullanım, sorgu paketindeki konuları kendiliğinden ilerletmez.

| İlk yıl sınırsız sonuç | Yıl önerisi |
|---|---|
| 0–300 | Yıl sınırı yok |
| 301–1000 | 2022–2026 |
| 1000'den fazla | Önce 2022–2026; bu sonuç da 500'den fazlaysa 2024–2026 |

Bu yıllar proje rehberine göre sabittir; takvimle otomatik değişmez. Bilgiler okunamazsa **Eksik kayıtlar** bölümünden özgün PNG'yi kontrol ederek tamamlayın. Excel'deki **Ekran dosyası** bağlantısı aramanın kanıtlarını açar. İlk kullanım kontrol listesi: [manuel kabul testleri](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/MANUEL_TEST.md).

### ÖNEMLİ: Otomasyonun sorgu paketi

**Sorgular build sırasında hazırlanmak zorunda değildir. Kurulumdan sonra değiştirilebilir; yeniden build, kurulum veya eklenti yükleme gerekmez.** Paket, başlangıç sorgusunu ve sırayla çalıştırılacak konu sorgularını belirler. Hazır paket OEC-1017/RAG araştırmasına aittir; başka bir araştırmada kendi terimlerinizle değiştirilmelidir.

Dosya her projenin içinde tutulur:

```text
<Seçtiğiniz proje klasörü>\03_Calisma\sorgu-paketi.json
```

Örneğin proje `D:\Tez\Literatur_Projem` ise dosya `D:\Tez\Literatur_Projem\03_Calisma\sorgu-paketi.json` olur. **Otomatik tarama** bölümü ilk açıldığında dosya yoksa varsayılan başlangıç + altı konu paketi oluşturulur. Tam dosya yolu aynı ekranda gösterilir; dosyayı `payload` veya program kurulum klasöründe aramayın.

**Eklentiden düzenlemek için:**

1. Chrome'da eklenti simgesi → **Kayıtlar ve ayarlar → Otomatik tarama → Sorgu paketi → Sorguları düzenle** yolunu açın.
2. Paket adını, başlangıç sorgusunu ve konu terimlerini düzenleyin. 1–20 konu kullanılabilir; konu eklenip çıkarılabilir.
3. Başlangıç sorgusunu `TITLE-ABS-KEY(...)` biçiminde yazın. Konulara yalnız kavram bloklarını yazın; alan, yıl ve yayın türü eklerini uygulama oluşturur. Sorgulara ayrıca `PUBYEAR` veya `DOCTYPE` eklemeyin.
4. **Sorgu paketini kaydet** seçin. JSON güncellenir; önceki dosya `Yedekler` altında korunur.
5. **Sorgu paketini göster** ile kontrol edin. Sonraki yeni tarama kaydedilmiş paketi kullanır.

**Dosyadan düzenlemek için:** JSON'u bir metin düzenleyicide UTF-8 olarak kaydedin; aynı ekranda **Değişiklikleri bırak ve dosyadan yükle** seçin. Bu düğme formdaki kaydedilmemiş değişiklikleri bırakır. `.txt` dosyaları otomatik okunmaz. JSON örneği ve alan açıklamaları: [sorgu paketi kılavuzu](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/KILAVUZ.md#sorgu-paketi-json-örneği).

Başlamış tarama kendi sorgu kopyasıyla devam eder. Paketi değiştirmek için oturumu tamamlayın veya **Durdur** seçin; yeni paketle **Taramayı başlat** kullanın. Başka kullanıcıya yalnız sorgu JSON'unu paylaşabilirsiniz; kullanıcının kendi proje klasöründeki aynı konuma koyması yeterlidir.

### Otomatik taramayı çalıştırma

1. Scopus oturumunu açın. Zotero'yu açıp **Settings → Advanced → Allow other applications on this computer to communicate with Zotero** ayarını etkinleştirin.
2. **Otomatik tarama** ekranında sorgu paketini, hedef Scopus sekmesini ve yayın türlerini kontrol edin. **İndirme iznini ver**, **Zotero bağlantısını kontrol et** ve ilk kullanımda **Zotero yazma iznini ver** işlemlerini tamamlayın.
3. **Taramayı başlat** seçin. Akış başlangıç sorgusu → yıl kararı → konu sorguları → PNG/Excel → RIS → Zotero şeklindedir; ara Ctrl+M veya yıl onayı beklenmez. Başlangıç/yıl denemeleri dışa aktarılmaz; konu sorgularının son filtreli sonuçları aktarılır.
4. Scopus önde kalmalıdır. Sekme/uygulama değişimi, giriş veya CAPTCHA ihtiyacı işlemi duraklatabilir. Yönetim ekranındaki **Duraklat / Devam et / Durdur** düğmelerini kullanın.

Otomatik Zotero yazma hedefi mevcut **TEZ** grubudur; grup üyeliği gerekir. Sorgu JSON'unu değiştirmek hedef kütüphaneyi değiştirmez. İşleyiş ve kabul koşulları [otomasyon planında](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/AUTOMATION_PLAN.md), doğrulama kapsamı [test raporunda](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/TEST_RAPORU.md) bulunur.

### Kayıtlar, çıktılar ve yedek

| Proje içindeki klasör | İçerik |
|---|---|
| `01_HamExport` | Otomatik taramanın doğrulanmış RIS dosyaları |
| `02_Ekranlar` | Özgün PNG'ler ve arama başına kanıt dizini |
| `03_Calisma` | Excel ve sorgu paketi; `Veri` altında SQLite kayıtları |
| `05_Teslim` | Kaynak/ekran PDF'leri ve BibTeX |
| `Yedekler` | Proje yedekleri ve koruma kopyaları |

Klasörler ilgili işlem gerektiğinde oluşturulur. Excel ilk kayıtla üretilir; boş çalışma kitabı için **Excel’i güncelle** kullanılabilir. Kayıt düzeltmelerini uygulamadan yapın: Excel asıl veritabanı değildir. Açık/değiştirilmiş Excel korunabilir ve ayrı çıktı sürümü oluşturulabilir; uygulamanın bildirdiği yolu kullanın.

**Zotero ve notlar** bölümünde koleksiyonları eşleştirip kaynak notlarını okuyun; **Çıktılar ve yedek** bölümünden PDF/BibTeX veya proje yedeği üretin. Her kullanıcı ayrı proje klasörü kullanmalıdır. İki kişinin Excel/SQLite dosyalarını üst üste kopyalamayın; otomatik proje birleştirme yoktur. Not şablonu ve geri yükleme ayrıntıları: [kullanım kılavuzu](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/KILAVUZ.md).

## Releases üzerinden kurulum

Gerekenler: **Windows 11 x64 ve Google Chrome**. Zotero özellikleri için Zotero ayrıca kurulur; otomatik yazma Zotero 10 kullanır. Son kullanıcının Python, Node.js veya Git kurması gerekmez.

### 1. Paketi indirin ve çıkarın

[Releases sayfasında](https://github.com/HasanBasriTaskin/Tez_Otomatize/releases) istediğiniz sürümü açın. **Assets → LiteraturKayit-<sürüm>.zip** dosyasını indirin; **Source code** dosyaları kurulum paketi değildir. ZIP'e sağ tıklayıp **Tümünü ayıkla** seçin. Çıkan klasörde `Kurulum.exe` ve `payload` birlikte bulunmalıdır. Eklentinin paket içindeki kopyası `payload\extension` altındadır.

### 2. Windows uygulamasını kurun

1. Kendinize ait bir proje klasörü oluşturun; örneğin `Belgeler\Literatur_Projem`. Önceki çalışmanıza devam ediyorsanız mevcut proje klasörünüzü kullanın.
2. Uygulama zaten çalışıyorsa önce yedek alın ve sistem tepsisindeki simgesinden **Çıkış** seçin.
3. **Kurulum.exe** dosyasını açın. **Proje ana klasörü / Klasör seç** alanında bu proje klasörünü seçin.
4. İstenirse **Windows oturumu açılınca başlat** seçeneğini işaretleyin; **Kur ve başlat** düğmesine basın. Yönetici izni gerekmez. Uygulama sistem tepsisinde başlar ve Başlat menüsü kısayolu oluşturulur.

**Kurucudaki klasör seçimi araştırma verileriniz içindir. Programın kurulum yeri otomatik belirlenir:**

| Konum | Görevi |
|---|---|
| ZIP'i çıkardığınız klasör | `Kurulum.exe` ve beraberindeki kurulum dosyaları |
| `%LOCALAPPDATA%\LiteraturKayit` | Windows programı, Chrome eklentisi ve yerel ayarlar; kurucu oluşturur |
| Seçtiğiniz proje klasörü | Excel, PNG, sorgu paketi, veri tabanı ve yedekler |

Bu nedenle proje olarak `payload` veya programın kurulum klasörünü seçmeyin. Proje için mevcut bir klasör seçilir; içindeki çalışma alt klasörlerini uygulama oluşturur.

### 3. Chrome eklentisini yükleyin

1. Chrome adres çubuğuna **`chrome://extensions`** yazın.
2. Sağ üstte **Geliştirici modu / Developer mode** seçeneğini açın.
3. **Paketlenmemiş öğe yükle / Load unpacked** düğmesine basın.
4. Klasör penceresinin adres alanına aşağıdaki yolu yapıştırıp klasörü seçin. Kurucu bu yolu panoya da kopyalar:

   ```text
   %LOCALAPPDATA%\LiteraturKayit\extension
   ```

5. Chrome'un uzantılar menüsünden **Literatür Kayıt Asistanı** simgesini araç çubuğuna sabitleyin. Güncelleme yapıyorsanız mevcut eklentide **Yenile ↻** yeterlidir; ikinci kopya yüklemeyin.
6. Araştırma sitesini açın. Eklenti simgesinden **Bu sitede etkinleştir** seçip izni verin. Üniversite proxy'si kullanılıyorsa izin açık olan proxy adresine verilir.

### 4. İlk kaydı kontrol edin

**Kayıtlar ve ayarlar → Ayarlar** bölümünde proje adı, takım kodu ve kaydı yapan kişiyi kaydedin. Sonuç sayfasında Ctrl+M yapıp PNG'de gerçek Windows saat/tarihinin ve adres çubuğunun göründüğünü kontrol edin. Sonra Ayarlar'daki saat/tarih kontrol kutusunu işaretleyip kaydedin. F11 tam ekran bu alanları gizleyebilir.

Sonraki kullanımlarda **Kurulum.exe** tekrar açılmaz; Başlat menüsündeki uygulama kullanılır. Bağlantı/okuma sorunu için [sorun giderme kılavuzuna](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/KILAVUZ.md#sorun-giderme-ve-kaldırma), ilk kontrol için [manuel test adımlarına](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/MANUEL_TEST.md) bakın. Güncellemede yeni paketin kurucusunu çalıştırın, aynı proje klasörünü seçin ve eklentiyi yenileyin. 0.3.0 veri tabanını günceller; eski sürüme dönüş için güncelleme öncesi yedek gerekir.

## Geliştirici: build ve dağıtım

### Hazırlık

Windows x64, **Python 3.12 x64** ve **Node.js 24** kurulu olmalıdır. Kaynağı GitHub Desktop veya **Code → Download ZIP** ile alabilirsiniz. Git kullanılıyorsa:

```powershell
git clone https://github.com/HasanBasriTaskin/Tez_Otomatize.git
cd Tez_Otomatize
```

Çalışmak istediğiniz sürümün kodunu seçin. Paket sürümü `package.json` dosyasından gelir. Aşağıdaki komutlar, `build.bat` ve `package.json` dosyalarının bulunduğu depo kökünde **PowerShell** üzerinden çalıştırılır. Uygulama yapısını değiştirmeden önce [uygulama planı ve teknik kararları](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/IMPLEMENTATION.md), otomasyon için [iş akışı planını](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/AUTOMATION_PLAN.md) inceleyin.

### Seçenek A — Tek komutla build

**build.bat** dosyasına çift tıklayın veya:

```powershell
.\build.bat
```

BAT sanal ortamı oluşturur, sabit bağımlılıkları kurar, tip/sözdizimi/güvenlik kontrolleri ile testleri çalıştırır; ardından **Windows EXE'leri, Chrome eklentisi ve kurulum ZIP'ini** üretip doğrular. Python ve Node.js önceden kurulmuş olmalıdır; bağımlılık kurulumu için internet gerekir. Hata varsa işlem durur. Sonucu okumak için açık kalan pencereyi bekletmeden kapatan otomasyon seçeneği: `.\build.bat --no-pause`.

### Seçenek B — BAT kullanmadan adım adım

**1. Ortamı ve bağımlılıkları hazırlayın:**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
npm.cmd ci
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TEMP = (Resolve-Path .tmp).Path
$env:TMP = $env:TEMP
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
```

**2. Kontrolleri ve testleri çalıştırın:**

```powershell
npm.cmd run typecheck
.\.venv\Scripts\python.exe -m compileall -q literature installer.py run_tray.py run_host.py
npm.cmd audit --audit-level=high
npm.cmd test
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

**3. Windows ve eklentiyi birlikte derleyip paketi doğrulayın:**

```powershell
.\.venv\Scripts\python.exe scripts/build-windows.py
.\.venv\Scripts\python.exe scripts/check-package.py
```

Komutları sırayla çalıştırın; bir adım hata verirse sonraki adıma geçmeyin. `build-windows.py` eklenti build'ini de çağırır. Sanal ortam aktivasyonu veya PowerShell güvenlik ayarı değişikliği gerekmez. Yalnız eklenti kaynakları değiştiyse `npm.cmd run build` kullanılabilir; bu komut EXE veya kurulum ZIP'ini yenilemez.

### Build tamamlanınca ne yapılır?

BAT ve manuel komutlar aynı çıktı düzenini kullanır. Tam build bitince `artifacts` içinde yalnız `release` kalır:

| Çıktı | Kullanım |
|---|---|
| `artifacts/release/LiteraturKayit-<sürüm>/Kurulum.exe` | Bu bilgisayarda kurulum/güncelleme; yanındaki `payload` ile çalışır |
| `artifacts/release/LiteraturKayit-<sürüm>/payload/extension` | Pakete giren Chrome eklentisi (kurulum bunu `%LOCALAPPDATA%\LiteraturKayit\extension` içine kopyalar) |
| `artifacts/release/LiteraturKayit-<sürüm>.zip` | Başka kullanıcıya verilecek tam kurulum paketi |

`artifacts/windows`, `artifacts/work` ve `artifacts/extension` build sırasında oluşan ara klasörlerdir; paketleme bitince silinir. Yalnız `npm.cmd run build` çalıştırılırsa `artifacts/extension` kalır.

**Kendi bilgisayarınıza uygulamak için:** tepsi uygulamasından çıkın, `artifacts/release/.../Kurulum.exe` ile mevcut proje klasörünü seçerek kurun; Chrome'da `%LOCALAPPDATA%\LiteraturKayit\extension` klasörünü yükleyin veya yenileyin. **Başkasına vermek için:** `artifacts/release` içindeki ZIP'in tamamını gönderin; alıcı yukarıdaki kurulum adımlarını uygular. Build tek başına kurulu uygulamayı güncellemez.

Tam build başlarken `artifacts` klasörünü temizler; saklanacak eski ZIP'leri önceden başka yere alın. Yalnız eklenti build'i `artifacts/extension` klasörünü temizler. Kullanıcı proje verileri bu alana konulmamalıdır. Bu çıktılar, `.venv`, `node_modules` ve `.tmp` Git dışında tutulur. Testlerin kapsamı ve gerçek cihazda yapılacak kontroller: [test raporu](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/TEST_RAPORU.md) ve [manuel testler](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/MANUEL_TEST.md).

### Actions ve yeni sürüm yayımlama

Dal push'ları Actions test/build paketini üretir. Paket sürümüyle aynı **vX.Y.Z** etiketi gönderildiğinde doğrulanan ZIP ve SHA-256 ayrıca **Releases** sayfasında yayımlanır. `release.json` içindeki `prerelease` alanı ön sürüm/kararlı ayrımını belirler; ön sürümler **Latest** kararlı sürümün yerini almaz. Sürüm numarası, notlar ve etiket komutları: [yayınlama adımları](https://github.com/HasanBasriTaskin/Tez_Otomatize/blob/main/docs/YAYINLAMA.md).

Build ve manuel kullanım için `.env` veya yapay zekâ API anahtarı gerekmez. Yerel Zotero erişim anahtarları Windows Kimlik Bilgileri Yöneticisi'nde saklanır; proje dosyaları ve kişisel ayarlar depoya gönderilmemelidir.

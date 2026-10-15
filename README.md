# Literatür Kayıt Asistanı

Windows 11 ve Chrome için literatür arama kayıt asistanı. Windows uygulaması gerçek monitör görüntüsünü alır; Chrome eklentisi aktif arama sekmesindeki sorgu, filtre ve sonuç sayısını okur. Kayıtlar SQLite'ta saklanır ve Excel'e aktarılır.

| Dal | Amaç | Durum |
|---|---|---|
| `main` | Günlük kullanım, 0.2.1 | Mevcut Ctrl+M ve onaylı yıl daraltma akışı |
| `feature/otomatize` | Yeni 0.3.0 otomatik tarama | Başlangıç + altı konu + RIS + Zotero; canlı kabul tamamlanmadı |

Bilgisayarda kurulu mevcut sürüm değiştirilmedi. Yeni otomasyon dalını indirmek veya Git dalını değiştirmek kurulu EXE'yi kendiliğinden güncellemez. Günlük kullanım için **main** paketini seçin. Scopus sonuç okuması gerçek projede kullanıldı; IEEE, ACM ve WoS canlı doğrulama bekliyor.

Depo yalnız uygulama kaynak kodunu içerir. Excel, ekran görüntüsü, RIS, SQLite, kişisel API anahtarı ve derlenmiş EXE dosyaları Git'e yüklenmez. EXE paketi aşağıdaki Actions adımlarından veya yerel derlemeyle alınır.

## ÖNEMLİ — Arama kelimeleri ve başka araştırmalara uyarlama

**TXT dosyasını değiştirmek otomasyonun sorgularını değiştirmez.** `main` / 0.2.1 sürümünde aramayı Scopus'ta siz yazarsınız; Ctrl+M o anki aramayı kaydeder. Bu sürümün yıl daraltması devam eder: kayıt sonrası öneri çıkar, siz onaylarsınız, yeni sonuçta tekrar Ctrl+M yaparsınız.

`feature/otomatize` / 0.3.0 geliştirme sürümü OEC-1017 için hazırlanmış bir başlangıç ve altı konu sorgusunu kullanır. Kaynak hazırlanırken `OEC-1017_O2_Sorgular.txt` esas alınmıştır; çalışma sırasında bu dosya okunmaz. Asıl sorgular bu dalın `literature/workflow.py` dosyasındaki `INITIAL` ve `TOPICS` sabitleridir. Başlatmadan önce **Otomatik tarama → Sorgu paketini göster** bölümünden okunabilir. Arayüzde sorgu düzenleyici veya TXT içe aktarma henüz yoktur.

Başka konuya uyarlayan geliştirici `feature/otomatize` dalında `INITIAL` ve `TOPICS` değerlerini, bunların beklentilerini içeren `tests/test_workflow.py` testlerini ve kendi sorgu belgesini birlikte güncellemelidir. Testlerden sonra EXE yeniden derlenip kurulur. `INITIAL` tam Scopus sorgusudur; `TOPICS` içindeki metinler `TITLE-ABS-KEY(...)` içine alınan kavram bloklarıdır. Konu adımlarının `Q` ile başlayan benzersiz kimlikleri korunmalıdır. Yıl ve yayın türü koşulları uygulama tarafından eklenir. Başlamış tarama sorgularının kopyasını sakladığı için değişiklikler yeni tarama oturumlarında geçerlidir.

Hazır paket, terimlerin bilimsel olarak yeterli olduğunun garantisi değildir. Rehbere göre 3–5 tohum makalenin yazar/dizin terimlerini kontrol edin; ilgili çalışmalar kaçıyorsa eş anlamlıları veya konu bloklarını, çok ilgisiz sonuç geliyorsa kapsamı gerekçesiyle güncelleyin. Bu değişiklikleri yeni aramalar olarak kaydedin. Tohum makale/terim doğrulaması henüz tamamlandı olarak işaretlenmemiştir. Otomasyon kendi başına yeni kelime üretmez veya makale uygunluğuna karar vermez.

Yıl kuralları sabittir: ilk sonuç ≤300 ise yıl sınırı yok; 301–1000 ise 2022–2026; ilk sonuç >1000 ise önce 2022–2026, bunun sonucu da >500 ise 2024–2026. Takvim ilerleyince yıllar kendiliğinden değişmez. Her konu ayrıca 300'ün altına düşene kadar daraltılmaz; konular ortak yıl aralığını kullanır.

**Başka bir kişiye dağıtırken:** günlük sürümde herkes kendi sorgusunu yazabilir ve kendi proje klasörünü kullanır. Yeni otomasyon genel amaçlı bir araştırma robotu değildir. Otomatik Zotero yazma hedefi mevcut TEZ grubuna ve koleksiyonlarına sabittir (`literature/zotero_writer.py`); yalnız TXT veya bir ayar değişikliğiyle başka gruba geçmez. Aynı grubu kullanacak kişinin erişimi olmalı; farklı grup/kütüphane desteği ayrıca geliştirilip test edilmelidir. Otomasyonun canlı kabulü tamamlanmadan günlük kurulumun üzerine yüklemeyin.

## Hızlı indirme: GitHub Actions

**Hazır günlük paket:** [0.2.1 kurulum ZIP'i — Releases](https://github.com/HasanBasriTaskin/Tez_Otomatize/releases/tag/v0.2.1). 15 Ekim 2026'daki ilk Actions denemesi, GitHub hesabının ödeme/harcama limiti nedeniyle runner başlamadan durdu. Bu hazır paket yerelde derlenip doğrulandı. Actions kullanmak için GitHub **Settings → Billing & plans** bölümündeki engeli giderip aşağıdaki adımları uygulayın.

1. [Actions → Windows test ve paket](https://github.com/HasanBasriTaskin/Tez_Otomatize/actions/workflows/windows.yml) sayfasını açın.
2. Başarılı **main** çalıştırmasını seçin. Kendiniz üretmek için **Run workflow → main → Run workflow** kullanın.
3. Çalıştırmanın altındaki **Artifacts** bölümünden `LiteraturKayit-Windows-…` dosyasını indirin. İçinde kurulum ZIP'i ve `.sha256` özeti bulunur.
4. İndirilen artifact ZIP'ini, ardından içindeki `LiteraturKayit-0.2.1.zip` dosyasını tamamen çıkarın. `Kurulum.exe` ile `payload` aynı klasörde kalmalı.
5. Aşağıdaki kurulum adımlarını uygulayın. Son kullanıcının Python, Node veya Git kurmasına gerek yoktur; Windows ve Chrome yeterlidir. Zotero özelliği için Zotero ayrıca kurulur.

Depo private olduğundan Actions indirmesi için depoya erişimi olan GitHub hesabı gerekir. Arkadaşınıza tam kurulum ZIP'ini iletebilirsiniz. Artifact saklama süresi bu iş akışında 14 gündür; daha sonra **Run workflow** ile tekrar üretilebilir. [GitHub artifact belgesi](https://docs.github.com/en/actions/tutorials/store-and-share-data)

## Kurulum

1. `release/LiteraturKayit-0.2.1/Kurulum.exe` dosyasını açın. ZIP kullanıyorsanız önce **tamamını** bir klasöre çıkarın; `payload` klasörü EXE’nin yanında kalmalı.
2. Kendinize ait bir proje klasörü oluşturun; örneğin `Belgeler\Tez_Hasan` veya `Belgeler\Tez_Arkadas`. Kurucuda bu klasörü seçip **Kur ve başlat** düğmesine basın. Mevcut kullanıcı kendi `OEC-1017_O2` klasörünü kullanabilir. Yönetici izni gerekmez. Windows başlangıcında çalıştırma isteğe bağlıdır.
3. Chrome’da `chrome://extensions` adresini açın. **Geliştirici modu → Paketlenmemiş öğe yükle** ile `%LOCALAPPDATA%\LiteraturKayit\extension` klasörünü seçin. Kurucu bu yolu panoya kopyalar.
4. Eklenti kimliği `bdboonffghjgpgnkbhekphddmncanlld` olmalı. Eklentiyi Chrome araç çubuğuna sabitleyin.
5. Eklentide **Kayıtlar ve ayarlar** bölümünü açın. Proje adı, takım kodu ve kaydı yapan kişiyi kontrol edin. Başlangıçta arama listesi boştur.
6. Araştırma sitesinde bir sonuç sayfası açın. Eklenti simgesinden **Bu sitede etkinleştir** seçin. Proxy kullanılıyorsa izin, gerçekten açık olan proxy adresi için verilir.
7. Sonuç sayfasına dönüp Ctrl+M yapın. İlk PNG’de Windows saati, tarih ve adres çubuğunun göründüğünü kontrol edin. Ayarlar’daki saat/tarih kontrolünü bundan sonra işaretleyin.

Günlük kullanım terminal gerektirmez. Başlat menüsündeki **Literatür Kayıt Asistanı** tepsi uygulamasını açar. Chrome bağlantısı da kapalı uygulamayı başlatabilir. Tepsi menüsünden duraklatma, son PNG ve proje klasörü erişilebilir. Chrome açılışında pencereyi Windows ile eşleştiren kısa süreli arka plan sekmesi oluşabilir; yakalama sırasında yeni sekme açılmaz.

Ana proje klasörünü seçtikten sonra uygulama `02_Ekranlar`, `03_Calisma/Veri/gecici`, `05_Teslim` ve `Yedekler` klasörlerini otomatik oluşturur. Excel `03_Calisma` altında ilk kayıtta üretilir; boş çalışma kitabı için **Excel’i güncelle** kullanılabilir. Başkasının Excel şablonunu veya SQLite veritabanını kopyalamak gerekmez.

## Bir aramayı kaydetme

Aramayı çalıştırın ve yüklenmenin bitmesini bekleyin. Sorgu, sonuç sayısı, Windows görev çubuğu ve adres çubuğu görünürken Ctrl+M’ye basın. Windows monitörün tamamını yakalar; ardından eklenti o penceredeki aktif sekmeyi okur. Bu sırada sekme değiştirmeyin.

Başarılı kayıt `S001` gibi bir kimlik alır. Görseller `02_Ekranlar/S001/` altında `S001_YYYYMMDD_a_sonuc.png` biçiminde tutulur. Tarih gerçek çekim anının İstanbul tarihidir. Aynı aramaya ek çekimler `_v02` gibi sürümlenir. Sorgu/filtre değişikliği veya farklı gün yeni çalıştırma oluşturur. Aynı sorguyu bilerek yeniden çalıştırırken **Sonraki yakalamayı yeni arama say** kullanılabilir.

Eşleşme belirsizse PNG korunur; **Eksik kayıtlar → Kontrol et** bölümünde gerçek PNG’ye bakarak alanları tamamlayın. İçe aktarılan PNG’nin çekim zamanı bilinmiyorsa bilinmiyor olarak kalır. Sayfa çalıştırılmış sorguyu göstermiyorsa makale başlığından sorgu veya sonuç sayısı üretilmez.

## Onaylı Scopus daraltma akışı

Ctrl+M önce mevcut PNG ve arama kaydını saklar. Sonuç kesin olarak okunmuşsa rehberdeki sabit kuralları kontrol eder:

| İlk yıl sınırsız sonuç | Öneri |
|---|---|
| 0–300 | Yıl sınırı önerilmez |
| 301–1000 | 2022–2026 |
| 1000 üstü | Önce 2022–2026; bunun sonucu da 500 üstüyse 2024–2026 |

**Aramayı daraltalım mı?** penceresinde tam yeni sorgu ve gerekçe görünür. **Uygula ve ara** seçilince aynı Scopus sekmesindeki yıl alanları kontrol edilip doldurulur ve yıl aralığı uygulanır. Sonuçların yüklenmesini bekleyip yeniden **Ctrl+M** yapın. Yeni arama, önceki arama kimliğine ve daraltma gerekçesine bağlanır; önceki PNG korunur. İkinci yıl önerisi gerekiyorsa bu yeni çekimden sonra çıkar. Excel'in 11 sütunu korunur; bağlantı gerekçesi Açıklama alanına yazılır.

**Şimdi değil** sayfayı değiştirmez. Öneri kayıt ayrıntısındaki **Daraltma önerisi** düğmesinden yeniden açılabilir. Otomatik uygulama sayfayı kesin tanıyamazsa **Sorguyu kopyala, elle uygula** ile aynı Scopus sekmesinde gelişmiş aramaya yapıştırıp çalıştırın, sonra Ctrl+M yapın. Yaklaşık/bilinmeyen sayılardan veya açıklanmamış mevcut yıl koşullarından yeni daraltma zinciri tahmin edilmez. Sorgu/sonuç değişmişse yeniden yakalama gerekir.

Yıllar takvim ilerledikçe kendiliğinden değişmez. Bu sürüm otomatik olarak yalnız Scopus yıl aralığını uygular; konu/anahtar sözcük ekleme kararı kullanıcıya aittir.

## Sitelerden bilgi nasıl okunur?

İlk sürüm görünür semantik etiketleri ve sonuç özetlerini okur. Site/proxy düzeni farklıysa otomatik tahmin tamamlanmış kayıt sayılmaz. Sorgu kutusundaki henüz çalıştırılmamış metin sonuçlarla eşleştirilmez. Sıfır, bilinmeyen, yaklaşık ve “en az” sayımları ayrıdır.

Gerekirse sonuç sayfasındaki **çalıştırılmış sorgu**, **toplam sonuç sayısı**, **uygulanan filtreler** ve **aranan alan** metnini ayrı ayrı seçip sağ tık menüsündeki **Literatür kaydı** alanlarına bağlayın. Bu seçim aynı site/adres yapısı için saklanır. Filtre seçimi, kullanılabilir bütün filtreleri değil uygulanmış filtre özetini göstermelidir. Sonraki Ctrl+M bu alanları okuyabilir. Site düzeni değişirse yeniden eşleştirin. Sorguyu doğrudan okuyamadığınızda manuel tamamlama kullanın.

Tanılama düğmesi seçili alanlardan sınırlı metin kaydeder; tüm HTML, çerez ve oturum bilgisi arşivlenmez. Mevcut semantik çıkarıcı dört platformun adını tanır; bu, her platformun canlı DOM’unun doğrulandığı anlamına gelmez. Gerçek sayfa üzerinden adapter iyileştirmeleri kabul testiyle yapılır.

## Excel ve klasörler

| Klasör | İçerik |
|---|---|
| `02_Ekranlar` | Özgün PNG’ler ve her aramanın görsel dizini |
| `03_Calisma/Veri` | SQLite, geçici/eksik işler ve tanılama |
| `03_Calisma` | Üretilen Excel görünümü |
| `05_Teslim` | PDF, BibTeX ve kaynak manifesti |
| `Yedekler` | Tutarlı proje yedekleri ve Excel koruma kopyaları |
| `Uygulama` | Kaynak kod ve kurulum paketi |

SQLite asıl kayıttır. Düzenlemeleri eklentiden yapın; Excel’den geri içe alma yoktur. Arama_Kaydi/Matris/Hariç için incelenen referansın 11/28/6 sütun başlıkları kullanılır; eski satırlar aktarılmaz. Projedeki mevcut Excel uygulamanın ürettiği dosya değilse korunur ve yeni sürüm oluşturulur. Kullanıcının sonradan değiştirdiği veya kilitlediği dosya da ezilmez. Mesajdaki gerçek çıktı yolunu kullanın.

Arama_Kaydi’nde bir arama bir satırdır. **Ekran dosyası** bağlantısı bütün görsellerin bulunduğu göreli dizini açar. Proje klasörü birlikte taşındığında bağlantılar korunur. **Dışa aktarılan kayıt sayısı** RIS/BibTeX okunmadığı için boş kalır; toplam sonuç sayısına eşitlenmez.

## Zotero ve teslim çıktıları

Önce temel arama akışını doğrulayın. Ardından Zotero’yu açın. Zotero **Settings → Advanced → Allow other applications on this computer to communicate with Zotero** ayarı yerel API erişimini açar. Yerel kişisel kütüphane `users/0` kullanır; okuma için API anahtarı gerekmez. Grup kütüphanesi `groups/ID` biçimindedir. [Zotero yerel API belgesi](https://www.zotero.org/support/dev/web_api/v3/local_api)

**Zotero ve notlar** bölümünde bağlantı ayarlarını kaydedin, koleksiyonları getirin ve Aday/Başlık-özet/Tam metin dahil/Hariç rollerini seçin. **Not şablonunu kopyala** ile her kaynağa bağlı bir Zotero notu oluşturun. Şablon alanlarını kaynak metne bakarak doldurun; bilgi yoksa “raporlanmadı” yazın. **Zotero’dan oku** sonrasında anotasyonu kontrol edip kaynak arama kimliklerini bağlayın. Aynı makaleye S001 ve S002 birlikte bağlanabilir. Çelişen koleksiyonlar/notlar ve DOI tekrar adayları gösterilir; DOI ile sessiz birleştirme yapılmaz.

Uygulama Zotero’ya yazmaz; yerel taslak notlar ayrıca tutulur. Web API seçilirse doğru kullanıcı/grup kimliği ve salt okunur anahtar gerekir. Anahtar Windows Kimlik Bilgileri Yöneticisi’nde tutulur. Yerel ve Web kütüphane ayarlarını kaydetmeden anahtar kaydetmeyin.

Scopus'taki toplam sonuç sayısı Zotero'ya aktarılacak kaynak sayısı değildir. Önce rehbere göre aramayı daraltın; inceleyeceğiniz kaynakları kendiniz Zotero'ya alın. Asistan seçili Zotero kütüphanesini okur. Bu bilgisayarda TEZ grubundaki Aday, Başlık/Özet, Tam Metin/Dahil ve Hariç koleksiyonları eşleştirilmiştir.

**Çıktılar ve yedek** bölümünden:

- `OEC-1017_O2_KaynakListesi.pdf` ve `OEC-1017_O2_kaynaklar.bib` aynı dahil kaynak kümesinden üretilir. Kontrol edilmemiş anotasyon final çıktıyı engeller; açıkça TASLAK seçilebilir.
- `OEC-1017_O2_AramaEkranlari.pdf` özgün PNG’leri sayfalara yerleştirir. Açıklama görüntünün dışında tutulur.
- Matris/Hariç güncellemesi için **Excel’i güncelle** kullanılır.
- Eksik alanlar çıktı raporunda gösterilir. Gerçek teslim kartı ayrıca kontrol edilmelidir.

## Yedek ve geri yükleme

**Yedek al**, SQLite’ın tutarlı anlık kopyasını ve proje dosyalarını bir ZIP’e koyar. Gizli API anahtarı ve program kodu yedeğe girmez. **Yedeği geri yükle** dosya yollarını, SHA-256 özetlerini ve SQLite bütünlüğünü kontrol ederek yeni klasör oluşturur. Ardından Ayarlar’dan o klasöre geçebilirsiniz. Aynı SQLite dosyasını iki bilgisayarda eşzamanlı yazmayın.

SHA-256, dosyanın sonradan değişip değişmediğini denetler; aramanın doğruluğunu veya çekim tarihini tek başına kanıtlamaz. Orijinal PNG’ye sonradan saat, sorgu veya sonuç sayısı eklenmez.

## Sorun giderme ve kaldırma

- **Windows bağlantısı yok:** Kurulum.exe’yi çalıştırın, tepsi uygulamasını açın, Chrome eklentisini yeniden yükleyip Yenile’ye basın. Eklenti kimliği yukarıdakiyle eşleşmeli.
- **Kısayol kullanılamıyor:** Ctrl+Alt+M seçin. Duraklatma kısayolu diğer uygulamalara bırakır.
- **Chrome önde değil/site izni yok:** Sonuç sayfasını öne getirin ve eklenti simgesinden o siteyi etkinleştirin. F11 tam ekran görev çubuğu/adres çubuğunu gizleyebilir.
- **Görüntü var ama kayıt eksik:** Eksik kayıtlar bölümünden PNG’yi açın. Sayfa yüklenmesi, sekme değişikliği veya okunamayan alanlar otomatik doğrulamayı durdurur.
- **Excel ayrı sürüm:** Özgün dosya korunmuştur. Bildirimdeki yeni yolu açın; kayıt SQLite’tadır.
- **Zotero HTTP 403:** Zotero’nun yerel erişim ayarını kontrol edin. Uygulama erişim engelini aşmaz.
- Tanılama günlüğü `%LOCALAPPDATA%\LiteraturKayit\application.log` altındadır. Günlükler tüm DOM/sorgu/anahtar içermemelidir.

Güncellemeden önce tepsi menüsünden **Çıkış** seçin, sonra yeni paketin Kurulum.exe dosyasını çalıştırın ve Chrome eklentisini yeniden yükleyin. Kaldırmak için Başlat menüsündeki **Kaydı kaldır** aracını ve ardından Chrome’un eklenti kaldırma düğmesini kullanın. Araç proje dosyalarını silmez; kurulum klasörü de bilerek korunur ve daha sonra elle silinebilir.

## Geliştirme ve test

Python 3.12 ve Node.js gerekir. Bağımlılıklar `requirements.lock` ve `package-lock.json` ile sabittir. Venv kurup `pip install -r requirements.lock`, ardından `npm ci` çalıştırın. Geliştirme ortamı TEMP izin hatası verirse TEMP/TMP için depo içindeki `.tmp` klasörünü kullanın.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
.\.venv\Scripts\python.exe scripts\native-smoke.py --packaged
.\.venv\Scripts\python.exe scripts\build-windows.py
```

Native smoke testi normal Windows oturumunda çalıştırılır; güvenlik sandbox’ı RegisterHotKey’yi reddedebilir. Geçici Ctrl+Alt+9 kullanır ve tez verisine yazmaz. Test sırasında tepsi uygulamasını kapatın.

Kabul adımları: [MANUEL_TEST.md](docs/MANUEL_TEST.md). Doğrulama kapsamı: [TEST_RAPORU.md](docs/TEST_RAPORU.md). Mimari kararlar: [IMPLEMENTATION.md](docs/IMPLEMENTATION.md).

## Kaynak koddan EXE oluşturma — adım adım

Windows x64 üzerinde Python **3.12**, Node.js **24** ve Git kurulu olmalı. Windows bağımlılıkları nedeniyle bu EXE derlemesi Windows runner/bilgisayarda yapılır. `package.json` sürümü paket klasörünü ve Chrome manifest sürümünü belirler.

PowerShell'de:

```powershell
git clone https://github.com/HasanBasriTaskin/Tez_Otomatize.git
cd Tez_Otomatize
git switch main
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
npm.cmd ci
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TEMP = (Resolve-Path .tmp).Path
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd run typecheck
npm.cmd test
.\.venv\Scripts\python.exe scripts/build-windows.py
.\.venv\Scripts\python.exe scripts/check-package.py
```

Bir komut başarısız olursa sonraki adıma geçmeden hatayı düzeltin. Aktivasyon betiği veya PowerShell execution-policy değişikliği gerekmez. Derleme betiği Chrome eklentisini esbuild ile, Windows programlarını PyInstaller ile paketler:

```text
release/
  LiteraturKayit-0.2.1.zip
  LiteraturKayit-0.2.1.zip.sha256
  LiteraturKayit-0.2.1/
    Kurulum.exe
    README.md
    MANUEL_TEST.md
    TEST_RAPORU.md
    payload/
      tray/LiteraturKayit.exe
      host/NativeHost.exe
      extension/manifest.json
      extension/worker.js
      product.json
```

`payload` içindeki diğer DLL/veri dosyaları da gereklidir; sadece tek EXE'yi kopyalamayın. Pakette üreticinin bilgisayarına ait proje yolu bulunmaz; kurulacak bilgisayarda klasör seçilir. Yalnız eklentiyi derlemek için `npm.cmd run build` yeterlidir; çıktı `extension/dist` olur. `product.json` sabit eklenti kimliğini ve açık anahtarı tutar; rastgele yeniden üretmeyin.

## CI nasıl çalışıyor?

[.github/workflows/windows.yml](.github/workflows/windows.yml), `main` ve `feature/otomatize` push'larında, main'e açılan PR'larda ve elle **Run workflow** tetiklenince çalışır. Windows 2022 runner'da sabit bağımlılıklar kurulur; TypeScript, Python sözdizimi, Node güvenlik kontrolü ve testler geçerse Windows paketi üretilir. ZIP içeriği, EXE başlıkları ve sürüm doğrulanır; SHA-256 oluşturulup artifact yüklenir. Test veya derleme hatasında paket yayınlanmaz. Bilgisayarınıza otomatik kurulum yapılmaz.

CI için Scopus/Zotero/API anahtarı veya ek repository secret gerekmez. CI gerçek üniversite/Scopus oturumuna giriş yapmaz ve masaüstündeki saat/PNG uyumunu doğrulayamaz. Bu kısım manuel kabul testidir. Actions hiç başlamıyorsa repository **Actions** ayarını ve hesabınızın Actions kullanım sınırını kontrol edin; kota yoksa yukarıdaki yerel komutlarla aynı paketi üretebilirsiniz. Buradaki CI çalışması Codex sohbet kotasından bağımsızdır; GitHub'ın kendi kullanım kuralları geçerlidir.

## İki kişiyle çalışma ve sonradan birleştirme

- İkiniz de aynı **main** paketini kendi bilgisayarınıza kurun; ayrı boş proje klasörleri seçin.
- **Ayarlar → Kaydı yapan kişi** alanına kendi adınızı, takım koduna aynı `OEC-1017` değerini yazın. Her uygulama kendi SQLite, Excel ve PNG dosyalarını oluşturur.
- Görev/konu paylaşımınızı önceden belirleyin. Ham sorguyu, filtreleri ve her aramanın gerçek kanıtını koruyun.
- Değiş tokuş için **Çıktılar ve yedek → Yedek al** kullanın. ZIP'leri kişi ve tarihle ayırt edin: `Hasan_2026-10-15.zip`, `Arkadas_2026-10-15.zip` gibi. Özgün yedekleri saklayın.
- İki makinede de `S001` oluşması normaldir. Aynı adlı klasör/Excel/SQLite dosyalarını üst üste kopyalamayın. Birleştirmede arama kimliklerinin ve kanıt yollarının yeniden eşlenmesi, kaynak tekrarlarının kontrolü gerekir.
- **Bu sürümde otomatik proje birleştirici yoktur.** Son birleştirme ayrı bir çalışma olarak yapılacak; yalnız Excel satırlarını birleştirmek PNG ve Zotero ilişkilerini birleştirmez.
- Ortak Zotero TEZ grubunu kullanacaksanız arkadaşınız grup üyesi olmalı. Ayrı Zotero kütüphanelerindeki item key'ler aynı kabul edilmez; kütüphane kimliğiyle birlikte değerlendirilir.

## En son: sizin yapacağınız manuel adımlar

1. Günlük kullanım ve arkadaş kurulumu için **main** dalının başarılı Actions paketini indirin veya yukarıdaki komutlarla derleyin.
2. Tam ZIP'i çıkarın, boş/size ait proje klasörünü seçip `Kurulum.exe` ile kurun. Chrome'a `%LOCALAPPDATA%\LiteraturKayit\extension` klasörünü paketlenmemiş eklenti olarak yükleyin.
3. Kaydı yapan kişi ve takım kodunu ayarlayın. Scopus/proxy sayfasında eklentinin **Bu sitede etkinleştir** düğmesini kullanın.
4. Bir arama yapıp Ctrl+M'ye basın. PNG'de gerçek Windows saat/tarihi ve adres çubuğunu; Excel'de sorgu ve sonuç sayısını kontrol edin. Ayarlar'daki saat/tarih doğrulamasını işaretleyin.
5. Daraltma önerisi çıkarsa onaylayın; sonuçlar yüklenince tekrar Ctrl+M yapın. Mevcut günlük sürüm bu şekilde çalışır.
6. Zotero gerekiyorsa **Settings → Advanced → Allow other applications on this computer to communicate with Zotero** ayarını açın; kütüphane/koleksiyon eşleştirmesini kontrol edin.
7. Çalışma sonunda uygulamadan yedek alın. İki kişinin yedeğini ayrı saklayın; birleştirme için ikisi birlikte kullanılacak.
8. `feature/otomatize` dalını günlük kurulumun üzerine kurmayın. Otomatik sürümün gerçek arama–RIS–Zotero ve tam paket testleri ayrı test ortamında tamamlanmalı.

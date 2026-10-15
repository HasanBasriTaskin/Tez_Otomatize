# Ayrıntılı kullanım ve geliştirme kılavuzu

Windows 11 ve Chrome için literatür arama kayıt asistanı. Windows uygulaması gerçek monitör görüntüsünü alır; Chrome eklentisi aktif arama sekmesindeki sorgu, filtre ve sonuç sayısını okur. Kayıtlar SQLite'ta saklanır ve Excel'e aktarılır.

| Dal | Amaç | Durum |
|---|---|---|
| `main` | Günlük kullanım, 0.2.1 | Mevcut Ctrl+M ve onaylı yıl daraltma akışı |
| `feature/otomatize` | Yeni 0.3.0 otomatik tarama | Başlangıç + altı konu + RIS + Zotero; canlı kabul tamamlanmadı |

Git dalını değiştirmek kurulu EXE'yi kendiliğinden güncellemez. Günlük kullanım için **main** paketini seçin. Scopus sonuç okuması gerçek projede kullanıldı; IEEE, ACM ve WoS canlı doğrulama bekliyor.

Depo yalnız uygulama kaynak kodunu içerir. Excel, ekran görüntüsü, RIS, SQLite, kişisel API anahtarı ve derlenmiş EXE dosyaları Git'e yüklenmez. EXE paketi aşağıdaki Actions adımlarından veya yerel derlemeyle alınır.

## En kısa yol

- **Sadece kullanacağım:** [Hazır manuel sürümü indir](https://github.com/HasanBasriTaskin/Tez_Otomatize/releases/tag/v0.2.1) → ZIP'in tamamını çıkar → **Kurulum.exe** → proje klasörünü seç → **Kur ve başlat**. Sonra [Chrome eklentisini bir kez yükle](#kurulum). Python, Node.js veya Git gerekmez.
- **Yeni geliştirme sürümünü kullanacağım:** [0.3.0 ön sürümünü](https://github.com/HasanBasriTaskin/Tez_Otomatize/releases/tag/v0.3.0) indir; aynı kurulum adımlarını uygula.
- **Kendi bilgisayarımda build alacağım:** Python 3.12 x64 ve Node.js 24 kuruluysa depo kökündeki **[build.bat](../build.bat)** dosyasına çift tıkla. Hem Windows programları hem Chrome eklentisi hazırlanır. Sonuç **artifacts/release** içindedir. PowerShell'den tek komut: `./build.bat`.

Build işlemi bağımlılıkları kurar, testleri çalıştırır, eski build çıktısını temizler ve kurulum ZIP'ini doğrular. Bir adım başarısızsa durur. Uygulamayı bilgisayarınıza kurmak için oluşan **Kurulum.exe** kullanılır. Günlük açılışta build yapmayın; Başlat menüsünden **Literatür Kayıt Asistanı** yeterlidir.

## ÖNEMLİ — Arama kelimeleri ve başka araştırmalara uyarlama

**Sorguları değiştirmek için yeniden build gerekmez.** Bu özellik `feature/otomatize` geliştirme dalındadır. Yeni sorgu düzenleyicisini içeren sürümü bir kez kurduktan sonra arama kelimeleri arayüzden veya proje dosyasından değiştirilebilir. Mevcut 0.2.1 kurulumuna kendiliğinden eklenmez.

**Manuel kullanım (`main` / 0.2.1 ve yeni sürüm):** aramayı Scopus'ta kendiniz yazarsınız. Ctrl+M o anki aramayı kaydeder ve yıl daraltmasını kontrol eder. Öneriyi onaylarsanız daraltılmış sonuçta tekrar Ctrl+M yaparsınız. Sonraki konuya otomatik geçmez; sizin sonraki sorgunuzu ve Ctrl+M'nizi bekler. Hazır sorgu paketi manuel kullanımı sınırlamaz.

**Otomatik kullanım:** **Otomatik tarama → Sorgu paketi → Sorguları düzenle** bölümünde paket adını, başlangıç sorgusunu ve konu terimlerini değiştirin. Konu ekleyip çıkarabilir, 1–20 konu kullanabilirsiniz. **Sorgu paketini kaydet** düğmesi değişiklikleri proje klasöründeki `03_Calisma/sorgu-paketi.json` dosyasına yazar. Eski dosya `Yedekler` altında korunur. **Sorgu paketini göster** ile kaydedilen metinleri kontrol edip **Taramayı başlat** seçin. Bu akış ara Ctrl+M veya yıl onayı beklemez. Kaydedilmemiş düzenlemelerle yeni tarama başlatılmaz.

**Dosyadan düzenleme:** aynı JSON dosyasını UTF-8 olarak düzenleyip arayüzde **Değişiklikleri bırak ve dosyadan yükle** seçin. Bu düğme kaydedilmemiş form değişikliklerini bırakır. `.txt` sorgu belgesi otomatik okunmaz. Dosya yoksa OEC-1017 başlangıç ve altı konu paketi oluşturulur; bozuk dosyada eski varsayılanlarla sessizce tarama yapılmaz. JSON içe aktarma için dosyayı kendi projenizin aynı konumuna koymanız yeterlidir; başka bir kişinin SQLite/Excel dosyasını kopyalamayın.

JSON alanları: `schema: 1`, `name` (paket adı), `initial` (tam `TITLE-ABS-KEY(...)` sorgusu), `topics` (sıralı konu listesi). Her konuda `code` (Q01 gibi benzersiz kimlik), `label` (konu adı), `query` (yalnız kavram blokları) bulunur. Konu sorgularına `TITLE-ABS-KEY(...)`, yıl ve yayın türü koşullarını uygulama ekler; bunları konu metnine tekrar yazmayın. Başlangıca da yıl/tür filtresi eklemeyin. Dosya en fazla 128 KB olabilir. Parantez/tırnak ve temel biçim kontrolü yapılır; Scopus'un bütün sorgu dilini doğrulayan bir editör değildir.

Başlamış tarama kendi paket kopyasını saklar. Formdan paket değiştirmek için mevcut taramayı tamamlayın veya **Durdur** seçin. Dosya dışarıdan değiştirilse bile **Devam et** eski oturumun sorgularını kullanır; yeni paket yeni taramada uygulanır. Dosya önizlemeden sonra değişirse uygulama yeniden yüklemenizi ister. Yıl kararları aşağıdaki rehber kurallarıyla devam eder.

Hazır paket, terimlerin bilimsel olarak yeterli olduğunun garantisi değildir. Rehbere göre 3–5 tohum makalenin yazar/dizin terimlerini kontrol edin; ilgili çalışmalar kaçıyorsa eş anlamlıları veya konu bloklarını, çok ilgisiz sonuç geliyorsa kapsamı gerekçesiyle güncelleyin. Bu değişiklikleri yeni aramalar olarak kaydedin. Tohum makale/terim doğrulaması henüz tamamlandı olarak işaretlenmemiştir. Otomasyon kendi başına yeni kelime üretmez veya makale uygunluğuna karar vermez.

Yıl kuralları sabittir: ilk sonuç ≤300 ise yıl sınırı yok; 301–1000 ise 2022–2026; ilk sonuç >1000 ise önce 2022–2026, bunun sonucu da >500 ise 2024–2026. Takvim ilerleyince yıllar kendiliğinden değişmez. Her konu ayrıca 300'ün altına düşene kadar daraltılmaz; konular ortak yıl aralığını kullanır.

**Başka bir kişiye dağıtırken:** günlük sürümde herkes kendi sorgusunu yazabilir ve kendi proje klasörünü kullanır. Yeni otomasyon genel amaçlı bir araştırma robotu değildir. Otomatik Zotero yazma hedefi mevcut TEZ grubuna ve koleksiyonlarına sabittir (`literature/zotero_writer.py`); sorgu JSON dosyasını değiştirerek başka gruba geçmez. Aynı grubu kullanacak kişinin erişimi olmalı; farklı grup/kütüphane desteği ayrıca geliştirilip test edilmelidir. Otomasyonun canlı kabulü tamamlanmış değildir.

## Hızlı indirme: GitHub Actions

**Bilgisayarınızda build almak zorunda değilsiniz.** Push sonrasında GitHub Actions testleri ve Windows build'ini otomatik çalıştırır. Depo public ve Actions çalışıyor. Hazır manuel sürüm ayrıca [Releases](https://github.com/HasanBasriTaskin/Tez_Otomatize/releases/tag/v0.2.1) sayfasındadır.

1. [Actions → Windows test ve paket](https://github.com/HasanBasriTaskin/Tez_Otomatize/actions/workflows/windows.yml) sayfasını açın.
2. İstediğiniz dalın yeşil işaretli başarılı çalıştırmasını seçin: **main** manuel sürüm; **feature/otomatize** geliştirme sürümü. Yazma yetkisi olanlar **Run workflow → dalı seç → Run workflow** ile de üretebilir.
3. Çalıştırmanın altındaki **Artifacts** bölümünden `LiteraturKayit-Windows-…` dosyasını indirin. İçinde kurulum ZIP'i ve `.sha256` özeti bulunur.
4. İndirilen artifact ZIP'ini, ardından içindeki `LiteraturKayit-<sürüm>.zip` dosyasını tamamen çıkarın. `Kurulum.exe` ile `payload` aynı klasörde kalmalı.
5. Aşağıdaki kurulum adımlarını uygulayın. Son kullanıcının Python, Node veya Git kurmasına gerek yoktur; Windows ve Chrome yeterlidir. Zotero özelliği için Zotero ayrıca kurulur.

Public depoda herkes kodu okuyabilir. Actions artifact'ini indirmek için GitHub hesabıyla oturum açmak gerekir; collaborator olmak gerekmez. Releases'teki hazır ZIP doğrudan indirilebilir. Arkadaşınıza tam kurulum ZIP'ini de iletebilirsiniz. Artifact saklama süresi 14 gündür. [GitHub indirme koşulları](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts?tool=webui)

## Kurulum

1. İndirdiğiniz ZIP'in **tamamını** çıkarıp içindeki `Kurulum.exe` dosyasını açın; `payload` klasörü EXE'nin yanında kalmalı. Yerel build aldıysanız dosya `artifacts/release/LiteraturKayit-<sürüm>/Kurulum.exe` konumundadır.
2. Kendinize ait boş bir proje klasörü oluşturup kurucuda seçin; örneğin `Belgeler\Tez_Arkadas`. Sonra **Kur ve başlat** düğmesine basın. Yönetici izni gerekmez. Windows başlangıcında çalıştırma isteğe bağlıdır.
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
.\.venv\Scripts\python.exe scripts\build-windows.py
.\.venv\Scripts\python.exe scripts\native-smoke.py --packaged
```

Native smoke testi normal Windows oturumunda çalıştırılır; güvenlik sandbox’ı RegisterHotKey’yi reddedebilir. Geçici Ctrl+Alt+9 kullanır ve tez verisine yazmaz. Test sırasında tepsi uygulamasını kapatın.

Kabul adımları: [MANUEL_TEST.md](MANUEL_TEST.md). Doğrulama kapsamı: [TEST_RAPORU.md](TEST_RAPORU.md). Mimari kararlar: [IMPLEMENTATION.md](IMPLEMENTATION.md).

## Kaynak koddan build

Bir kez [Python **3.12 x64**](https://www.python.org/downloads/windows/) ve [Node.js **24**](https://nodejs.org/en/download) kurun. Node.js kurulumundan sonra terminali yeniden açın. Kaynağı GitHub Desktop ile alın veya **Code → Download ZIP** ile indirip çıkarın; ZIP kullanıyorsanız Git gerekmez. Windows bağımlılıkları nedeniyle EXE build'i Windows'ta yapılır. `package.json` sürümü paket klasörünü ve Chrome manifest sürümünü belirler.

**Her build için:** kökteki **build.bat** dosyasına çift tıklayın veya PowerShell'de `./build.bat` çalıştırın. İlk sefer `.venv` otomatik oluşturulur. Sabit Python/Node bağımlılıkları kurulur, TypeScript/sözdizimi/güvenlik kontrolleri ve testler çalışır, Windows ve eklenti birlikte derlenir, ZIP ve SHA-256 doğrulanır. İnternet gerekir. Python/Node yoksa veya sürümleri uygun değilse açıklama gösterilir; bilgisayara sessizce başka program kurulmaz. Pencere sonunda sonucu okuyabilmeniz için açık kalır. CI/terminal otomasyonu için `build.bat --no-pause` aynı işlemi bekleme yapmadan çalıştırır ve hata kodunu döndürür.

<details>
<summary>Tek tek komut kullanmak isteyenler için manuel alternatif</summary>

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

Bir komut başarısız olursa sonraki adıma geçmeden hatayı düzeltin. Aktivasyon betiği veya PowerShell execution-policy değişikliği gerekmez.

</details>

Chrome eklentisi esbuild, Windows programları PyInstaller ile aynı ana klasöre paketlenir:

```text
artifacts/
  extension/                     # Chrome'a yüklenebilen eklenti build'i
    manifest.json
    worker.js
    ...
  windows/                       # Paketlenmiş Windows programları
    Kurulum.exe
    LiteraturKayit/LiteraturKayit.exe
    NativeHost/NativeHost.exe
  work/                          # PyInstaller önbelleği, spec ve geçici dosyalar
  release/                       # Kullanıcıya verilecek tam paket
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
        product.json
```

**Build temizliği:** `scripts/build-windows.py` her çalışmada önce `artifacts` klasörünün tamamını temizler; eski sürüm ZIP'leri dahil yalnız yeni çıktılar kalır. `npm run build` sadece `artifacts/extension` klasörünü temizler. Saklamak istediğiniz eski kurulum ZIP'ini yeni build'den önce bu klasörün dışına alın. `artifacts` içine elle kaynak, ayar veya tez verisi koymayın. Klasör başka konuma yönlenen bir bağlantıysa temizlik durur. EXE, geçici dosya ve spec yolları [PyInstaller'ın çıktı seçenekleriyle](https://pyinstaller.org/en/stable/usage.html#options) belirlenir.

`artifacts/`, eski `build/`, `dist/`, `release/`, `extension/dist/`, `.spec` ve derlenmiş Windows dosyaları `.gitignore` içindedir. GitHub Desktop'ta yalnız kaynak değişiklikleri görünür. `.tmp` test çalışma alanı ve `qa-output` örnek çıktıları da izlenmez. Kurulu uygulamanın `%LOCALAPPDATA%\LiteraturKayit` klasörü ve proje kayıtları build temizliğine dahil değildir. Build almak uygulamayı güncellemez; kurulum için **artifacts/release** içindeki tam paket kullanılır, `windows/Kurulum.exe` tek başına dağıtılmaz.

`payload` içindeki diğer DLL/veri dosyaları da gereklidir; sadece tek EXE'yi kopyalamayın. Pakette üreticinin bilgisayarına ait proje yolu bulunmaz; kurulacak bilgisayarda klasör seçilir. Yalnız eklentiyi derlemek için `npm.cmd run build` yeterlidir; çıktı `artifacts/extension` olur. `product.json` sabit eklenti kimliğini ve açık anahtarı tutar; rastgele yeniden üretmeyin.

## CI nasıl çalışıyor?

[.github/workflows/windows.yml](../.github/workflows/windows.yml), `main` ve `feature/otomatize` push'larında, main'e açılan PR'larda ve elle **Run workflow** tetiklenince çalışır. Windows 2022 runner Python 3.12 ve Node.js 24'ü kurar; ardından yereldekiyle aynı **build.bat --no-pause** akışını çalıştırır. ZIP içeriği, EXE başlıkları ve sürüm doğrulanır; SHA-256 oluşturulup artifact yüklenir. Test veya derleme hatasında yeni paket yüklenmez. Bilgisayarınıza otomatik kurulum yapılmaz. Dal push'ları Actions paketi üretir. Sürüm etiketi (`vX.Y.Z`) push edildiğinde test/build sonrasında Releases yayını yapılır. Ayrıntılar: [Sürüm yayımlama](YAYINLAMA.md).

CI için Scopus/Zotero/API anahtarı veya ek repository secret gerekmez. CI gerçek üniversite/Scopus oturumuna giriş yapmaz ve masaüstündeki saat/PNG uyumunu doğrulayamaz. Bu kısım manuel kabul testidir. Actions hiç başlamıyorsa repository **Actions** ayarını ve hesabınızın Actions kullanım sınırını kontrol edin; kota yoksa yukarıdaki yerel komutlarla aynı paketi üretebilirsiniz. Buradaki CI çalışması Codex sohbet kotasından bağımsızdır; GitHub'ın kendi kullanım kuralları geçerlidir.

## Public depo, anahtarlar ve katkı yetkisi

Bu uygulama build ve manuel kayıt için `.env` veya yapay zekâ API anahtarı istemez. `product.json` içindeki `public_key` Chrome eklentisinin **açık anahtarıdır**, parola değildir. Zotero'nun sonradan verdiği erişim anahtarı Windows Kimlik Bilgileri Yöneticisi'nde tutulur; Git'e veya kurulum ZIP'ine eklenmez. `.env`, `.env.*`, özel anahtar dosyaları, yerel ayarlar, proje verileri ve build çıktıları `.gitignore` kapsamındadır. `.gitignore` daha önce commit edilmiş bir sırrı geçmişten silmez.

Public olmak yazma yetkisi vermez. Herkes kodu okuyabilir, kendi fork'unda commit oluşturabilir ve pull request önerebilir. Asıl depoya push/merge için sahibin verdiği yazma yetkisi gerekir; yetkilendirilmiş uygulamalar da kendi izinleri kapsamında işlem yapabilir. [GitHub kişisel depo yetkileri](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository)

Depo sahibi **Settings → Code security** bölümünden **Secret scanning** ve **Push protection** açabilir. Korumalı dallar/PR inceleme zorunluluğu ayrıca **Settings → Rules** üzerinden tanımlanır; public depo kendiliğinden PR onayı zorunluluğu getirmez. [GitHub güvenlik ayarları](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-security-and-analysis-settings-for-your-repository)

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
8. `feature/otomatize` kullanacaksanız önce proje yedeği alın. Otomatik sürümün gerçek arama–RIS–Zotero kabul testleri henüz tamamlanmadı; başarılı build bu zincirin canlı doğrulandığı anlamına gelmez.

# Ayrıntılı kullanım ve geliştirme kılavuzu

Windows 11 ve Chrome için yerel uygulama, Chrome eklentisi ve kaynak kod. Sürüm 0.4.0, IEEE Xplore'u Scopus gibi okur, yayın türü + yıl penceresi önerir ve IEEE CSV'sini otomatik RIS'e çevirir ([IEEE akışı](#ieee-xploreda-her-arama-040)). Sürüm 0.3.2, konu sorgularına eşik sorgusunun yıl penceresini uygular ([daraltma akışı](#onaylı-scopus-daraltma-akışı)). Sürüm 0.3.1, 0.3.0 üzerine elle tarama + Zotero şablonları + teslim kontrolü ekler ([elle çalışma akışı](#elle-çalışma-akışı-031--arama-zotero-ve-teslim)). Sürüm 0.3.0 bir kabul testi sürümüdür. Scopus otomatik tarama, RIS indirme ve Zotero aday havuzu aktarımı eklenmiştir. Yeni arama/dışa aktarım/yazma zinciri canlı doğrulama bekler; yalnız otomatik testlerin geçmesi saha kabulü sayılmaz. IEEE ve ACM otomatik taraması sonraki aşamadır.

**Sürümler:** 0.2.1 manuel kayıt sürümüdür; 0.3.0 sorgu düzenleyicisi ve otomatik taramayı içerir. İkisinde de manuel Ctrl+M ve onaylı yıl daraltma vardır. Otomatik taramanın canlı kabulü henüz tamamlanmadı. Güncellemeden önce proje yedeği alın; Git dalı değiştirmek kurulu uygulamayı değiştirmez.

## En kısa yol

- **Sadece kullanacağım:** [Hazır manuel sürümü indir](https://github.com/HasanBasriTaskin/Tez_Otomatize/releases/tag/v0.2.1) → ZIP'in tamamını çıkar → **Kurulum.exe** → proje klasörünü seç → **Kur ve başlat**. Sonra [Chrome eklentisini bir kez yükle](#kurulum). Python, Node.js veya Git gerekmez.
- **Yeni geliştirme sürümünü kullanacağım:** [0.3.0 ön sürümünü](https://github.com/HasanBasriTaskin/Tez_Otomatize/releases/tag/v0.3.0) indir; aynı kurulum adımlarını uygula.
- **Kendi bilgisayarımda build alacağım:** Python 3.12 x64 ve Node.js 24 kuruluysa depo kökündeki **[build.bat](../build.bat)** dosyasına çift tıkla. Hem Windows programları hem Chrome eklentisi hazırlanır. Sonuç **artifacts/release** içindedir. PowerShell'den tek komut: `./build.bat`.

Build işlemi bağımlılıkları kurar, testleri çalıştırır, eski build çıktısını temizler ve kurulum ZIP'ini doğrular. Bir adım başarısızsa durur. Uygulamayı bilgisayarınıza kurmak için oluşan **Kurulum.exe** kullanılır. Günlük açılışta build yapmayın; Başlat menüsünden **Literatür Kayıt Asistanı** yeterlidir.

## ÖNEMLİ — Arama kelimeleri ve başka araştırmalara uyarlama

**Sorguları değiştirmek için yeniden build gerekmez.** Sorgu düzenleyicisi 0.3.0 ile eklenmiştir. Yeni sorgu düzenleyicisini içeren sürümü bir kez kurduktan sonra arama kelimeleri arayüzden veya proje dosyasından değiştirilebilir. Mevcut 0.2.1 kurulumuna kendiliğinden eklenmez.

**Manuel kullanım:** aramayı Scopus'ta kendiniz yazarsınız. Ctrl+M o anki aramayı kaydeder ve yıl daraltmasını kontrol eder. Öneriyi onaylarsanız daraltılmış sonuçta tekrar Ctrl+M yaparsınız. Sonraki konuya otomatik geçmez; sizin sonraki sorgunuzu ve Ctrl+M'nizi bekler. Hazır sorgu paketi manuel kullanımı sınırlamaz.

**Otomatik kullanım:** **Otomatik tarama → Sorgu paketi → Sorguları düzenle** bölümünde paket adını, başlangıç sorgusunu ve konu terimlerini değiştirin. Konu ekleyip çıkarabilir, 1–20 konu kullanabilirsiniz. **Sorgu paketini kaydet** düğmesi değişiklikleri proje klasöründeki `03_Calisma/sorgu-paketi.json` dosyasına yazar. Eski dosya `Yedekler` altında korunur. **Sorgu paketini göster** ile kaydedilen metinleri kontrol edip **Taramayı başlat** seçin. Bu akış ara Ctrl+M veya yıl onayı beklemez. Kaydedilmemiş düzenlemelerle yeni tarama başlatılmaz.

**Dosyadan düzenleme:** aynı JSON dosyasını UTF-8 olarak düzenleyip arayüzde **Değişiklikleri bırak ve dosyadan yükle** seçin. Bu düğme kaydedilmemiş form değişikliklerini bırakır. `.txt` sorgu belgesi otomatik okunmaz. Dosya yoksa OEC-1017 başlangıç ve altı konu paketi oluşturulur; bozuk dosyada eski varsayılanlarla sessizce tarama yapılmaz. JSON içe aktarma için dosyayı kendi projenizin aynı konumuna koymanız yeterlidir; başka bir kişinin SQLite/Excel dosyasını kopyalamayın.

### Sorgu paketi JSON örneği

Dosya, seçilen proje kökünün `03_Calisma/sorgu-paketi.json` konumundadır. **Otomatik tarama** bölümü ilk açıldığında dosya yoksa varsayılan paket oluşturulur; build çıktılarının içine yazılmaz. Arayüz aynı ekranda tam dosya yolunu gösterir.

Aşağıdaki tek konulu örnek dosya biçimini gösterir; araştırma kapsamının yeterliliğini göstermez:

```json
{
  "schema": 1,
  "name": "RAG örnek taraması",
  "initial": "TITLE-ABS-KEY(\"retrieval augmented generation\")",
  "topics": [
    {
      "code": "Q01",
      "label": "Türkçe çalışmalar",
      "query": "\"retrieval augmented generation\" AND Turkish"
    }
  ]
}
```

Kurulumdan sonra **Eklenti → Kayıtlar ve ayarlar → Otomatik tarama → Sorgu paketi → Sorguları düzenle** ile düzenleyin ve **Sorgu paketini kaydet** seçin. Dosyayı elle değiştirdiyseniz önce kendi kopyasını alın, UTF-8 olarak kaydedin ve **Değişiklikleri bırak ve dosyadan yükle** kullanın. Formdaki kaydedilmemiş değişiklikler bırakılır. Son kontrol için **Sorgu paketini göster** seçin. Yeniden build veya eklenti yükleme gerekmez.

JSON alanları: `schema: 1`, `name` (paket adı), `initial` (tam `TITLE-ABS-KEY(...)` sorgusu), `topics` (sıralı konu listesi). Her konuda `code` (Q01 gibi benzersiz kimlik), `label` (konu adı), `query` (yalnız kavram blokları) bulunur. Konu sorgularına `TITLE-ABS-KEY(...)`, yıl ve yayın türü koşullarını uygulama ekler; bunları konu metnine tekrar yazmayın. Başlangıca da yıl/tür filtresi eklemeyin. Dosya en fazla 128 KB olabilir. Parantez/tırnak ve temel biçim kontrolü yapılır; Scopus'un bütün sorgu dilini doğrulayan bir editör değildir.

Başlamış tarama kendi paket kopyasını saklar. Formdan paket değiştirmek için mevcut taramayı tamamlayın veya **Durdur** seçin. Dosya dışarıdan değiştirilse bile **Devam et** eski oturumun sorgularını kullanır; yeni paket yeni taramada uygulanır. Dosya önizlemeden sonra değişirse uygulama yeniden yüklemenizi ister. Yıl kararları aşağıdaki rehber kurallarıyla devam eder.

Hazır paket, terimlerin bilimsel olarak yeterli olduğunun garantisi değildir. Rehbere göre 3–5 tohum makalenin yazar/dizin terimlerini kontrol edin; ilgili çalışmalar kaçıyorsa eş anlamlıları veya konu bloklarını, çok ilgisiz sonuç geliyorsa kapsamı gerekçesiyle güncelleyin. Bu değişiklikleri yeni aramalar olarak kaydedin. Tohum makale/terim doğrulaması henüz tamamlandı olarak işaretlenmemiştir. Otomasyon kendi başına yeni kelime üretmez veya makale uygunluğuna karar vermez.

Yıl kuralları sabittir: ilk sonuç ≤300 ise yıl sınırı yok; 301–1000 ise 2022–2026; ilk sonuç >1000 ise önce 2022–2026, bunun sonucu da >500 ise 2024–2026. Takvim ilerleyince yıllar kendiliğinden değişmez. Her konu ayrıca 300'ün altına düşene kadar daraltılmaz; konular ortak yıl aralığını kullanır.

**Başka bir kişiye dağıtırken:** herkes kendi sorgusunu yazabilir ve kendi proje klasörünü kullanır. Yeni otomasyon genel amaçlı bir araştırma robotu değildir. Otomatik Zotero yazma hedefi mevcut TEZ grubuna ve koleksiyonlarına sabittir (`literature/zotero_writer.py`); sorgu JSON dosyasını değiştirerek başka gruba geçmez. Aynı grubu kullanacak kişinin erişimi olmalı; farklı grup/kütüphane desteği ayrıca geliştirilip test edilmelidir. Otomasyonun canlı kabulü tamamlanmış değildir.

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
2. Kendinize ait bir proje klasörü seçin; örneğin `Belgeler\Tez_Arkadas`. **Kaydı yapan kişi**, **Zotero kütüphanesi** ve **Zotero veri klasörü** alanlarını kontrol edin (veri klasörü: Zotero → Settings → Advanced → Files and Folders → Data Directory Location; çoğunlukla `%USERPROFILE%\Zotero`): takım varsayılanı (Hasan Basri Taşkın, `groups/6718452`) dolu gelir; başka biri kuruyorsa kendi adını, kendi kütüphanesi farklıysa onu yazar (`users/0` kişisel kütüphanedir). Sonra **Kur ve başlat** düğmesine basın. Yönetici izni gerekmez. Windows başlangıcında çalıştırma isteğe bağlıdır.
3. Kurucu uygulamayı ve eklentiyi `%LOCALAPPDATA%\LiteraturKayit` klasörüne kopyalar. Chrome’da `chrome://extensions` adresini açın. **Geliştirici modu → Paketlenmemiş öğe yükle** ile `%LOCALAPPDATA%\LiteraturKayit\extension` klasörünü seçin; kurucu bu yolu panoya kopyalar. Build klasöründeki kopyayı seçmeyin; sonraki build onu siler.
4. Eklenti kimliği `bdboonffghjgpgnkbhekphddmncanlld` olmalı. Eklentiyi Chrome araç çubuğuna sabitleyin.
5. Eklentide **Kayıtlar ve ayarlar** bölümünü açın. Proje adı, takım kodu ve kaydı yapan kişiyi kontrol edin. Başlangıçta arama listesi boştur.
6. Araştırma sitesinde bir sonuç sayfası açın. Eklenti simgesinden **Bu sitede etkinleştir** seçin. Proxy kullanılıyorsa izin, gerçekten açık olan proxy adresi için verilir.
7. Sonuç sayfasına dönüp Ctrl+M yapın. İlk PNG’de Windows saati, tarih ve adres çubuğunun göründüğünü kontrol edin. Ayarlar’daki saat/tarih kontrolünü bundan sonra işaretleyin.

**Güncelleme (her yeni sürümde):** `git pull` → `build.bat` → tepsideki uygulamadan **Çıkış** → Chrome'da eklentiyi kapatın (ya da Chrome'u kapatın) → yeni `Kurulum.exe` (pencere başlığında yeni sürüm görünmeli) → **Kur ve başlat** → Chrome'da eklentinin **↻** düğmesi. Eklentiyi kaldırıp yeniden yüklemek gerekmez; site izinleri korunur. Yalnız ↻ yapmak, kurucu çalışmadıysa eski dosyaları yeniden yükler. Kişi, Zotero kütüphanesi ve koleksiyon rolleri kurulum klasöründe hatırlanır; proje veritabanı yeniden oluşsa da yeniden girilmez. Daha önce oluşmuş bir projede hiç değiştirilmemiş ayarlar (Windows kullanıcı adı, `users/0`, boş roller) açılışta bu varsayılanlarla doldurulur; girdiğiniz değerlere dokunulmaz. Takım kütüphanesi `groups/6718452` seçilirse koleksiyon rolleri de hazır gelir.

Günlük kullanım terminal gerektirmez. Başlat menüsündeki **Literatür Kayıt Asistanı** tepsi uygulamasını açar. Chrome bağlantısı da kapalı uygulamayı başlatabilir. Tepsi menüsünden duraklatma, son PNG ve proje klasörü erişilebilir. Chrome açılışında pencereyi Windows ile eşleştiren kısa süreli arka plan sekmesi oluşabilir; yakalama sırasında yeni sekme açılmaz.

**Proje klasörünü değiştirmek (ör. deneme için):** Ayarlar → Proje klasörü → tam yolu yapıştırın → **Bu klasöre geç**. Ctrl+M kayıtları, Excel ve ekranlar bundan sonra o klasöre yazılır; eski proje olduğu gibi kalır. Geri dönmek için eski yolu yazın. Ctrl+M'den önce ekrandaki yolu kontrol edin.

Ana proje klasörünü seçtikten sonra uygulama `02_Ekranlar`, `03_Calisma/Veri/gecici`, `05_Teslim` ve `Yedekler` klasörlerini otomatik oluşturur. Excel `03_Calisma` altında ilk kayıtta üretilir; boş çalışma kitabı için **Excel’i güncelle** kullanılabilir. Başkasının Excel şablonunu veya SQLite veritabanını kopyalamak gerekmez.

## Otomatik Scopus taraması

1. Scopus sekmesinde kurumsal erişimin yanında kişisel Scopus oturumunu da açın; Export oturum istiyorsa indirme ilerlemez. Eklentinin site izni açık olmalı.
2. Yönetim ekranında **Otomatik tarama** bölümünü açın. Proje klasörünü, TEZ grubunu ve sorgu paketini kontrol edin. Konu türleri Article + Conference Paper; Review isteğe bağlıdır.
3. **İndirme iznini ver** düğmesini kullanın. **Zotero yazma iznini ver** ile Zotero’nun kendi penceresindeki isteği yanıtlayın. Kalıcı izin verilmezse sonraki çalıştırmada izin yeniden gerekebilir. Anahtar yedeğe girmez.
4. Scopus sekmesini seçip **Taramayı başlat** seçin. Scopus öne gelir. Başlangıç, gerekli yıl daraltmaları ve paketteki konular sıralı çalışır. Konulardaki bütün sonuç künyeleri hedeflenir; başlangıç/yıl denemeleri dışa aktarılmaz.
5. Başka sekmeye veya uygulamaya geçmek taramayı duraklatır. Durumu yönetim ekranında inceleyip hedef sekmeyi seçerek **Devam et** kullanın. **Durdur** mevcut oturumu kapatır; kaydedilen dosyalar korunur.

Her konu için gerçek PNG → Excel → RIS doğrulama → Zotero sırası korunur. Dosya sayısı beklenen sonuçla eşleşmezse sonraki konuya geçilmez. RIS destek sınırına göre 20.000’lik aralıklar kullanılır; sayfanın aralık kontrolü doğrulanamazsa işlem durur. Sayfa için 120 saniye, indirme için 15 dakika beklenir. İndirme kimliği, kaynak/referrer ve dosya adı belirsizse ilgisiz dosya alınmaz.

TEZ içindeki `01_Aday` ve `00_AramaKayitlari / Tarama … / S…` koleksiyonlarına metadata yazılır. Aynı Scopus EID yeni makale oluşturmaz; arama ilişkisi eklenir. DOI/başlık benzerliği kontrol adayıdır. Ham RIS, Zotero aktarımı ve benzersiz Scopus kaynak sayıları ayrı raporlanır. PDF indirme, bilimsel eleme ve insan okuması bu sürümün işi değildir; yapay zekâ API anahtarı gerekmez.

Uygulama kapanırsa oturum **Durakladı** olarak açılır. Sonucu belirsiz bir sorgu/indirme körlemesine yeniden gönderilmez; kontrol gerekir. Saat değişikliği algılanırsa kanıtlar korunarak durulur. Windows saati değiştirilmez; süre insan okuma süresi olarak kaydedilmez.

## Bir aramayı elle kaydetme

Aramayı çalıştırın ve yüklenmenin bitmesini bekleyin. Sorgu, sonuç sayısı, Windows görev çubuğu ve adres çubuğu görünürken Ctrl+M’ye basın. Windows monitörün tamamını yakalar; ardından eklenti o penceredeki aktif sekmeyi okur. Bu sırada sekme değiştirmeyin.

Başarılı kayıt `S001` gibi bir kimlik alır. Görseller `02_Ekranlar/S001/` altında `S001_YYYYMMDD_a_sonuc.png` biçiminde tutulur. Tarih gerçek çekim anının İstanbul tarihidir. Aynı aramaya ek çekimler `_v02` gibi sürümlenir. Sorgu/filtre değişikliği veya farklı gün yeni çalıştırma oluşturur. Aynı sorguyu bilerek yeniden çalıştırırken **Sonraki yakalamayı yeni arama say** kullanılabilir.

Eşleşme belirsizse PNG korunur; **Eksik kayıtlar → Kontrol et** bölümünde gerçek PNG’ye bakarak alanları tamamlayın. Yakalama yanlış sayfada alındıysa (ör. sonuç yerine gelişmiş arama formu) **Yanlış kayıt — atla** düğmesine iki kez basın: arama kaydı oluşmaz, kayıt listeden ve teslim kontrolünden çıkar, PNG ve denetim kaydı saklanır. İçe aktarılan PNG’nin çekim zamanı bilinmiyorsa bilinmiyor olarak kalır. Sayfa çalıştırılmış sorguyu göstermiyorsa makale başlığından sorgu veya sonuç sayısı üretilmez.

## Onaylı Scopus daraltma akışı

Ctrl+M önce mevcut PNG ve arama kaydını saklar. Sonuç kesin olarak okunmuşsa rehberdeki sabit kuralları kontrol eder:

| İlk yıl sınırsız sonuç | Öneri |
|---|---|
| 0–300 | Yıl sınırı önerilmez |
| 301–1000 | 2022–2026 |
| 1000 üstü | Önce 2022–2026; bunun sonucu da 500 üstüyse 2024–2026 |

Bu tablo yalnız **eşik sorgusuna** (projedeki ilk daraltma zincirine) uygulanır; kılavuzun Tablo 4'ü pencereyi ilk sorguya göre bir kez belirler. **0.3.2'den itibaren** zincir yakalandıktan sonra (ör. S001 → S002 → S003, 2024–2026) yılsız her yeni Scopus sorgusuna, sonuç sayısı ne olursa olsun, doğrudan bu pencere önerilir. Konu sorgusu böylece iki çekimle biter: yılsız ve pencereli. RIS dışa aktarımı pencereli çekimden yapılır. Sıfır sonuçlu sorguya öneri yapılmaz. Önerilip yakalanmamış bir adım pencereyi belirlemez.

**Aramayı daraltalım mı?** penceresinde tam yeni sorgu ve gerekçe görünür. **Uygula ve ara** seçilince aynı Scopus sekmesindeki yıl alanları kontrol edilip doldurulur ve yıl aralığı uygulanır. Sonuçların yüklenmesini bekleyip yeniden **Ctrl+M** yapın. Yeni arama, önceki arama kimliğine ve daraltma gerekçesine bağlanır; önceki PNG korunur. İkinci yıl önerisi gerekiyorsa bu yeni çekimden sonra çıkar. Excel'in 11 sütunu korunur; bağlantı gerekçesi Açıklama alanına yazılır.

**Şimdi değil** sayfayı değiştirmez. Öneri kayıt ayrıntısındaki **Daraltma önerisi** düğmesinden yeniden açılabilir. Scopus yıl kutusunu sonuçlardaki yıllara göre kendisi değiştirirse (ör. sonuçlarda 2022 yayını yoksa 2022 yerine 2023 yazar), program aramayı çalıştırmaz ve tam sorguyu panoya kopyalar. Otomatik uygulama sayfayı kesin tanıyamazsa **Sorguyu kopyala, elle uygula** ile aynı Scopus sekmesinde gelişmiş aramaya yapıştırıp çalıştırın, sonra Ctrl+M yapın. Yaklaşık/bilinmeyen sayılardan veya açıklanmamış mevcut yıl koşullarından yeni daraltma zinciri tahmin edilmez. Sorgu/sonuç değişmişse yeniden yakalama gerekir.

Yıllar takvim ilerledikçe kendiliğinden değişmez. Bu bölüm manuel Ctrl+M akışıdır; otomatik taramada hazır konu paketi ve aynı yıl kuralları ara onay olmadan uygulanır.

## IEEE Xplore'da her arama (0.4.0)

Kabul testi sürümüdür: okuyucu 16.10.2026'da kaydedilen gerçek IEEE sayfalarıyla test edildi; canlı sayfada doğrulama kullanıcı testindedir.

1. IEEE'de **Advanced Search → Command Search**'e sorguyu yazıp çalıştırın (yıl ve yayın türü eklemeyin).
2. Sonuç sayfası yüklenince **Ctrl+M**. Program sorguyu, sonuç sayısını, aranan alanı (ör. `Abstract`), yayın türü filtrelerini ve IEEE'nin gösterdiği yıl aralığını okur.
3. **Aramayı daraltalım mı?** penceresi açılırsa uygulanacak filtreler yazar:
   - Yayın türü her zaman yalnız **Conferences + Journals** (Scopus'taki makale/bildiri/derleme karşılığı). Early Access, Magazines, Books vb. çıkarılır.
   - Yıl: proje yıl penceresi (Scopus eşik zinciri, ör. S002 → S003 = 2024–2026) ya da Ayarlar'daki **Yıl penceresi başlangıcı**. Pencere yoksa Tablo 4 IEEE sonuç sayısına uygulanır (>300 → 2022–2026; ilk >1000 ve 2022–2026 >500 → 2024–2026). IEEE'nin kendi yıl aralığı zaten pencerenin içindeyse yıl filtresi eklenmez.
4. **Uygula ve ara**: aynı sekme bu filtrelerle yeniden yüklenir (sorgu değişmez). Sonuçlar gelince yeniden **Ctrl+M**; yeni kayıt önceki kayda bağlanır, Açıklama'ya “S0xx devamı: IEEE filtreleri uygulandı (…)” yazılır.
   Otomatik yükleme filtreleri göstermezse **Filtreleri elle uygula**: sol panelde Content Type → Conferences + Journals → Apply; Year kutularına yılları yazıp Apply; sonra Ctrl+M.
5. Filtreli sayfada **Export → Search Results → CSV** (hiçbir kaydı seçmeden). İnen dosyayı **adını değiştirmeden** proje klasöründeki `01_HamExport` içine koyun. Birkaç saniye içinde program:
   - sonuç sayısı CSV satır sayısına eşit olan IEEE kaydını bulur (daraltılıp yerine yenisi alınmış kayıt aday sayılmaz),
   - CSV'yi `S0xx_IEEE.csv` yapar, yanına `S0xx_IEEE.ris` yazar (IEEE'nin kendi RIS etiketleriyle; var olan dosyanın üzerine yazmaz, `_2` ekler),
   - dosya adlarını kaydın **Export dosya adları** alanına ve Excel'e yazar, bildirim gösterir.
   Birden çok kayıt uyuyorsa ya da hiçbiri uymuyorsa (ör. 2.000 üstü sonuç) **Arama kayıtları → IEEE CSV → RIS** panelinden aramayı seçip **Bu aramaya bağla** deyin. Dosyayı kendiniz `S0xx_IEEE.csv` diye adlandırırsanız doğrudan o kayda bağlanır. IEEE olmayan CSV'lere dokunulmaz.
6. RIS'i Zotero'da `00_AramaKayitlari/S0xx` koleksiyonuna aktarın; sayı Zotero'dan okunur.

IEEE'nin **Citations → RIS** dışa aktarımı yalnız o sayfada seçilen kayıtları verir (sayfalar arası seçim birikmez); bu yüzden toplu yol CSV'dir.

### Dışa aktarılan kayıt sayısı (0.4.1)

Excel'deki **Dışa aktarılan kayıt sayısı**, **Aktarım sayısının kaynağı** ve **Export dosyaları** sütunları kendiliğinden dolar (öncelik sırasıyla):

1. Kayıt penceresine elle yazılan sayı.
2. `01_HamExport` içindeki `S0xx_….ris` dosyalarının kayıt sayısı (birden çok parça toplanır; ör. `S005_Scopus.ris`, `S020_IEEE.ris`). Ekrandaki sonuç sayısıyla uyuşmazsa ya da dosya adı başka platformu gösteriyorsa (ör. Scopus kaydına `_IEEE.ris`) kaynak sütununda uyarı çıkar.
3. Zotero'daki `S0xx` koleksiyonunun sayısı.
4. `01_HamExport\_aktarilmayacak` içindeki `S0xx_….ris` → 0 (“Aktarılmadı”).
5. Yıl/filtre daraltmasıyla yerine yeni kayıt alınan arama (ör. S004 → S005) → 0.

Dosyalar yalnız okunur; taşınmaz, yeniden adlandırılmaz. Bir dosyayı `_aktarilmayacak`'a taşırsanız birkaç saniye içinde sayı güncellenir.

## ACM Digital Library'de her arama (0.5.0)

RTEÜ'nün ACM aboneliği yok; ACM'nin ücretsiz (Basic) sürümünde toplu “Export Citations”, çoklu seçimle dışa aktarma ve tür filtresi yoktur, sayfa başına en fazla 50 sonuç gösterilir. Program bu yüzden kayıtları aramanın kendi sonuç sayfalarından toplar. Okuyucu 16.10.2026'da kaydedilen gerçek ACM sayfalarıyla test edildi; canlı doğrulama kullanıcı testindedir.

1. dl.acm.org'da aramayı tarih filtresiyle çalıştırın. ACM sorgu satırında `AND [E-Publication Date: (01/01/2024 TO 12/31/2026)]` görünmeli.
2. Sonuç sayfası yüklenince **Ctrl+M**. Program ACM'nin **“Results for:”** satırındaki sorguyu (tarih dahil), sonuç sayısını ve aranan alanı (`Abstract`) okur. Excel'in Filtre sütununa `Yıl: 2024–2026` ve `Tür: research-article, short-paper` yazılır.
3. **ACM kayıtlarını toplayalım mı?** penceresinde **Topla**. Program sonuç sayfalarını 50'şer kayıtla, sayfalar arasında 1,5 sn bekleyerek sırayla okur (makale sayfası açmaz, PDF indirmez). Her sayfada sorgu ve toplam kayıttakiyle aynı olmalı; değilse hiçbir şey yazılmaz. Arama sekmesi açık kalsın.
4. Yalnız kılavuz K2'nin saydığı türler alınır: **research-article** ve **short-paper**. Poster, extended-abstract, abstract, demonstration vb. alınmaz.
5. Liste okununca alınan her kaydın ACM makale sayfası (kayıt başına ~1,2 sn ara ile) okunur: **özet** ve **erişim** (Açık (ACM PDF) / Ücretli). Crossref'te ACM bildirilerinin özeti yoktur. Üst üste 3 makale sayfası alınamazsa özet okuma durur, liste yine kaydedilir. İlerleme pencerede görünür; pencere kapatılabilir.
6. Künyeler DOI'den Crossref'ten tamamlanır (Crossref'te olmayanlar, ör. `10.5555/…`, ACM listesindeki bilgiyle). Sonra:
   - `01_HamExport\S0xx_ACM_liste.csv`: okunan her kayıt, Alındı/Alınmadı kararı, nedeni, künye ve özet kaynağı, erişim.
   - `01_HamExport\S0xx_ACM.ris`: alınan kayıtlar. Excel'deki **Dışa aktarılan kayıt sayısı** bu dosyadan dolar.
   - Zotero'da `00_AramaKayitlari › S0xx_ACM` (ve `01_Aday`). Zotero açık ve yazma izni verilmiş olmalı (**Otomatik tarama → Zotero bağlantısını kontrol et**).
7. Bitince bildirim gelir (ör. “S032: 33 kayıt okundu, 21 kayıt alındı…”). Pencere kapandıysa **Arama kayıtları → kayıt → ACM kayıtları** ile yeniden açılır. Hata olursa **Yeniden topla**; aynı arama için Zotero'da ikinci kopya oluşmaz.

Ücretli (ör. `10.5555/…`, ACM dışı yayıncı) kayıtlar aramada elenmez; tam metne hiçbir yoldan ulaşılamazsa tam metin aşamasında H3 ile hariç tutulur. Scopus/IEEE'de de bulunan makaleler ACM koleksiyonuna ayrıca eklenir; en sonda Zotero'nun **Duplicate Items** görünümünde birleştirilir (kılavuz Adım 6 m.4). Tek seferde en fazla 2.000 kayıt toplanır.

## İndirilenler klasörü takibi (0.6.0)

**Ayarlar → İndirilenler klasörünü takip et** açıkken Scopus ve IEEE dışa aktarımlarını elle taşımanız gerekmez:

1. Aramada Ctrl+M yapın (kayıt oluşsun).
2. Scopus'ta **Export → RIS** ya da IEEE'de **Export → Search Results → CSV** ile indirin; dosya adını değiştirmeyin.
3. Birkaç saniye içinde program dosyayı tanır, kayıt sayısı ekrandaki sonuçla aynı olan ve henüz dosyası olmayan aramayı bulur ve `01_HamExport\S0xx_Scopus.ris` / `S0xx_IEEE.csv` olarak taşır. IEEE CSV'si RIS'e çevrilir; Excel ve bildirim güncellenir.
4. Eşleşme kesin değilse dosya İndirilenler'de kalır; **Arama kayıtları → İndirilenler** bölümünden aramayı seçip **Bu aramaya taşı** deyin.

Takip açıldığında son 24 saatte inen dosyalara da bakılır. Yarım indirmelere, 01_HamExport'ta aynısı bulunan dosyalara ve RIS/CSV dışındaki dosyalara dokunulmaz.

## Scopus ve IEEE RIS'lerini Zotero'ya aktarma (0.7.0)

**Zotero ve notlar → Scopus ve IEEE RIS → Zotero → RIS'leri Zotero'ya aktar.** Zotero açık ve yazma izni verilmiş olmalı (Otomatik tarama → Zotero bağlantısını kontrol et).

- 01_HamExport'taki her Scopus/IEEE RIS'i (\_aktarilmayacak hariç) `00_AramaKayitlari › S0xx_Scopus` / `S0xx_IEEE` koleksiyonuna ve `01_Aday`'a yazılır.
- Aynı makale (DOI, yoksa başlık) **tek öğe** olarak oluşturulur ve bulunduğu bütün aramaların koleksiyonlarına konur; ACM'den gelmiş öğeler yeniden kullanılır. Duplicate Items'ta yalnız DOI'si/başlığı farklı yazılmış az sayıda kopya kalabilir.
- Arama başına sayılar bölümde görünür. Yarıda kalırsa düğmeye yeniden basın; kaldığı yerden devam eder.

## Başlık-özet elemesini Zotero'ya işleme (0.8.0)

Kararlar programın dışında hazırlanır ve proje klasöründe `03_Calisma\Eleme\eleme_kararlari.json` dosyasında durur
(her 01_Aday kaydı için bir satır: Hariç + H kodu + kanıt alıntısı, ya da Geçti + Seçildi/Yedek). Biçim:
[ELEME_AKTARIM.md](ELEME_AKTARIM.md).

1. Zotero bölümünde **Zotero'dan oku** (01_Aday güncel olmalı).
2. **Başlık-özet eleme → Denetle.** Sayılar ve varsa sorunlar listelenir (01_Aday'da olmayan ya da başlığı değişmiş
   kayıt, geçersiz kod, başlıkta geçmeyen kanıt…). Sorun varken onay ve uygulama pasif kalır.
3. **Eleme Excel'ini üret** ile `Eleme_Calisma.xlsx`'i açıp kararları kontrol edin.
4. **"Kararları kontrol ettim; onaylıyorum"** kutusu → **Kararları onayla.** Onaylayan, Ayarlar'daki "Kaydı yapan kişi";
   tarih bugünün tarihi. Onay, kararların o anki içeriğine bağlıdır: dosya sonradan değişirse onay düşer. Önceki dosya
   `Yedekler` klasörüne kopyalanır.
5. **Zotero'ya uygula.** Zotero açık ve yazma izni verilmiş olmalı. Yazılanlar:
   - hariç: `05_Haric_BaslikOzet` + H kodu etiketi + hariç notu (Karar, Aşama: Başlık-özet, Gerekçe kodu, Açıklama ve
     kanıt, Karar veren, Karar tarihi);
   - geçen: `02_BaslikOzet_Gecen` + `TamMetin-Secildi` ya da `TamMetin-Yedek` etiketi;
   - erişimi "Kontrol edilecek" olan seçilmiş kayıtlar ayrıca `06_Erisim_Kontrol` (yoksa oluşturulur).

   Kayıtlar 01_Aday'da kalır; hiçbir öğe, koleksiyon, etiket ya da not silinmez veya değiştirilmez. Yarıda kalırsa
   düğmeye yeniden basın; kaldığı yerden devam eder, ikinci not yazılmaz. Bitince Zotero kendiliğinden yeniden okunur.
6. **Çıktılar ve yedek → Teslim kontrolünü çalıştır**: PRISMA'da başlığı/özeti incelenen, başlıktan/özetten hariç
   (kodlarıyla), geçen, seçilen ve yedek kutuları görünür. **PRISMA şeması (PDF)** `05_Teslim\<takım>_O2_PRISMA.pdf`
   üretir; karar bekleyen kayıt varken başlığında TASLAK yazar.

Matris Excel'inin **Hariç** sayfası değişmez: kılavuza göre orada yalnız tam metinde hariç tutulanlar listelenir.

## Sitelerden bilgi nasıl okunur?

İlk sürüm görünür semantik etiketleri ve sonuç özetlerini okur. Site/proxy düzeni farklıysa otomatik tahmin tamamlanmış kayıt sayılmaz. Sorgu kutusundaki henüz çalıştırılmamış metin sonuçlarla eşleştirilmez. Sıfır, bilinmeyen, yaklaşık ve “en az” sayımları ayrıdır.

Gerekirse sonuç sayfasındaki **çalıştırılmış sorgu**, **toplam sonuç sayısı**, **uygulanan filtreler** ve **aranan alan** metnini ayrı ayrı seçip sağ tık menüsündeki **Literatür kaydı** alanlarına bağlayın. Bu seçim aynı site/adres yapısı için saklanır. Filtre seçimi, kullanılabilir bütün filtreleri değil uygulanmış filtre özetini göstermelidir. Sonraki Ctrl+M bu alanları okuyabilir. Site düzeni değişirse yeniden eşleştirin. Sorguyu doğrudan okuyamadığınızda manuel tamamlama kullanın.

Tanılama düğmesi seçili alanlardan sınırlı metin kaydeder; tüm HTML, çerez ve oturum bilgisi arşivlenmez. Mevcut semantik çıkarıcı dört platformun adını tanır; bu, her platformun canlı DOM’unun doğrulandığı anlamına gelmez. Gerçek sayfa üzerinden adapter iyileştirmeleri kabul testiyle yapılır.

## Excel ve klasörler

| Klasör | İçerik |
|---|---|
| `01_HamExport` | Doğrulanmış RIS dosyaları; arama kimliği ve kayıt aralığı |
| `02_Ekranlar` | Özgün PNG’ler ve her aramanın görsel dizini |
| `03_Calisma/Veri` | SQLite, geçici/eksik işler ve tanılama |
| `03_Calisma` | Üretilen Excel görünümü |
| `05_Teslim` | PDF, BibTeX ve kaynak manifesti |
| `Yedekler` | Tutarlı proje yedekleri ve Excel koruma kopyaları |
| `Uygulama` | Kaynak kod ve kurulum paketi |

SQLite asıl kayıttır. Düzenlemeleri eklentiden yapın; Excel’den geri içe alma yoktur. Arama_Kaydi/Matris/Hariç için incelenen referansın 11/28/6 sütun başlıkları kullanılır; eski satırlar aktarılmaz. Projedeki mevcut Excel uygulamanın ürettiği dosya değilse korunur ve yeni sürüm oluşturulur. Kullanıcının sonradan değiştirdiği veya kilitlediği dosya da ezilmez. Mesajdaki gerçek çıktı yolunu kullanın.

Arama_Kaydi’nde bir arama bir satırdır. **Ekran dosyası** bağlantısı bütün görsellerin bulunduğu göreli dizini açar. Proje klasörü birlikte taşındığında bağlantılar korunur. **Dışa aktarılan kayıt sayısı** otomatik taramada doğrulanmış RIS dosyalarındaki gerçek kayıtların toplamıdır; manuel kayıtta bilinmiyorsa boş kalır. Açıklama oturum/adım ve RIS yollarını içerir.

## Elle çalışma akışı (0.3.1) — arama, Zotero ve teslim

Bu akış CEN401 Literatür Kılavuzu Kısım I (Ö2) teslim paketini üretir. Ayarlar'da **Kaydı yapan kişi** alanını doldurun. **Yıl penceresi başlangıcı** boşsa onaylı yıl daraltmasından alınır.

### 1. Zotero'yu bir kez hazırlayın

Takım grubunda aynı düzeyde şu koleksiyonları açın:

| Koleksiyon | Ne konur? | Programdaki rol |
|---|---|---|
| `00_AramaKayitlari/S001`, `S002`… | Her aramanın RIS/BibTeX aktarımı. Ad S kodu ile başlamalı (`S004_Scopus` olur) | Rol yok. Program aktarım sayısını ve bulunma yolunu buradan okur |
| `01_Aday` | Aktarılan bütün kayıtlar | Aday |
| `02_BaslikOzet_Gecen` | Başlık-özet elemesini geçenler | Başlık-özet geçti |
| `03_TamMetin_Dahil` | Tam metni okunup dahil edilenler | Tam metin dahil |
| `04_Haric_TamMetin` | Tam metinde elenenler (Hariç sayfasına yazılır) | Tam metin hariç |
| `05_Haric_BaslikOzet` | Başlık-özet aşamasında elenenler (yalnız sayılır) | Başlık-özet hariç |

Kayıt bir aşamadan ötekine geçince eski aşama koleksiyonundan çıkarın (**Remove Item from Collection**). Çöpe atmayın. Aynı kaydın hem dahil hem hariç koleksiyonunda bulunması çelişki olarak raporlanır.

**Zotero ve notlar** ekranında:
1. **Koleksiyonları getir** ile koleksiyonları listeleyin.
2. Beş rolü eşleyip kaydedin.
3. **Zotero veri klasörü** alanına Zotero → Settings → Advanced → Files and Folders → *Data Directory Location* yolunu yazın. Boşsa `%USERPROFILE%\Zotero` kullanılır.

### 2. Her arama

1. Scopus'ta yılsız sorguyu çalıştırın. Sonuçlar, sorgu ve Windows saati görünürken **Ctrl+M** yapın.
2. Eşik sorgusunda daraltma önerilerini sırayla uygulayın (ör. S001 → S002 → S003); bu zincirden RIS alınmaz. Konu sorgusunda program doğrudan proje penceresini önerir (ör. S004 yılsız → S005 2024–2026). **Uygula ve ara** → sonuçlar yüklenince yeniden **Ctrl+M**. Öneri gelmeyen son çekim, dışa aktarılacak çekimdir.
3. Bu son sayfada Export → **RIS** (ACM'de BibTeX; Scopus'ta "Zotero (RIS)" değil düz RIS):
   - Aralık: **Documents 1 – toplam sonuç sayısı** ("All documents on this page" yalnız ekrandaki 10 kaydı alır).
   - Bilgiler: Citation information, Bibliographical information, **Abstract & keywords**, Other information → Conference information.
   - Dosyayı `01_HamExport` klasörüne son çekimin koduyla kaydedin: `S005_Scopus.ris`. Ad dosyadan Zotero koleksiyonuna geçer; program S kodunu oradan okur.
4. Zotero'da TEZ grubu seçiliyken **File → Import** ile aktarın. Oluşan `S005_Scopus` koleksiyonunu `00_AramaKayitlari` altına taşıyın, kayıtları ayrıca `01_Aday`'a sürükleyin.
5. Programda aramayı açın, **Export dosya adları** alanını doldurun.
   - Aktarılan sayıyı yazmanız gerekmez: **Zotero'dan oku** sonrası `S005` koleksiyonundaki kayıt sayısı Excel'e yazılır.
   - Dışa aktarılmayan bütün çekimlerde (eşik zinciri ve konuların yılsız çekimleri) **Elle aktarılan sayı** alanına `0` yazın; boş kalırsa teslim kontrolü uyarır.
   - Program çalışırken Excel dosyasını açık tutmayın; açıksa program `_v02.xlsx` adlı ayrı bir sürüm yazar.

### 3. Eleme ve okuma

- **Başlık-özet:** Not yazmayın. Kaydı `02_BaslikOzet_Gecen` veya `05_Haric_BaslikOzet` koleksiyonuna taşıyın. Kararlar bir karar dosyasında toplandıysa bunu program yapar: [Başlık-özet elemesini Zotero'ya işleme](#başlık-özet-elemesini-zoteroya-işleme-080).
- **Tam metin, hariç:**
  1. Eklenti simgesi → **Hariç şablonunu kopyala**.
  2. Zotero'da kayda sağ tık → **Add Note** → yapıştırın.
  3. Gerekçe kodunu (H1–H6), açıklamayı, karar vereni ve tarihi yazın.
  4. Kaydı `04_Haric_TamMetin` koleksiyonuna taşıyın.
- **Tam metin, dahil:**
  1. **Okuma şablonunu kopyala** ile şablonu nota yapıştırın.
  2. **Matris ID** verin (L001, L002…).
  3. Alanları PDF'ten kendi cümlelerinizle doldurun. **Temel bulgu**'ya sayı, koşul ve sayfa/tablo numarasını birlikte yazın.
  4. 2024 öncesi temel çalışmada **İstisna gerekçesi** zorunludur.

Şablon kuralları:
- Alan adlarını ve iki noktayı değiştirmeyin.
- Parantezli ipucu metni değiştirilmezse boş sayılır.
- Tanınmayan bir alan adı (ör. yazım hatası) içerik kaybolmadan teslim kontrolünde uyarı olarak görünür.

PDF'i yayıncının sayfasından **Zotero Connector** ile kayda ekleyebilirsiniz. **Find Available PDF** özelliğini tek tek veya küçük gruplar halinde kullanın; kılavuz toplu otomatik indirmeyi yasaklar.

### 4. Çıktılar

1. **Zotero'dan oku** → Excel kendiliğinden yenilenir: Arama_Kaydi, Matris, Hariç.
2. **Çıktılar ve yedek → Literatur_PDF arşivini oluştur:** Dahil kayıtların Zotero PDF'leri proje kökündeki `Literatur_PDF` klasörüne `L001_Yazar_Yil_KisaBaslik.pdf` adıyla **kopyalanır**. Nottaki **Yerel PDF** adı doluysa o kullanılır. Arşivdeki farklı içerikli dosyaların üzerine yazılmaz, matriste karşılığı olmayanlar silinmez; ikisi de raporlanır. Zotero vurguları özgün PDF'e yazılmaz; vurgulu kopya için Zotero'da *File → Export PDF* kullanın.
3. **Teslim kontrolünü çalıştır:** PRISMA sayıları, kılavuz sınırları ve eksik alanlar listelenir. Rapor salt okunurdur. Hata kalmayana kadar teslim etmeyin.
4. **Kaynak listesi ve BibTeX üret** ve **Ekran kanıtları PDF'si** önceki sürümdeki gibidir.

## Zotero ve teslim çıktıları

Önce temel arama akışını doğrulayın. Ardından Zotero’yu açın. Zotero **Settings → Advanced → Allow other applications on this computer to communicate with Zotero** ayarı yerel API erişimini açar. Yerel kişisel kütüphane `users/0` kullanır; okuma için API anahtarı gerekmez. Grup kütüphanesi `groups/ID` biçimindedir. [Zotero yerel API belgesi](https://www.zotero.org/support/dev/web_api/v3/local_api)

**Zotero ve notlar** bölümünde bağlantı ayarlarını kaydedin, koleksiyonları getirin ve Aday/Başlık-özet/Tam metin dahil/Hariç rollerini seçin. **Not şablonunu kopyala** ile her kaynağa bağlı bir Zotero notu oluşturun. Şablon alanlarını kaynak metne bakarak doldurun; bilgi yoksa “raporlanmadı” yazın. **Zotero’dan oku** sonrasında anotasyonu kontrol edip kaynak arama kimliklerini bağlayın. Aynı makaleye S001 ve S002 birlikte bağlanabilir. Çelişen koleksiyonlar/notlar ve DOI tekrar adayları gösterilir; DOI ile sessiz birleştirme yapılmaz.

**Zotero’dan oku** ve teslim çıktıları salt okunur çalışır; otomatik tarama ayrı, izinli Zotero 10 yerel yazma yolunu kullanır. Bu yazma yolu yalnız TEZ grubuna künye ve koleksiyon ilişkisi ekler. Kullanıcının okuma notlarını ve dahil/hariç kararlarını korur. Web API mevcut okuma özelliği içindir; otomatik taramada kullanılmaz. Kalıcı anahtar Windows Kimlik Bilgileri Yöneticisi’nde tutulur.

Başlangıçtaki Scopus sonuç sayısı Zotero’ya aktarım hedefi değildir. Otomatik tarama, ortak yıl kararı ve konu/tür filtreleri sonrasındaki paket sonuçlarının tamamını toplar. Aramalar arasında aynı kaynak tekrar bulunabildiği için ham toplam benzersiz aday sayısından büyük olabilir. Aday havuzuna eklenmek, bilimsel olarak dahil edilmiş veya okunmuş olmak anlamına gelmez.

**Çıktılar ve yedek** bölümünden:

- `OEC-1017_O2_KaynakListesi.pdf` ve `OEC-1017_O2_kaynaklar.bib` aynı dahil kaynak kümesinden üretilir. Kontrol edilmemiş anotasyon final çıktıyı engeller; açıkça TASLAK seçilebilir.
- `OEC-1017_O2_AramaEkranlari.pdf` özgün PNG’leri sayfalara yerleştirir. Açıklama görüntünün dışında tutulur.
- Matris/Hariç güncellemesi için **Excel’i güncelle** kullanılır.
- Eksik alanlar çıktı raporunda gösterilir. Gerçek teslim kartı ayrıca kontrol edilmelidir.

## Yedek ve geri yükleme

**Yedek al**, SQLite’ın tutarlı anlık kopyasını ve proje dosyalarını bir ZIP’e koyar. Gizli API anahtarı ve program kodu yedeğe girmez. **Yedeği geri yükle** dosya yollarını, SHA-256 özetlerini ve SQLite bütünlüğünü kontrol ederek yeni klasör oluşturur. Ardından Ayarlar’dan o klasöre geçebilirsiniz. Aynı SQLite dosyasını iki bilgisayarda eşzamanlı yazmayın.

SHA-256, dosyanın sonradan değişip değişmediğini denetler; aramanın doğruluğunu veya çekim tarihini tek başına kanıtlamaz. Orijinal PNG’ye sonradan saat, sorgu veya sonuç sayısı eklenmez.

0.3.0 ilk açılışta schema1 SQLite yedeğini `Yedekler/schema1_…sqlite3` altında alır ve schema2’ye geçer. Eski uygulama schema2’yi açmaz. Geri dönüş için güncelleme öncesi proje ZIP’ini yeni klasöre geri yükleyin; eski veritabanını yeni kayıtların üzerine kopyalamayın.

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

Chrome eklentisi esbuild, Windows programları PyInstaller ile derlenir. Build sırasında `artifacts/extension`, `artifacts/windows` ve `artifacts/work` ara klasörleri oluşur; paketleme bitince silinir. Tam build sonunda yalnız şu yapı kalır:

```text
artifacts/
  release/
    LiteraturKayit-0.3.2.zip          # Başkasına verilecek tam paket
    LiteraturKayit-0.3.2.zip.sha256
    LiteraturKayit-0.3.2/
      Kurulum.exe                     # Çalıştırılacak dosya (payload yanında kalmalı)
      extension/                      # Chrome'a yüklenecek eklenti klasörü
        manifest.json
      README.md
      MANUEL_TEST.md
      TEST_RAPORU.md
      payload/
        tray/LiteraturKayit.exe
        host/NativeHost.exe
        product.json
```

**Build temizliği:** `scripts/build-windows.py` her çalışmada önce `artifacts` klasörünün tamamını temizler, paketleme bitince ara klasörleri de siler; eski sürüm ZIP'leri dahil yalnız yeni paket kalır. `npm run build` sadece `artifacts/extension` klasörünü temizleyip yeniden üretir. Saklamak istediğiniz eski kurulum ZIP'ini yeni build'den önce bu klasörün dışına alın. `artifacts` içine elle kaynak, ayar veya tez verisi koymayın. Klasör başka konuma yönlenen bir bağlantıysa temizlik durur. EXE, geçici dosya ve spec yolları [PyInstaller'ın çıktı seçenekleriyle](https://pyinstaller.org/en/stable/usage.html#options) belirlenir.

`artifacts/`, eski `build/`, `dist/`, `release/`, `extension/dist/`, `.spec` ve derlenmiş Windows dosyaları `.gitignore` içindedir. GitHub Desktop'ta yalnız kaynak değişiklikleri görünür. `.tmp` test çalışma alanı ve `qa-output` örnek çıktıları da izlenmez. Kurulu uygulamanın `%LOCALAPPDATA%\\LiteraturKayit` klasörü ve proje kayıtları build temizliğine dahil değildir. Build almak uygulamayı güncellemez; kurulum için **artifacts/release** içindeki tam paket kullanılır.

`payload` içindeki diğer DLL/veri dosyaları da gereklidir; sadece tek EXE'yi kopyalamayın. Pakette üreticinin bilgisayarına ait proje yolu bulunmaz; kurulacak bilgisayarda klasör seçilir. Yalnız eklentiyi derlemek için `npm.cmd run build` yeterlidir; çıktı `artifacts/extension` olur. `product.json` sabit eklenti kimliğini ve açık anahtarı tutar; rastgele yeniden üretmeyin.

## CI nasıl çalışıyor?

[.github/workflows/windows.yml](../.github/workflows/windows.yml), `main` ve `feature/…` push'larında, main'e açılan PR'larda ve elle **Run workflow** tetiklenince çalışır. Windows 2022 runner Python 3.12 ve Node.js 24'ü kurar; ardından yereldekiyle aynı **build.bat --no-pause** akışını çalıştırır. ZIP içeriği, EXE başlıkları ve sürüm doğrulanır; SHA-256 oluşturulup artifact yüklenir. Test veya derleme hatasında yeni paket yüklenmez. Bilgisayarınıza otomatik kurulum yapılmaz. Dal push'ları Actions paketi üretir; `package.json`'daki sürümün etiketi henüz yoksa test/build sonrasında Releases yayını da kendiliğinden yapılır (etiketi yayın oluşturur). Ayrıntılar: [Sürüm yayımlama](YAYINLAMA.md).

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
8. Otomatik tarama sürümünü kullanacaksanız önce proje yedeği alın. Otomatik sürümün gerçek arama–RIS–Zotero kabul testleri henüz tamamlanmadı; başarılı build bu zincirin canlı doğrulandığı anlamına gelmez.

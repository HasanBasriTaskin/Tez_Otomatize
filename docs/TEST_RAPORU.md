# Doğrulama kapsamı — 0.3.0 geliştirme / 0.2.1 günlük kullanım

## Scopus Monaco sorgu editörü — 15 Ekim 2026

- Canlı denemede saat/tarih ve Zotero izinlerinden sonra başlangıç adımı `opening` durumunda `unsupported` hatasıyla durdu. Kullanıcının paylaştığı HTML, normal textarea yerine Monaco `native-edit-context` alanını ve salt okunur IME textarea'sını gösterdi.
- Bu yapı artık tanınıyor. Sorgu, editörün kendi seçme/kopyalama/yapıştırma olaylarıyla değiştirilip modelden geri okunuyor; Windows panosu değiştirilmiyor. Gecikmeli yapıştırma tek kez gönderiliyor ve tam sorgu doğrulanmadan Search tıklanmıyor.
- **74 eklenti testi**, TypeScript kontrolü ve eklenti build'i geçti. Yeni testler tanıma, tüm modeli değiştirme, gecikmeli yapıştırma, görünmeyen ek satırlar, salt okunur/çoklu editör ve yanıt vermeyen editörü kapsıyor.
- Ayrı geçici profilde gerçek Chrome headless ve **Monaco 0.57.0** ile çok satırlı/Türkçe sorgunun modele yazılması, doğru sorgunun gönderilmesi ve görünmeyen ek metnin gönderimi engellemesi doğrulandı. Ekran görüntüsü alınmadı; test bir Scopus oturumu kullanmadı.
- Bu düzeltme yalnız eklentidedir; EXE değişmedi. Eklenti ve Scopus sayfası yenilendikten sonra mevcut duraklatılmış oturumdan canlı kabul sürdürülecek. **Scopus → PNG → Excel → RIS → Zotero zinciri henüz tamamlanmış sayılmıyor.**

## Değiştirilebilir sorgu paketi — 15 Ekim 2026

- 98 Python ve 68 eklenti testi geçti; TypeScript ve eklenti build'i başarılı.
- Arayüzden sorgu kaydetme, konu ekleme/çıkarma, JSON dosyasından yükleme, dış değişiklikleri ezmeme, eski dosyayı yedekleme ve oturum sorgularını koruma sınandı. Bozuk JSON yeni taramayı engeller; kayıtlı oturuma devam etmeyi engellemez.
- Manuel Ctrl+M sorgu paketini ilerletmez. Kendi yazılan aramayı kaydeder, rehberin yıl önerisini kontrol eder ve yeni kullanıcı işlemini bekler. Otomatik çalışma ayrı başlatılır.
- Yeni sorgu düzenleyicisi için Windows/Chrome canlı kabulü ve Scopus → PNG → Excel → RIS → Zotero zinciri henüz tamamlanmadı. Otomatik test sonuçları bu kabulün yerine geçmez.
- İlk ayrı eklenti denemesi kullanıcı tercihiyle bırakıldı; geçici Native Messaging kaydı ve test sunucusu kaldırıldı. Sonraki deneme kullanıcının isteğiyle tek normal eklenti, feature/otomatize kodu ve ayrı test veri klasörüyle yapılacak.

## Tek eklentiye güncelleme — 15 Ekim 2026

- Kullanıcının açık isteğiyle ana depo `feature/otomatize` dalına geçirildi ve 0.3.0 mevcut normal kurulum konumuna kuruldu. İkinci test eklentisi kullanıcı tarafından kaldırıldı; geçici test host kaydı/sunucusu kapatıldı.
- Günlük projenin 13 araması kurulu uygulamanın ZIP yedek komutuyla yedeklendi; 0.2.1 program dosyaları ve ayarları `Test_Otomatize/Geri_Donus` altında korundu. Yeni kurulum hedefi `Test_Otomatize/Calisma`; günlük proje yeni sürüm tarafından açılmadı.
- Windows paketi ve ZIP bütünlük kontrolü geçti. Paketlenmiş tray/bridge hello, status, kısayol, pause, Excel, yedek ve bridge kapanış kontrolleri geçti.
- Kurulan dosyalar paket özetleriyle eşleşti. Gerçek kurulu EXE üzerinden sorgu paketini okuma/kaydetme ve boş `TEST_O2_LiteraturMatrisi.xlsx` üretimi doğrulandı. Başlangıç ve tek konu için küçük makale başlığı sorgusu hazırlandı.
- Chrome eklentisinin kullanıcı tarafından yeniden yüklenmesi bekleniyor. Canlı Scopus → PNG → RIS → Zotero zinciri henüz geçmedi; Zotero yazma ve Chrome indirme izinleri canlı denemede kullanıcı tarafından verilecek.

## 0.3.0 — 15 Ekim 2026

- Python: 89 test geçti. Eklenti: 64 test geçti. TypeScript kontrolü ve eklenti build'i geçti. Windows 0.3.0 paketi derlendi.
- Kapsam: eşik sınırları, ortak yıl/tür sorguları, sıfır/belirsiz sonuç, yakalama sırası ve bağlam, Chrome soğuk yeniden başlatmada indirme günlüğü, alakasız/bozuk RIS, kalıcı Zotero anahtarları ve kayıp yanıt uzlaştırması, kısmi yazma, eşzamanlı üyelik değişimi, not/karar koruması, Excel/PNG dosya koruması, şema yedeği.
- Bağımsız incelemedeki altı sorun giderildi: aynı pencerede sekme değişimi, otomatik çekimde aktif monitör, yeni kaynakların yerel not satırı, kalıcı indirme takibi, Excel başarısızlığında dışa aktarımı engelleme ve konu sorgularında yıl koşulunun konumu. Regresyon testleri eklendi.
- Canlı salt okunur Zotero 10 yerel API ve TEZ grubu görüldü. Canlı yeni yazma yetkisi, yeni Scopus sorgu/RIS indirme zinciri ve bütün konu paketi **henüz doğrulanmadı**.
- Kullanıcı günlük sürümü kullanmak istediği için kurulum güncellenmedi. Kurulu eklenti manifesti 0.2.1 olarak okundu. Günlük proje schema2'ye geçirilmedi; 0.3.0 testleri geçici projelerde yapıldı.
- Günlük dal: `feature/literatur-kayit` (`202d5dc`). Geliştirme dalı: `feature/otomatize`. Canlı kabul ayrı test ortamında devam edecek; bu sürüm tamamlandı olarak ilan edilmedi.

Önceki sürümlerin doğrulamaları aşağıdadır.

Bu belge otomatik test ile canlı kullanıcı kabulünü ayırır. Canlı veri tabanı uçtan uca kabulü tamamlanmadan ürünün bütün akışının doğrulandığı iddia edilmez.

## Tamamlanan kontroller

- Python unittest: 33 test; kalıcı kayıt, dosya bütünlüğü, saat dilimi, aynı aramaya ek görsel, yinelenen iş, değişmiş bağlam, bilinmeyen/sıfır sonuç, Excel metin güvenliği, kullanıcı Excel’inin korunması, yarım işlem kurtarma, Zotero kimliği/notları, kaynak kümesi, yedek ve yol dışına çıkma. Ek regresyonlar: galeri hatasından sonra kanıtın taşınmaması, paylaşılan SQLite işlem kilidi, büyük önizleme/mesaj sınırı, köprü kopması, takım koduna göre dosya adı, disk yazma hatası, Excel kilidi ve başka klasörde göreli kanıt bağlantıları.
- Eklenti: 11 JSDOM testi; 7 sentetik ve 4 gerçek Scopus DOM yapısından sadeleştirilmiş fixture testi; sıfır/yerel sayı biçimi/yaklaşık değer, çalıştırılmış sorgu, düzenlenmiş kutu, yüklenme/erişim/çelişkili sayım, makale sayfası ve alan adı benzerliği. Yeni test mevcut iki panelin yalnız `hidden` niteliğiyle değiştirilmesini de belirsiz yakalama sayıyor.
- TypeScript tür kontrolü ve esbuild derlemesi.
- Gerçek Windows 11, tek 1920×1080 monitör: MSS monitör yakalama. PNG’de görev çubuğu, saat ve tarih görsel olarak görüldü. Bu çekim Scopus üzerinde değildi.
- Normal kullanıcı oturumunda RegisterHotKey ve Win32 mesaj döngüsü; geçici Ctrl+Alt+9 kaydı başarılı. Sandbox bu işlemi Access denied ile engelliyor.
- Kullanıcı SID/oturumuna özel gerçek named pipe üzerinden 64 KB üzeri Türkçe mesaj ve yanıt; asenkron duplex okuma/yazma.
- Kaynak ve paketlenmiş NativeHost.exe’nin binary stdin/stdout → pipe → Application hello/status akışı izole projede geçti.
- Paketlenmiş tepsi uygulaması + NativeHost.exe birlikte açıldı; gerçek kısayol kaydı, status, pause, Excel ve ZIP yedek üretimi izole projede geçti.
- Son paket testinde tepsi süreci kapatıldı; Chrome tarafını temsil eden stdin açık tutulmasına rağmen NativeHost.exe 5 saniyelik sınır içinde normal çıkış yaptı. Yeniden bağlantıyı engelleyen açık köprü sorunu giderildi; gerçek Chrome yeniden bağlanması hâlâ kullanıcı kabulündedir.
- PDF/BibTeX sentetik veriyle üretildi; kaynak ve kanıt PDF’leri Poppler ile PNG’ye çevrilip görsel kontrol edildi. Türkçe karakterler ve görüntü sınırları düzgün.
- Yönetim ekranı ayrı yerel test sayfasında açıkça sentetik taşıma katmanıyla görüntülendi. Arama, ayar ve Zotero bölümleri erişilebilir DOM/açık etiketler içeriyor; incelenen sayfalarda konsol hata/uyarı kaydı yok. Bu test Chrome Native Messaging entegrasyonunun yerine geçmez.

## Açık kabul adımları

- Gerçek Chrome eklenti yüklemesi, Native Messaging kaydı ve HWND–Chrome pencere eşleştirmesi.
- Gerçek Ctrl+M → aktif Scopus sekmesi → PNG → DOM → Excel eşleşmesi.
- Gerçek iki sekme, iki pencere ve farklı Chrome profilleriyle hızlı geçiş.
- Basılı tutulan fiziksel Ctrl+M ve yakalama sırasında ikinci basış.
- Gerçek Scopus/IEEE/ACM/WoS ve VETİS/proxy adapter doğrulaması.
- Gerçek Zotero kütüphanesinin yerel/Web API’den okunması; koleksiyon ve not örnekleri.
- Fiziksel ikinci monitör, negatif koordinat ve farklı DPI.
- Gerçek Microsoft Excel kilidi; otomatik testlerde dosya koruma davranışı sınanır.

## Bağımsız inceleme

İnceleme iki kritik, dört önemli hata buldu. Her biri önce başarısız regresyon testiyle gösterildi ve düzeltildikten sonra bütün testler geçti. Küçük arayüz eksiği: Zotero kaynak listesinde önceki sayfa düğmesi yok; listeyi başa almak için yeniden okuma yapılabilir. Bu sürümde ertelendi. Artık bulunamayan Zotero kaydının Türkçe durum etiketi eklendi.

Kullanıcı adımları `MANUEL_TEST.md` içindedir. Bu liste başarı sonucu gelmeden “geçti” olarak değiştirilmez.

## 15 Ekim 2026 — Scopus ve Excel görünümü

- Scopus publications sayfasından alınan sadeleştirilmiş DOM ile çalıştırılmış sorgu, TITLE-ABS-KEY alanı, Boolean filtre ifadesi ve 12.773 sonuç doğrulandı. Düzenlenebilir sorgu, uygulanmamış filtre, eksik filtre paneli, sıfır sonuç ve çelişkili başlık durumları sınandı. Bu, tüm Scopus sayfa çeşitlerinin veya diğer platformların kabulü değildir.
- Gerçek projede S001 kaydı, PNG bağlantısı ve 12.773 sonuç mevcut. Kullanıcının tercihine göre Arama_Kaydi 11 sütunda kaldı; başlıklar ilk satıra taşındı. Üç sekmede ortak yazı, renk, kaydırma, sütun genişliği ve içerik uzunluğuna göre satır yüksekliği uygulandı. Proje bilgileri dosya özelliklerinde saklanıyor.
- Üç sekmenin görünümü render edilip incelendi. Önizleme aracı özel tarih biçimini seri sayı olarak gösterdiği için ayrıca Microsoft Excel'de salt okunur geçici kopya açıldı: tarih 15.10.2026 01:26:45, sonuç 12.773 olarak doğrulandı.
- Metinlerin formüle dönüşmemesi, sıfır değer, ilk veri satırı, göreli PNG galeri bağlantısı ve başka klasöre geri yükleme testleri geçti. Asıl 18 sütunlu kullanıcı şablonunun dosya özeti değişmedi.
- Gerçek açık Excel'in geçici ~$ sahiplik dosyası yedek almayı engelledi; bu geçici dosyalar yedekten çıkarıldı. Sahiplik dosyası varken Excel çıktısı ayrı sürüme yazılıyor. İki durum da önce başarısız regresyon testiyle gösterildi; düzeltme sonrası 33 Python testi geçti.
- Güncellenen paket gerçek kullanıcı kurulumuna kopyalandı; kurulu EXE özeti paketle eşleşti. Yeniden başlatılan kurulu uygulama gerçek projede 11 sütunlu Excel'i ve ZIP yedeğini üretti. Üretilen dosyada S001, 12.773 sonuç, tarih biçimi ve göreli galeri bağlantısı yeniden doğrulandı.

## 15 Ekim 2026 — Zotero bağlantısı ve onaylı yıl daraltması

- Kullanıcının Zotero yerel API izni sonrasında HTTP 200 alındı. Kurulu uygulama üzerinden TEZ grup kütüphanesi ve dört rol koleksiyonu eşleştirildi. Salt okunur kaynak okuması başarılı: grup boş, sıfır kaynak. Gerçek makale/not ve bunlardan teslim üretimi henüz sınanmadı.
- 41 Python testi geçti. Yeni testler 300/301, 1000/1001, 500/501 sınırlarını; ilk sayının ikinci aşama kararında korunmasını; onay ve profil/sekme eşleşmesini; tekrar onayının reddini; yeniden açılışta karar geçmişini; Scopus'un biriktirdiği yıl koşullarını; belirsiz yıl ifadelerini; önerinin PNG kaydından ve yakalama kilidinin bırakılmasından sonra açılmasını kapsıyor.
- 16 eklenti testi ve TypeScript tür kontrolü geçti. Yeni testler yıl alanlarının doldurulmasını, tek uygulama tıklamasını, eski sorgu/sayı reddini, arada değişen filtre/yüklenme reddini, eksik düğmede geri alma ve elle uygulama yolunu, onay ekranının kullanıcı tıklamasını beklemesini kapsıyor.
- Otomatik Scopus yıl uygulaması gerçek sayfada henüz denenmedi. Seçiciler kaydedilmiş publications DOM'una dayanıyor; uygulama düğmesi ve sonuçların yeniden yüklenmesi canlı kabul gerektiriyor. Birim/DOM testleri bu kabulün yerine geçmez.
- Kaydedilmiş Scopus arayüz kodunda yıl aralığının ancak alandan çıkışta işleme alındığı görüldü. Bu davranış fixture'a eklenince test başarısız oldu; alanların doldurulması sonrası odak/blur adımıyla düzeltildi. Son eklenti test sonucu yine 16/16.
- 0.2.0 Windows paketi derlendi ve gerçek kullanıcı kurulumuna kopyalandı. Önce proje ZIP yedeği ve önceki program dosyalarının yedeği alındı. Kurulu EXE/bridge dosyaları paket özetiyle eşleşti. Yeniden açılışta kısayol hatası yok, Chrome bağlantısı var, SQLite bütünlük kontrolü başarılı; 2 arama ve 5 PNG'nin dosya özetleri korundu. TEZ koleksiyonları yeniden okunabildi.
- Chrome eklentisinin arayüzden yeniden yüklenmesi tamamlanamadı: Computer Use aracı geçerli tarayıcı URL'sini yeterli güvenle belirleyemediği için durdu. Kurulu eklenti dosyaları güncel; kullanıcı chrome://extensions üzerinden Yeniden yükle düğmesine basmalı, Scopus sekmesini yenileyip yeni akışı denemeli.

## 0.2.1 — Scopus'un otomatik doldurduğu bitiş yılı

- Kullanıcı S003 için onay verdiğinde “Yıl seçimi değişti” hatası aldı. Kayıt geçmişi aramanın başlatılmadığını doğruluyor. Scopus'un React 18.3.1 aralık bileşeni ilk sınır işlenince diğer sınırı mevcut yıllardan dolduruyor. İki değer ilk blur öncesinde yazılınca 2026 üst sınırı 2027 ile değişebiliyor.
- Gerçek bileşenin taslak/işlenmiş değer ve karşı sınırı doldurma davranışı React fixture'ına eklendi; eski kod aynı hata ile başarısız oldu. Düzeltme başlangıç yılını doldurup işlenmesini bekliyor, sonra bitiş yılını dolduruyor. Son değerlerin ve mevcut sorgunun kontrolleri korunuyor; hata olursa beklenen/okunan yıllar da gösteriliyor.
- 17 eklenti testi ve TypeScript kontrolü geçti. Yeni regresyon hem boş aralıktan 2022–2026'ya hem de oradan 2024–2026'ya geçişi doğruluyor. Ayrı geçici profilli gerçek Chrome'da React örneği normal ve izole eklenti JavaScript ortamında 2022–2026'yı uyguladı. Kullanıcının Scopus oturumu bu testlerde kullanılmadı.
- React 18.3.1 ve React DOM 18.3.1 yalnız test bağımlılığıdır; eklenti paketine eklenmez. Chrome bağlam testi [ExecutionWorld belgesindeki](https://developer.chrome.com/docs/extensions/reference/api/scripting#type-ExecutionWorld) MAIN/ISOLATED ayrımını kullanır.
- Windows 0.2.1 paketi yedek alınarak kuruldu. Chrome'da mevcut eklenti yeniden yüklendi ve kartta 0.2.1 sürümü görüldü. Scopus sonuç sekmesi yenilendi. Python 41/41, eklenti 17/17 geçti; canlı Scopus'taki yeni Uygula ve ara denemesi kullanıcı adımıdır.
- Sayfa yenilemesi ardından VETİS `/coproxy/error/401` adresinde “Unauthorized / Sorry, you are not authorized” döndürdü. Canlı düzeltme kabulü bu nedenle tamamlanamadı. Kullanıcının kurumsal erişimi yeniden açması gerekiyor; oturum açma veya erişim ayarları otomatik değiştirilmedi.

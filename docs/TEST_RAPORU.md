# Doğrulama kapsamı — 0.2.0

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

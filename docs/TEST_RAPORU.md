# Doğrulama kapsamı — 0.1.0

Bu belge otomatik test ile canlı kullanıcı kabulünü ayırır. Canlı veri tabanı uçtan uca kabulü tamamlanmadan ürünün bütün akışının doğrulandığı iddia edilmez.

## Tamamlanan kontroller

- Python unittest: 31 test; kalıcı kayıt, dosya bütünlüğü, saat dilimi, aynı aramaya ek görsel, yinelenen iş, değişmiş bağlam, bilinmeyen/sıfır sonuç, Excel metin güvenliği, kullanıcı Excel’inin korunması, yarım işlem kurtarma, Zotero kimliği/notları, kaynak kümesi, yedek ve yol dışına çıkma. Ek regresyonlar: galeri hatasından sonra kanıtın taşınmaması, paylaşılan SQLite işlem kilidi, büyük önizleme/mesaj sınırı, köprü kopması, takım koduna göre dosya adı, disk yazma hatası, Excel kilidi ve başka klasörde göreli kanıt bağlantıları.
- Eklenti: 7 sentetik JSDOM testi; sıfır/yerel sayı biçimi/yaklaşık değer, çalıştırılmış sorgu, düzenlenmiş kutu, yüklenme/erişim/çelişkili sayım, makale sayfası ve alan adı benzerliği. Yeni test mevcut iki panelin yalnız `hidden` niteliğiyle değiştirilmesini de belirsiz yakalama sayıyor.
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

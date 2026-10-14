# Literatür Kayıt Asistanı

Windows 11 ve Chrome için yerel uygulama, Chrome eklentisi ve kaynak kod. Sürüm 0.1.0 bir kabul testi sürümüdür. Canlı Scopus, IEEE, ACM, WoS ve kurumsal proxy ekranları henüz doğrulanmadı; ilk gerçek arama aşağıdaki testle kontrol edilmelidir.

## Kurulum

1. `release/LiteraturKayit-0.1.0/Kurulum.exe` dosyasını açın. ZIP kullanıyorsanız önce **tamamını** bir klasöre çıkarın; `payload` klasörü EXE’nin yanında kalmalı.
2. Proje klasörünü `D:\Hasan_Desktop\Hasan\Tez\OEC-1017_O2` olarak seçip **Kur ve başlat** düğmesine basın. Yönetici izni gerekmez. Windows başlangıcında çalıştırma isteğe bağlıdır.
3. Chrome’da `chrome://extensions` adresini açın. **Geliştirici modu → Paketlenmemiş öğe yükle** ile `%LOCALAPPDATA%\LiteraturKayit\extension` klasörünü seçin. Kurucu bu yolu panoya kopyalar.
4. Eklenti kimliği `bdboonffghjgpgnkbhekphddmncanlld` olmalı. Eklentiyi Chrome araç çubuğuna sabitleyin.
5. Eklentide **Kayıtlar ve ayarlar** bölümünü açın. Proje adı, takım kodu ve kaydı yapan kişiyi kontrol edin. Başlangıçta arama listesi boştur.
6. Araştırma sitesinde bir sonuç sayfası açın. Eklenti simgesinden **Bu sitede etkinleştir** seçin. Proxy kullanılıyorsa izin, gerçekten açık olan proxy adresi için verilir.
7. Sonuç sayfasına dönüp Ctrl+M yapın. İlk PNG’de Windows saati, tarih ve adres çubuğunun göründüğünü kontrol edin. Ayarlar’daki saat/tarih kontrolünü bundan sonra işaretleyin.

Günlük kullanım terminal gerektirmez. Başlat menüsündeki **Literatür Kayıt Asistanı** tepsi uygulamasını açar. Chrome bağlantısı da kapalı uygulamayı başlatabilir. Tepsi menüsünden duraklatma, son PNG ve proje klasörü erişilebilir. Chrome açılışında pencereyi Windows ile eşleştiren kısa süreli arka plan sekmesi oluşabilir; yakalama sırasında yeni sekme açılmaz.

## Bir aramayı kaydetme

Aramayı çalıştırın ve yüklenmenin bitmesini bekleyin. Sorgu, sonuç sayısı, Windows görev çubuğu ve adres çubuğu görünürken Ctrl+M’ye basın. Windows monitörün tamamını yakalar; ardından eklenti o penceredeki aktif sekmeyi okur. Bu sırada sekme değiştirmeyin.

Başarılı kayıt `S001` gibi bir kimlik alır. Görseller `02_Ekranlar/S001/` altında `S001_YYYYMMDD_a_sonuc.png` biçiminde tutulur. Tarih gerçek çekim anının İstanbul tarihidir. Aynı aramaya ek çekimler `_v02` gibi sürümlenir. Sorgu/filtre değişikliği veya farklı gün yeni çalıştırma oluşturur. Aynı sorguyu bilerek yeniden çalıştırırken **Sonraki yakalamayı yeni arama say** kullanılabilir.

Eşleşme belirsizse PNG korunur; **Eksik kayıtlar → Kontrol et** bölümünde gerçek PNG’ye bakarak alanları tamamlayın. İçe aktarılan PNG’nin çekim zamanı bilinmiyorsa bilinmiyor olarak kalır. Sayfa çalıştırılmış sorguyu göstermiyorsa makale başlığından sorgu veya sonuç sayısı üretilmez.

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

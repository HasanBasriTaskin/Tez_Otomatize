# Kullanıcı kabul testi

Önce yalnız 1–5 adımlarını yapın. Bir adım beklenenden farklıysa sonraki testi zorlamayın; adım numarasını, ekrandaki mesajı ve oluşan dosyanın adını bildirin. Parola, API anahtarı veya çerez paylaşmanız gerekmez. Canlı Scopus ve kurumsal proxy testi için kendi normal oturumunuz kullanılmalıdır.

## İlk akış — yaklaşık 5 dakika

1. `Kurulum.exe → Kur ve başlat` ile Windows uygulamasını kurun. Chrome `chrome://extensions` sayfasından Geliştirici modu → Paketlenmemiş öğe yükle → `%LOCALAPPDATA%\LiteraturKayit\extension`. Eklenti simgesini sabitleyin. **Beklenen:** yönetim ekranında Windows bağlantısı hazır.
2. Scopus’ta kendi sorgunuzu çalıştırın. Sonuçlar yüklenince eklentiden **Bu sitede etkinleştir** seçin. Popup’ı kapatın. **Beklenen:** açık olan site/proxy izni verilmiş, sonuç sekmesi aktif.
3. Sonuç sayısı ve sorgu görünürken **Ctrl+M’ye bir kez basın**. Yakalama bitene kadar sekme değiştirmeyin. **Beklenen:** çekimden sonra bildirim, ardından ya S001 kaydı ya da eksik kayıt. Eksik kayıt, otomatik çıkarımın henüz doğrulanmadığı anlamına gelir; PNG kaybolmamalı.
4. Özgün PNG’yi açın. **Kontrol:** tüm monitör, Windows görev çubuğu, saat, tarih, Chrome adres çubuğu; ekrandaki sorgu/sonuç ile görüntü aynı. Saat/tarih görünüyorsa Ayarlar’daki kontrolü işaretleyin. Eksik kayıt varsa o PNG’ye bakarak alanları doldurup doğrulayın. **Beklenen:** `02_Ekranlar/S001/S001_YYYYMMDD_a_sonuc.png` ve 03_Calisma altında üretilen Excel.
5. Excel’in **Arama_Kaydi** sayfasını açın. **Kontrol:** tek arama satırı, tam sorgu, doğru filtre/sonuç, boş dışa aktarım sayısı. Ekran dosyası bağlantısı görüntü dizinini açmalı. Mevcut Excel korunduysa bildirilen yeni sürümü açın.

Yanıt örneği: “1–2 geçti. 3 eksik kayıt dedi. 4 PNG doğru. Sonuç 184, sorgu alanı boş. 5 manuel doğrulama sonrası tek satır.” Bu bilgiyle gerçek sayfanın adapterını kesinleştirebiliriz.

## Doğru sekme ve tekrarlar

6. İki farklı sorguyu iki sekmede açın. Sırayla Ctrl+M yapın. Her PNG ve Excel satırı o anki aktif sekmeyle eşleşmeli. İkinci bir Chrome penceresinde de tekrarlayın.
7. Ctrl+M’den hemen sonra başka sekmeye/pencereye geçin. **Beklenen:** ya çekim başlamadan reddedilir ya da PNG eksik kayıt olarak korunur; eski görüntüye yeni sekme bilgisi bağlanmaz.
8. Sabit sonuç sayfasında Ctrl+M’yi iki saniye basılı tutun. **Beklenen:** tek yakalama. Yakalama sürerken ikinci basış ilk işin bağlamını değiştirmemeli.
9. Aynı aramayı değiştirmeden iki ayrı çekim yapın. **Beklenen:** tek arama satırı, iki PNG; ikinci dosyada `_v02`. Otomatik çıkarım eksikse manuel formda **Mevcut aramaya ekle: S001** kullanın. Bilgiler farklıysa ekleme reddedilmeli.
10. Sorgu veya uygulanmış filtreyi değiştirip yeniden arayın. **Beklenen:** yeni arama kimliği. Eski PNG’ler değişmemeli.

## Eksik bilgiler ve toparlanma

11. Gerçek sıfır sonuç araması yapın. **Beklenen:** doğrulanmış `0`, boş/bilinmeyen sayıya dönüşmez. Yaklaşık veya `10,000+` görünüyorsa niteliği ayrıca korunmalı.
12. Yeni sorguyu kutuya yazın ama çalıştırmayın; Ctrl+M yapın. **Beklenen:** belirsizlik/eksik kayıt; eski sonuçlarla yeni sorgu otomatik birleştirilmez.
13. Bir PNG’yi **Eksik kayıtlar → PNG içe aktar** ile seçin. **Beklenen:** gerçek çekim zamanı bilinmiyor; içe aktarma zamanı ayrı. Eksik alanları tamamlayabilirsiniz.
14. Excel’i açık tutup yeni kayıt alın. **Beklenen:** SQLite kaydı ve PNG korunur; yazma kilitliyse Excel ayrı sürüme çıkar. Excel’de bir hücreyi değiştirip kaydedin, eklentiden yenileyin: elle değiştirilmiş dosya ezilmemeli.
15. Tepsi uygulamasını kapatıp açın. **Beklenen:** kayıtlar/eksik işler durur. Chrome yeniden bağlanır. Elektriği kesmek veya diski doldurmak gerekmiyor; bu hata senaryoları otomatik testlerle sınanır.
16. **Yedek al → Yedeği geri yükle** ile başka klasöre yükleyin. Ayarlar’dan yeni projeyi seçin. **Beklenen:** kayıtlar, PNG’ler ve Excel’in göreli kanıt bağlantıları çalışır. Sonra ana projeye dönebilirsiniz.

## İkinci aşama — temel akış geçtikten sonra

17. Zotero yerel API erişimini açın; kişisel kütüphane `users/0`. Eklentide koleksiyonları getirip dahil/hariç rollerini eşleştirin. **Beklenen:** yalnız okuma, Zotero’da hiçbir kayıt değişmez.
18. Bir makalenin bağlı notuna şablon alanlarını ve Anotasyon’u girin. Yeniden okuyun, kaynak arama kimliklerini bağlayın, anotasyonu kontrol edildi işaretleyin. **Beklenen:** kaynak tek kayıt, birden fazla arama bağlantısı korunur.
19. Kaynak PDF’si/BibTeX ve ekran PDF’si üretin. **Beklenen:** PDF/BibTeX aynı kaynak sayısı/kimlikleri; Türkçe metin doğru; anotasyon var; görüntüler kırpılmamış. Kontrol edilmemiş anotasyon final üretimi durdurur.
20. IEEE, ACM ve WoS için ilk beş adımı ayrı tekrarlayın. Bir platformdaki başarı diğer platformun doğrulandığı anlamına gelmez.

Fiziksel olarak ek monitör varsa negatif koordinat, farklı DPI ve Chrome’u ekranlar arasında taşıma ayrıca sınanmalıdır. Bu bilgisayardaki tek monitör testi çoklu monitör desteğini doğrulamaz.

## 0.2.0 — Onaylı yıl daraltması

1. Scopus'ta yıl sınırı olmayan, sonucu 300'den büyük aramanızı açıp Ctrl+M yapın. Önce kayıt alınmalı, sonra **Aramayı daraltalım mı?** açılmalı. Öneri 2022–2026 olmalı; siz onaylamadan sayfa değişmemeli.
2. **Uygula ve ara** seçin. Scopus'ta 2022–2026 uygulanıp yeni sonuçlar gelmeli. Kontrol edilen düğme bulunamazsa pencere hata ve elle uygulama seçeneği göstermeli; hazır sorguyu aynı sekmede gelişmiş aramaya yapıştırıp çalıştırabilirsiniz.
3. Sonuçlar yüklenince tekrar Ctrl+M yapın. Yeni arama satırındaki sorgu/sonuç PNG ile eşleşmeli. Açıklama önceki S kimliğini ve gerekçeyi içermeli. İlk sonuç 1000 üstü, bu yeni sonuç da 500 üstüyse 2024–2026 önerisi gelmeli; diğer durumlarda gelmemeli.
4. İkinci öneriyi onaylayıp sonuçlar yüklenince Ctrl+M yapın. Üçüncü kayıt oluşmalı; bu akışta başka yıl önerilmemeli. Önceki görüntüler ve kayıtlar korunmalı.
5. Başka bir öneride **Şimdi değil** seçin: sorgu değişmemeli. Kayıt ayrıntısından öneri yeniden açılabilmeli. Öneri açıkken asıl sorguyu değiştirip **Uygula ve ara** seçerseniz eski öneri uygulanmamalı; yeni Ctrl+M istenmeli.

Zotero bağlantısı bu bilgisayarda TEZ grubuna kuruludur. Zotero açıkken **Zotero'dan oku** kullanılabilir. Boş grup için sıfır kaynak normaldir; ilk gerçek kaynak/not ve teslim çıktısı kontrolü 18–19. adımlardadır.

## 0.3.0 — otomatik tarama kabulü (ayrı test kurulumu)

Günlük 0.2.1 kurulumu korunur. Önce ayrı proje ve çakışmayan test kurulumunda küçük gerçek sorguyla PNG → Excel → RIS → Zotero zinciri doğrulanır. İzin penceresi kullanıcı tarafından yanıtlanır; Scopus kişisel oturumu Export için açık olmalıdır. İlk zincir doğrulanmadan altı sorgunun tamamı kabul edilmiş sayılmaz.

1. Sorgu paketinin başlangıç + altı konu metnini ve ar/cp, isteğe bağlı re seçimini karşılaştırın. İlk aramada yıl/tür olmamalı.
2. Tek başlangıçtan sonra Scopus önde kalsın. Ara onay/Ctrl+M olmadan yıl adımları ve konular ilerlemeli. Ortak yıl ve belge türleri her PNG/Excel satırında doğru olmalı.
3. Her RIS dosyasının gerçek TY/ER kayıt sayısı ve dışa aktarma aralığı eşleşmeli. Sıfır sonuçta RIS/öğe üretilmemeli; başlangıç/yıl denemeleri dışa aktarılmamalı.
4. TEZ → 01_Aday ve 00_AramaKayitlari altındaki arama ilişkilerini kontrol edin. Aynı EID iki aramada bir Zotero kaydı olmalı. DOI benzerliği birleştirilmemeli. Yerel taslak kaydedilip yeniden açılabilmeli.
5. Başka sekmeye/uygulamaya geçin; tarama durmalı. Devam ile aynı adıma dönmeli. Özellikle Zotero aktarımı sırasında aynı Chrome penceresinde sekme değişimini sınayın.
6. RIS indirmesi sırasında Chrome’u kapatıp açın. Mevcut indirme kendi kimliğiyle bulunmalı; belirsizlikte tekrar gönderim yapılmadan kontrol istenmeli.
7. Excel kilidinde ayrı sürümün yolu görünmeli. Disk/RIS sayım/izin hatasında kayıt korunmalı; adım tamamlandı görünmemeli.
8. Bütün paket sonunda PNG, 11 sütunlu Excel, RIS ham toplamı ve Zotero benzersiz/arama ilişkilerini karşılaştırın. Gerçek süre sistem saatinden ayrı ölçülmeli.

Bu adımlar henüz canlı tamamlanmadı; otomatik testler bunların fiziksel bilgisayarda geçtiğini kanıtlamaz.

## 0.8.0 — Başlık-özet elemesini Zotero'ya işleme

Önce **Deneme** projesinde, Deneme Zotero koleksiyonlarıyla 5–10 kayıtlık bir karar dosyası kullanın.

1. Karar dosyasında bir başlığı bilerek değiştirin → Denetle: "başlık Zotero kaydıyla aynı değil" görünmeli; onay ve
   uygulama pasif olmalı. Düzeltin.
2. Kutu işaretlenmeden **Kararları onayla** → uyarı; dosya değişmemeli. Kutuyla onay → `Yedekler`de onay öncesi kopya,
   panelde "Onaylı: <ad>, <tarih>".
3. Onaydan sonra dosyada bir kararı değiştirin → "Onay geçersiz" görünmeli, **Zotero'ya uygula** pasif olmalı.
   Değişikliği geri alın.
4. **Zotero'ya uygula** → koleksiyonlar, etiketler ve hariç notları; notu Zotero'da açıp alanları okuyun. Kayıtlar
   01_Aday'da kalmalı; önceden olan etiket ve koleksiyonlar korunmalı.
5. Uygulama sürerken Zotero'yu kapatın → hata; Zotero'yu açıp yeniden **Zotero'ya uygula** → kaldığı yerden devam,
   her hariç kaydında tek not.
6. **Teslim kontrolü** ve **PRISMA şeması (PDF)**: sayılar karar dosyasıyla aynı olmalı.

Asıl projede (OEC-1017_O2) önce proje yedeği ve Zotero veri klasörünün (`zotero.sqlite`) kopyası alınır. Beklenen:
05_Haric_BaslikOzet 1.262, 02_BaslikOzet_Gecen 1.626, 06_Erisim_Kontrol 54, 1.262 hariç notu.

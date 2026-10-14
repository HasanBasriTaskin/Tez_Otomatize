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

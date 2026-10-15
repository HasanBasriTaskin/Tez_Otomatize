# Scopus otomasyonu — onaylanan ilk teslim

15 Ekim 2026: Kullanıcı başlangıç + yıl kararı + altı konu sorgusunun tek başlangıçla yürütülmesini, gerçek Windows PNG/Excel/RIS kayıtlarını ve TEZ grubuna otomatik künye aktarımını onayladı. PDF okuma, YZ sağlayıcısı, IEEE/ACM ve nihai kaynak seçimi bu teslimin dışında.

Başlangıç yıl/tür filtresiz. <=300 yıl yok; 301–1000 2022–2026; >1000 önce 2022–2026, bunun sonucu >500 ise 2024–2026. Konu aramalarında ortak yıl, ar/cp; Review kullanıcı seçimi. Kaynak: ../../output/revizyon/teslim/OEC-1017_O2_Sorgular.txt (tez köküne göre).

Her konuda sorguyu doğrula → PNG → Excel → tüm sonuçların RIS dosyası → gerçek sayım → Zotero → sonraki. Sıfır sonuç dosya/öğe üretmeden tamamlanır. Bilinmeyen sonuç, odak kaybı, erişim/izin veya belirsiz işlem duraklatır. Tamamlanmamış işlem başarılı sayılmaz. Saat değiştirme/yapay okuma yok. Eski kayıtlar korunur.

## İşler ve ilerleme

- [x] Kalıcı oturum/adım/aktarım ve schema 2 migration, yedek, eşik testleri.
- [x] Aynı yakalama motoru ile sessiz otomatik PNG, eşzamanlı kısayol ve odak koruması.
- [x] Scopus kısa DOM eylemleri, Chrome indirme korelasyonu, devam/yeniden başlatma.
- [x] RIS doğrulama, Zotero 10 yetkilendirme/yazma ve tekrar işlem uzlaştırması.
- [x] Türkçe yönetim ekranı, ön kontroller, durum/duraklat/devam/durdur.
- [x] Birleşik otomatik testler, bağımsız inceleme, geliştirme paketi.
- [ ] İzole gerçek Scopus/RIS/Zotero zinciri ve tüm paket kabulü. Günlük kurulum güncellenmedi.

## 15 Ekim — geliştirme ve günlük kullanım ayrımı

Kullanıcının son isteğiyle günlük sürüm korunmuştur. `feature/literatur-kayit` dalı otomasyon öncesi `202d5dc` commit'indedir. Otomasyonun bütün değişiklikleri `feature/otomatize` dalındadır. Kurulu Chrome eklentisi ve Windows uygulaması 0.2.1 olarak bırakılmıştır; 0.3.0 yalnız geliştirme paketidir.

Günlük proje üzerinde schema2 migration veya yeni otomasyon çalıştırılmadı. Canlı test devam ederken ayrı test projesi ve günlük eklentiyle çakışmayan test kurulumu kullanılmalıdır. Yeni paketin varsayılan proje yolu günlük projeyi gösterdiğinden kabul testinden önce değiştirilmelidir. Günlük kuruluma geçiş kullanıcı bu sürüme geçmek istediğinde yapılacaktır.

## Entegrasyon sözleşmeleri

Python iş akışı tek yürütücüdür. Eklenti `workflow_browser` ile yalnız izin verilen kısa DOM eylemlerini yürütür. `runScopusAction(doc,url,action,p)` sonucu stage/nextAction/data taşır. Dosya bitişi Chrome download ID ile doğrulanır; native taraf dosyayı kopyalamadan yol/biçim/hash/sayım kontrol eder.

`parse_ris(bytes)` EID ve Zotero veri alanları olan kayıtlar döndürür. `ZoteroWriter.preflight(authorize=False)` ve `import_records(records, session_id, search_id, check_cancel)` yalnız yerel API/konfigüre TEZ grubuna yazar. Kimlikler yazmadan önce SQLite'a kaydedilir. Aynı EID tekrar oluşturulmaz; DOI benzerliği birleştirme nedeni değildir.

## Kabul

Tek başlatmadan sonra Ctrl+M/ara onay olmadan bütün Scopus adımları; her arama için sorgu/filtre/sayı/PNG eşleşmesi; RIS gerçek sayıları ve Zotero ilişkileri. 120 sn sayfa, 15 dk export bekleme. Canlı giriş/izin engeli geçilmeden kabul tamamlanmış sayılmaz. İlk kurulumdaki Zotero yetki diyaloğunu yalnız kullanıcı onaylar.

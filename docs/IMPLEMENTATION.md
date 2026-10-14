# Uygulama planı ve ilerleme

Onay: 14 Ekim 2026 konuşmasındaki Windows ekran yakalama planı.

## Sabit kararlar
- Veri kökü uygulamanın üst klasörü OEC-1017_O2; yalnız yeni arama kayıtları.
- Windows tam monitör PNG üretir; eklenti yalnız aktif sekmenin DOM bilgisini okur.
- CaptureJobId tüm adımlarda aynı; bağlam değişirse dosya korunur, otomatik eşleştirme yapılmaz.
- SQLite asıl kayıt kaynağı; Excel üç sayfalı türetilmiş görünüm.
- Köprü yalnız izinli eklenti, kullanıcı oturumuna özel named pipe ve sınırlı komutlarla çalışır.
- Kullanıcı Git ve aşamalı commit istedi. Yeni ayrı depo/dal kullanılıyor; mevcut tez dosyaları Git'e alınmıyor.
- Canlı platform erişimi yoksa adapter doğrulanmış sayılmayacak. Sentetik fixture yalnız regresyon testi.

## İş sırası
1. Kalıcı işler, PNG bütünlüğü, arama kimlikleri, Excel ve kurtarma testleri.
2. Windows hotkey/yakalama, native IPC, aktif pencere eşleştirme ve eklenti.
3. Platform adapterları, manuel düzeltme ve kurulum arayüzü.
4. Zotero okuma, not eşleştirme, PDF/BibTeX ve yedek/geri yükleme.
5. Windows paketi, gerçek yakalama/bağlantı kontrolü, bağımsız inceleme ve kullanım belgesi.

## Arayüz ön kontrolü
- Eklenti ile köprü: v=1, id, type, payload; yakalama için jobId ve window/tab/document bağlamı.
- Native köprü stdout yalnız uzunluk önekli UTF-8 JSON; görseller diskte.
- Host tarafından doğrulanan HWND yalnız bağlantı sayfasından gelir; service worker HWND=0 eşleştirme yapmaz.
- Tek seferde bir yakalama; ikinci basış ilk bağlamı değiştirmez.

## İlerleme
- Ortam: Windows 11 build 26200, tek monitör, Python 3.12.14; Git 2.54 kurulu.
- Mevcut Excel: 11/28/6 sütunlu üç sayfa başlıkları incelendi. Yeni çalışma kitabında eski satırlar kullanılmayacak.
- Ruling: Tez klasöründe mevcut Git deposu olmadığından Uygulama içinde yeni bağımsız feature dalı oluşturuldu; ek worktree gerekmiyor.
- Python venv bootstrap sistem geçici klasöründe izin hatası verdi; geliştirme geçici dosyaları depo içindeki .tmp altında tutulacak.
- 2–4: Windows/Chrome bağlantısı, yönetim arayüzü, Zotero okuma, PDF/BibTeX ve yedek kodu eklendi. Canlı entegrasyon kabulü henüz açık.
- Test: Python unittest 21/21, eklenti sentetik DOM 6/6; TypeScript typecheck geçti.
- Gerçek cihaz kontrolü: MSS 1920x1080 PNG, Windows görev çubuğu/saat/tarih görsel olarak doğrulandı. Normal kullanıcı oturumunda geçici Ctrl+Alt+9 RegisterHotKey başarılı; sandbox Access denied üretiyor.
- PNG bütünlüğü doğrulama öncesi yeniden kontrol ediliyor. Zotero tam okumada artık bulunamayan kayıtlar silinmeden unavailable durumuna alınıyor; iki regresyon RED→GREEN.
- Windows IPC gerçek test: senkron ReadFile/WriteFile çift yönlü bağlantıyı kilitledi; FILE_FLAG_OVERLAPPED, ayrı olaylar ve önceden ayrılmış okuma tamponuyla düzeltildi. Kaynak ve EXE köprüsü geçti.
- Paket: Python içeren iki EXE, kullanıcı düzeyinde Kurulum.exe, sabit kimlikli eklenti, ZIP ve Türkçe kılavuz hazır. Registry/Chrome gerçek kurulum kabulü kullanıcı adımı olarak açık.
- Final review: bağımsız gpt-6-astra incelemesi iki kritik/dört önemli hata bildirdi. Düzeltilenler: terminal verified durumunun korunması + job/capture idempotency; tüm DOM nitelik değişimlerinin izlenmesi; bütün paylaşılan SQLite komutlarının aynı kilidi kullanması; pipe EOF ile bridge kapanması; boyut sınırlı önizleme + açık protokol hatası + eksik kayıt sayfalama; bütün Excel kullanıcı metinlerinin literal yazılması. Regresyonların her biri RED→GREEN. Son birim test: Python31/31, TS7/7, typecheck başarılı.
- Ek kabul otomasyonu: disk yazma hatası, Excel kilidi, yedeğin farklı klasöre yüklenmesinden sonra göreli Excel/PNG bağlantıları geçti. Paketlenmiş tepsi+köprü hello/status/pause/export_excel/backup geçti.
- Final: Ruling: canlı adapter, gerçek HWND/sekme, çoklu monitör ve Zotero kabulü açık bırakıldı — kullanıcı canlı testi yapmayı teklif etti; eldeki sahte fixture'lar bu davranışları kanıtlamaz — yanlış kabul edilirse yanlış araştırma kaydı riski vardır, bu nedenle canlı destek doğrulandı olarak etiketlenmiyor.
- Final: Ruling: AI/OCR, RIS içe alma ve çok kullanıcılı birleştirme bu sürüme eklenmedi — onaylı temel plan ve isteğe bağlı sonraki işler sınırı — dışa aktarılan kayıt sayısı bilinmiyor kalır, okuma notunu kullanıcı sağlar.
- Final: Ruling: unavailable kaynak etiketi küçük görsel sorun yerine yanlış durum anlaşılması riski sayılıp Türkçeleştirildi — kaldırılmış kaynakların teslim kümesinden çıktığı anlaşılmalı.
- Final: minor (deferred): Zotero listesinde önceki sayfa düğmesi; yeniden okuma listeyi başa alır.
- Git entegrasyonu: yeni bağımsız yerel repo olduğu ve kullanıcı yalnız commit istediği için feature/literatur-kayit dalı korunuyor; uzak depo/PR oluşturulmadı.
- Son teslim doğrulaması: yeniden derlenen EXE tepsi+host hello/status/pause/Excel/backup ve tepsi kapandığında stdin açıkken host kapanması geçti. Test süreçleri kapatıldı. Gerçek proje Excel'i korunmuş durumda; QA kayıtları yalnız .tmp/qa-output içinde.

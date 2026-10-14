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

# Literatür Kayıt Asistanı

Windows ve Chrome üzerinde literatür aramalarını gerçek ekran görüntüsü, sorgu, filtre ve sonuç sayısıyla kaydeder. Excel ve proje klasörleri otomatik oluşturulur.

| Dal | Sürüm | Kapsam |
|---|---|---|
| `main` | 0.2.1 | Manuel Ctrl+M kaydı ve onaylı yıl daraltma |
| `feature/otomatize` | 0.3.0 | Sorgu düzenleyicisi ve otomatik Scopus/Zotero akışı; ön sürüm |

## Kurulum

1. [0.2.1 manuel sürümü](https://github.com/HasanBasriTaskin/Tez_Otomatize/releases/tag/v0.2.1) veya [0.3.0 ön sürümünü](https://github.com/HasanBasriTaskin/Tez_Otomatize/releases/tag/v0.3.0) açın. **Assets → LiteraturKayit-<sürüm>.zip** dosyasını indirin. **Source code** kurulum paketi değildir.
2. ZIP'in tamamını çıkarın. **Kurulum.exe** dosyasını açın, kendi proje klasörünüzü seçip **Kur ve başlat** düğmesini kullanın. `payload` klasörü EXE'nin yanında kalmalıdır.
3. Chrome'da `chrome://extensions` → **Geliştirici modu → Paketlenmemiş öğe yükle** ile `%LOCALAPPDATA%\LiteraturKayit\extension` klasörünü seçin.
4. Araştırma sitesinde eklentiyi açıp **Bu sitede etkinleştir** seçin. **Kayıtlar ve ayarlar** bölümünde kaydı yapan kişiyi belirtin.

Son kullanıcı için Python, Node.js ve Git gerekmez. Güncellemeden önce uygulamadan yedek alın, tepsi menüsünden çıkış yapın. Kurulumdan sonra Chrome eklentisini yenileyin.

## Kullanım

Uygulama çalışırken Chrome'da aramayı açın. Sorgu, sonuç sayısı, adres çubuğu ve Windows saat/tarihi görünürken **Ctrl+M** yapın. PNG `02_Ekranlar`, Excel `03_Calisma` altında oluşur. Yıl daraltmasını onayladıysanız sonuçlar yüklenince yeniden Ctrl+M yapın. Manuel akış sonraki sorguyu sizin girmenizi bekler.

**ÖNEMLİ — Sorgular:** Manuel kullanımda sorguyu doğrudan Scopus'a yazın. 0.3.0'da otomatik sorgular **Otomatik tarama → Sorguları düzenle** bölümünden veya `03_Calisma/sorgu-paketi.json` dosyasından değiştirilir; yeniden build gerekmez. Hazır paket OEC-1017 konusuna aittir. Otomatik Zotero yazma mevcut **TEZ** grubu içindir. Otomatik Scopus → RIS → Zotero zincirinin canlı kabulü henüz tamamlanmamıştır.

Her kullanıcı ayrı proje klasörü kullanmalıdır. İki kişinin SQLite/Excel dosyalarını üst üste kopyalamayın; otomatik proje birleştirme henüz yoktur.

## Build

Windows x64, Python **3.12** ve Node.js **24** gerekir. Depo kökünde [build.bat](build.bat) dosyasına çift tıklayın veya çalıştırın:

```powershell
.\build.bat
```

Bağımlılıklar hazırlanır, testler çalışır, eski build çıktıları temizlenir; Windows ve eklenti birlikte derlenir. Sonuçlar `artifacts/windows`, `artifacts/extension` ve `artifacts/release` altındadır. Dağıtılacak dosya `artifacts/release` içindeki ZIP'tir. Build çıktıları Git'e eklenmez; build almak kurulu uygulamayı güncellemez.

## Otomatik yayın

Dal push'larında Actions test ve build yapar. Paket sürümüyle aynı **vX.Y.Z** etiketi gönderildiğinde ZIP ve SHA-256 ayrıca **Releases** sayfasında yayımlanır. Test başarısızsa yayın yapılmaz. `release.json` içindeki `prerelease` alanı ön sürüm/kararlı ayrımını belirler. Ön sürümler **Latest** kararlı sürümün yerini almaz.

## Belgeler

- [Ayrıntılı kurulum, kullanım ve sorun giderme](docs/KILAVUZ.md)
- [Yeni sürüm yayımlama](docs/YAYINLAMA.md)
- [Manuel kabul testleri](docs/MANUEL_TEST.md)

`.env` veya yapay zekâ API anahtarı gerekmez. Public depo herkes tarafından okunabilir; doğrudan push yetkisi yalnız yetkilendirilmiş hesaplardadır.

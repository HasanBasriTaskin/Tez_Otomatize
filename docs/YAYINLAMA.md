# Sürüm yayımlama

Her yayın, sürüm etiketinin işaret ettiği kaynak koddan üretilir. Release yayımlamak dalları birleştirmez veya kurulu uygulamaları değiştirmez. Kullanıcı kurulum adımları için [README](../README.md#releases-üzerinden-kurulum) bölümüne bakın.

## Yeni sürüm

Yayımlanacak dalda değişiklikleri tamamlayın. Aşağıdaki `0.3.1` örneğini yeni sürüm numaranızla değiştirin:

1. `npm version 0.3.1 --no-git-tag-version` çalıştırın. `package.json` ve `package-lock.json` birlikte güncellenir.
2. `docs/releases/v0.3.1.md` dosyasına değişiklikleri, kurulum bilgisini ve bilinen sınırları yazın.
3. `release.json` içinde `prerelease: true` geliştirme/ön sürüm; `false` kararlı sürüm içindir. Canlı kabul tamamlanana kadar otomasyon sürümlerinde `true` kullanın.
4. Değişiklikleri commit edip dalı push edin.
5. Tam bu commit için etiketi gönderin:

   ```powershell
   git tag -a v0.3.1 -m "Release 0.3.1"
   git push origin v0.3.1
   ```

Actions testleri çalıştırır, Windows ve Chrome paketini üretir, ZIP/SHA-256 doğrular, dosyaları bir taslak Release'e yükler ve yükleme tamamlanınca yayımlar. Ek API anahtarı gerekmez. Windows build işi salt okunur; yalnız yayın işi `contents: write` yetkisi alır.

## Tetikleme ve hata davranışı

- Dal push'u ve **Run workflow**: test/build ve Actions artifact üretir.
- `vX.Y.Z` etiketi push'u: aynı kontrollerden sonra Releases yayını yapar. Etiket ile paket sürümü aynı olmalı; sürüm notu bulunmalı.
- Yükleme yarım kalırsa taslak gizli kalır. Aynı Actions çalıştırmasında **Re-run failed jobs** ile yayın tekrar denenebilir.
- Yayımlanmış bir sürümün dosyaları yeniden yazılmaz. Yeni değişiklik için yeni sürüm numarası ve etiket gerekir.
- Ön sürüm, **Latest** kararlı sürümün yerini almaz. Bu nedenle 0.3.0 yayımlansa da 0.2.1'in **Latest** etiketi görünmeye devam edebilir. 0.3.0 kendi Release sayfasından indirilir.
- `main` ve geliştirme dalındaki sürüm numaralarını bu işlem birleştirmez.

## Kullanıcıya verilecek dosya

Releases → Assets → `LiteraturKayit-<sürüm>.zip`. GitHub'ın otomatik oluşturduğu **Source code** arşivleri kurulum paketi değildir. ZIP'in tamamı çıkarılmalı; `Kurulum.exe` ve `payload` birlikte kalmalıdır.

[GitHub etiket tetikleyicileri](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow) · [GitHub CLI yayın komutu](https://cli.github.com/manual/gh_release_create)

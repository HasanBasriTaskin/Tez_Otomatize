# Başlık-özet eleme kararlarının programa aktarılması (hazırlık, 0.8.0 için)

Durum: hazırlık. `literature/screening.py` karar dosyasını okuyor, denetliyor, PRISMA sayılarını çıkarıyor ve Zotero için
yapılacakları kuru çalıştırma olarak listeliyor. Zotero'ya yazma, Yönetim ekranı düğmeleri ve Excel/PRISMA çıktısı
henüz eklenmedi.

## Girdi
`<proje>/03_Calisma/Eleme/eleme_kararlari.json` (sema 1)

| Alan | Anlamı |
|---|---|
| `onay` | `{onaylandi, onaylayan, tarih}`. Kullanıcı onaylamadan Zotero'ya not yazılmaz. |
| `koleksiyonlar` | Geçti → 02_BaslikOzet_Gecen, Hariç → 05_Haric_BaslikOzet. Özeti okunmayanlar 01_Aday'da kalır. |
| `gerekce_metinleri` | H1, H2, H5, H6 için kısa gerekçe metinleri. |
| `kayitlar[]` | 01_Aday'daki her kayıt için bir satır (alanlar aşağıda). |

Kayıt alanları: `key`, `baslik`, `doi`, `tur`, `yil`, `aramalar`, `asama` (Başlık-özet), `bakilan` (Başlık/Özet),
`durum` (Hariç / Geçti / Özet okunmadı), `gerekce_kodu`, `gerekce`, `kanit_alinti`, `arama_konusu`, `okuma_sirasi`,
`AS`, `tam_metin` (Seçildi / Yedek), `secim_gerekcesi`, `erisim_on_kontrol`, `notlar`.

## Denetimler (`screening.check`)
- Her 01_Aday anahtarı için tek karar var; dosyada 01_Aday dışı anahtar yok.
- Başlıklar Zotero kaydıyla birebir aynı.
- Hariç: gerekçe kodu H1/H2/H5/H6 (H3 ve H4 tam metin aşamasına ait); kanıt alıntısı dolu. Başlıktan elenen
  kayıtlarda alıntı başlığın içinde geçiyor.
- Geçti: gerekçe kodu yok; tam metin durumu Seçildi ya da Yedek.
- Özet okunmadı: hiçbir karar izi yok.

## Zotero'ya yazma (sonraki adım; yalnız onaydan sonra)
- Hariç → 05_Haric_BaslikOzet koleksiyonuna eklenir, gerekçe kodu etiketi (H5 vb.) ve hariç notu eklenir. Not
  şablonundaki satırlar: Aşama, Gerekçe kodu, Gerekçe, Kanıt, Karar veren, Karar tarihi. "Karar veren" ve "Karar
  tarihi" alanları `onay` bilgisinden doldurulur.
- Geçti → 02_BaslikOzet_Gecen koleksiyonuna eklenir; `TamMetin-Secildi` ya da `TamMetin-Yedek` etiketi alır.
- Özet okunmadı → değişiklik yapılmaz.
- Kayıtlar 01_Aday'dan çıkarılmaz, böylece tanımlama sayısı korunur. İşlem ledger'a yazılır ve yeniden
  çalıştırıldığında aynı adımlar tekrarlanmaz.
- Seçilen 80 kayıttan erişimi "Kontrol edilecek" olanlar 06_Erisim_Kontrol koleksiyonuna da eklenir.

## Çıktılar (sonraki adım)
- Excel'in Hariç sayfasına yalnız tam metin aşamasında hariç tutulanlar yazılır (kılavuz, Teslim Paketi). Başlık-özet
  aşamasında elenenler bu sayfaya girmez; Zotero'da ve PRISMA kutusunda sayılır.
- PRISMA: başlığı incelenen, özeti incelenen, başlık-özet aşamasında hariç (kod dağılımıyla), geçen, özeti okunmayan
  ve tam metin için seçilen sayıları. `screening.counts` her kutunun bir öncekinden aritmetik olarak çıkarılabilmesini
  sağlar (hariç + geçen + özeti okunmayan = aday).
- Çalışma Excel'i (Eleme_Calisma.xlsx) karar dosyasından yeniden üretilebilir. Sayfalar: Ozet, TamMetin_80, Yedek,
  Haric_BaslikOzet, Ozet_Okunmadi, Olcutler.

## Aynı sürümde yapılacak küçük düzeltme
- "DOI tekrar adayı" sayımından birleştirilmiş (unavailable) öğeler çıkarılacak.

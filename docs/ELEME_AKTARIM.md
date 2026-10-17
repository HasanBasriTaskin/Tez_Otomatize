# Başlık-özet eleme kararlarının programa aktarılması (0.8.0)

Kullanım adımları: [KILAVUZ.md → Başlık-özet elemesini Zotero'ya işleme](KILAVUZ.md#başlık-özet-elemesini-zoteroya-işleme-080).
Plan ve kararlar: [PLAN_0.8.0_ELEME.md](PLAN_0.8.0_ELEME.md).

## Girdi
`<proje>/03_Calisma/Eleme/eleme_kararlari.json` (sema 1)

| Alan | Anlamı |
|---|---|
| `onay` | `{onaylandi, onaylayan, tarih, ozet}`. Yönetim ekranındaki onayla yazılır. `ozet`, kararların SHA-256 özetidir; kararlar onaydan sonra değişirse onay geçersiz olur. |
| `koleksiyonlar` | Bilgi amaçlı. Program hedefleri koleksiyon eşleştirmesinden (title_abstract, excluded_title) alır ve adlarını doğrular. |
| `gerekce_metinleri` | H1, H2, H5, H6 için kısa gerekçe metinleri. |
| `kayitlar[]` | 01_Aday'daki her kayıt için bir satır. |

Kayıt alanları: `no`, `key`, `baslik`, `doi`, `tur`, `yil`, `aramalar`, `asama` (Başlık-özet), `bakilan` (Başlık/Özet),
`durum` (Hariç / Geçti / Özet okunmadı / Taranmadı), `kapsam` (sınırlı taramada kaydın grubu), `gerekce_kodu`, `gerekce`, `kanit_alinti`, `arama_konusu`, `AS`,
`tam_metin` (Seçildi / Yedek), `secim_gerekcesi`, `erisim_on_kontrol`, `notlar`.
Onay özeti şu alanlardan hesaplanır: `key`, `baslik`, `durum`, `bakilan`, `gerekce_kodu`, `gerekce`, `kanit_alinti`,
`tam_metin`, `erisim_on_kontrol`, `kapsam` (notlar ve seçim gerekçesi değişince onay düşmez).

## Denetimler (`screening.check`)
- Her 01_Aday anahtarı için tek karar var; dosyada 01_Aday dışı anahtar yok.
- Başlıklar Zotero kaydıyla birebir aynı.
- Hariç: gerekçe kodu H1/H2/H5/H6 (H3 ve H4 tam metin aşamasına ait); kanıt alıntısı dolu. Başlıktan elenen
  kayıtlarda alıntı başlığın içinde geçiyor.
- Geçti: gerekçe kodu yok; tam metin durumu Seçildi ya da Yedek.
- Özet okunmadı: hiçbir karar izi yok.
- Taranmadı (tarama bir örneklemle sınırlandığında kapsam dışı kalan kayıt): karar alanları boş; Zotero'da değişiklik
  yapılmaz, PRISMA'da "taranmayan kayıt" kutusunda sayılır.

## Zotero'ya yazma (`ZoteroWriter.apply_screening`, yalnız onaydan sonra)
| Karar | Koleksiyon (eklenir) | Etiket | Alt not |
|---|---|---|---|
| Hariç | 05_Haric_BaslikOzet | H kodu | hariç notu |
| Geçti, Seçildi | 02_BaslikOzet_Gecen | TamMetin-Secildi | — |
| Geçti, Yedek | 02_BaslikOzet_Gecen | TamMetin-Yedek | — |
| Seçildi ve erişim "Kontrol edilecek…" | ayrıca 06_Erisim_Kontrol | — | — |

- Yazmadan önce kütüphane okunur ve denetim 01_Aday'ın o anki hâline karşı yeniden yapılır; sorun varsa hiçbir şey yazılmaz.
- Koleksiyon ve etiketler birleşimle eklenir (`If-Unmodified-Since-Version`, 412'de yeniden okunur); eksik bir şey
  yoksa istek gönderilmez. Kayıtlar 01_Aday'da kalır.
- Hariç notu, programın hariç şablonunun alan adlarıyla yazılır (not okuyucusu tanır):
  `Karar`, `Aşama: Başlık-özet`, `Gerekçe kodu`, `Açıklama` (+ `Kanıt (başlık|özet): "…"` satırı), `Karar veren`, `Karar tarihi`.
- Notun anahtarı gönderilmeden önce veritabanına yazılır (`zotero_import_objects`, kimlik `screening-note:<öğe>`);
  yanıt kaybolsa da yeniden çalıştırmada aynı not bulunur. Aynı içerikli not Zotero'da zaten varsa yenisi yazılmaz.
- Öğe başına sonuç `screening_applications` tablosunda (uygulandı / hata).

## Çıktılar
- PRISMA (teslim kontrolü): başlığı/özeti incelenen ve hariç tutulan (karar dosyasından), başlık-özet hariç kodları,
  geçen, tam metin bekleyen seçilmiş ve yedek (Zotero etiketlerinden). Onaylı dosya ile Zotero tutmazsa uyarı.
- `05_Teslim/<takım>_O2_PRISMA.pdf`: PRISMA 2020 akış şeması; tam metinde H3 "erişilemeyen" kutusunda.
- `03_Calisma/Eleme/Eleme_Calisma.xlsx`: Ozet, TamMetin_<n>, Yedek, Haric_BaslikOzet, (Ozet_Okunmadi), Olcutler.
  Programın son yazdığı dosya değilse ya da Excel'de açıksa `_v02…` olarak ayrı yazılır.
- Matris Excel'inin Hariç sayfası değişmez: yalnız tam metinde hariç tutulanlar (kılavuz, Teslim Paketi).

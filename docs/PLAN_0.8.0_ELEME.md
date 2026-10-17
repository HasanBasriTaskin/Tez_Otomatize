# 0.8.0 planı — Başlık-özet elemesini Zotero'ya uygulama ve paketleme

Dal: `feature/eleme-uygulama` (taban: `feature/baslik-ozet-eleme`, 083c9dd). Tarih: 17.10.2026.

## Amaç
`03_Calisma/Eleme/eleme_kararlari.json` dosyasındaki 2.888 başlık-özet kararını kullanıcı onayından sonra TEZ grubuna
(groups/6718452) işlemek; PRISMA sayılarını ve teslim kontrolünü bu aşamaya göre güncellemek; eleme çalışma Excel'ini
program içinden üretmek.

Girdi (bugünkü dosya): 2.888 kayıt → başlıktan hariç 706, özetten hariç 556, geçen 1.626 (tam metin için seçilen 85,
yedek 1.541). `screening.check` 0 sorun.

## Değişmez kurallar
1. Kullanıcı onayı yoksa Zotero'ya **hiçbir şey** yazılmaz (koleksiyon, etiket, not). Onaysız yalnız denetim ve kuru
   çalıştırma.
2. Onay, karar dosyasının o anki içeriğine bağlanır (özet değeri). Onaydan sonra dosya değişirse onay geçersiz olur,
   yeniden onay gerekir.
3. "Karar veren" ve "Karar tarihi" yalnız onaydan doldurulur (onaylayan = Ayarlar'daki "Kaydı yapan kişi").
4. Zotero notlarına, etiketlere ve Excel'e karar içeriği dışında bir şey yazılmaz (araç, yöntem, otomatik işlem
   açıklaması yok).
5. Kayıtlar 01_Aday'dan çıkarılmaz, hiçbir Zotero öğesi silinmez veya üzerine yazılmaz; yalnız koleksiyon/etiket
   **eklenir** ve yeni alt not oluşturulur.
6. Yarıda kalan iş yeniden başlatılınca kaldığı yerden devam eder; ikinci çalıştırma ikinci not ya da tekrar etiket
   üretmez.
7. Sürüm numarası (0.8.0) en son, kullanıcı kabulünden sonra yükseltilir. (Dala sürüm değişikliğiyle push yapılınca
   GitHub Release kendiliğinden yayımlanıyor; o zamana kadar push'lar yalnız test ve paket üretir.)

## Zotero'da yapılacaklar (onaydan sonra)
| Karar | Koleksiyon (eklenir) | Etiket | Alt not |
|---|---|---|---|
| Hariç (başlık / özet) | 05_Haric_BaslikOzet | H1 / H2 / H5 / H6 | Hariç notu (aşağıda) |
| Geçti, Seçildi | 02_BaslikOzet_Gecen | TamMetin-Secildi | yok |
| Geçti, Yedek | 02_BaslikOzet_Gecen | TamMetin-Yedek | yok |
| Seçildi + erişim "Kontrol edilecek" | ayrıca 06_Erisim_Kontrol | — | yok |

Hariç notu, programın mevcut hariç şablonundaki alan adlarıyla yazılır (not okuyucusu bunları tanır; "Gerekçe" ve
"Kanıt" gibi tanınmayan alan adı kullanılmaz):
```
Karar: Hariç
Aşama: Başlık-özet
Gerekçe kodu: H5
Açıklama: Bağlam uyuşmuyor: metin tabanlı belge soru-cevabı dışı ya da tezin temalarıyla ilgisiz.
Kanıt (özet): "…birebir alıntı…"
Karar veren: Hasan Basri Taşkın
Karar tarihi: 17.10.2026
```
Sayılar: 1.262 not, 2.888 koleksiyon/etiket güncellemesi, 54 kayıt 06_Erisim_Kontrol'e (48 "Kontrol edilecek" + 6 DOI'siz).

## İş adımları (her biri ayrı commit, önce test)

### A. Karar dosyası ve onay (`literature/screening.py`)
- `digest(data)`: kayıtların sıralı JSON özeti (SHA-256). `approved()` onaylandi + onaylayan + tarih **ve** özet eşleşmesi ister.
- `approve(path, operator, today)`: önce `check` temiz olmalı; eski dosyayı `Yedekler/`e kopyalar; `onay`
  alanını {onaylandi, onaylayan, tarih, ozet} ile atomik yazar. Kararları değiştirmez.
- `note()` hariç şablonunun alanlarıyla (yukarıdaki biçim); `parse_note` ile geri okunduğunda bilinmeyen alan vermediği test edilir.
- `plan()`: koleksiyon anahtarları rol eşleştirmesinden (title_abstract VHIBG6RK, excluded_title RR4X8Y8B);
  06_Erisim_Kontrol için ayrı işaret; özet sayılar (kaç not, kaç etiket, kaç koleksiyon).
- Testler: onaysız/özeti tutmayan onay → yazma planında not yok; onay sonrası dosya değişince onay düşer; not geri okunuyor.

### B. Zotero'ya yazma (`literature/zotero_writer.py` → `apply_screening`)
- Önkontrol: yazma izni, TEZ hedefi, 01_Aday/02/05 koleksiyonları adlarıyla doğrulanır. 06_Erisim_Kontrol yoksa kökte
  oluşturulur (ledger'la; ikinci kez oluşturulmaz).
- Kütüphane bir kez okunur; 01_Aday üyeleri `{anahtar: başlık}` → `screening.check` yeniden çalışır. Sorun varsa hiçbir şey yazılmaz.
- Her öğe: hemen önce okunur, koleksiyon ve etiketler **birleşimle** PATCH edilir (`If-Unmodified-Since-Version`,
  412'de 3 deneme). Zaten varsa istek atılmaz.
- Notlar: kimlik `screening-note:<öğe anahtarı>`; anahtar önce veritabanına yazılır, sonra 50'şerlik gruplarla POST.
  Uzlaştırma, Zotero'nun HTML'i değiştirmesine karşı düz metin + `parentItem` karşılaştırmasıyla yapılır. Aynı öğede
  aynı içerikli not zaten varsa yeni not yazılmaz.
- Sonuç tablosu `screening_applications` (anahtar, durum, hata, zaman); ilerleme satırları; iptal.
- Testler (sahte yerel API ile): tam uygulama; ikinci çalıştırmada yeni istek/not yok; yanıt kaybından sonra
  yeniden çalıştırma tek not bırakır; eşzamanlı değişiklikte kullanıcının koleksiyon/etiketi korunur; onaysız ve
  `check` sorunlu dosyada ağ isteği yok; silinmiş öğe yeniden oluşturulmaz; izin reddi kalıcı hata olarak kaydedilir.

### C. Uygulama komutları ve yönetim ekranı
- Komutlar: `screening_status` (dosya yolu, sorunlar, sayılar, onay durumu, son uygulama), `screening_approve`
  (onay kutusu işaretli olmalı), `screening_apply` (arka plan işi; bitince "Zotero'dan oku" kendiliğinden çalışır ve
  Excel güncellenir), `screening_workbook`.
- Zotero bölümüne "Başlık-özet eleme" paneli: sayılar ve sorunlar → "Kararları kontrol ettim, onaylıyorum" kutusu +
  "Onayla" → "Zotero'ya uygula" (onay ve temiz denetim yoksa pasif) → ilerleme.
- Eklenti testleri (sentetik DOM): düğme durumları, onaysız uygulamanın engellenmesi.

### D. PRISMA ve teslim kontrolü (`literature/exports.py`)
- PRISMA'ya başlık-özet kutuları: başlığı incelenen, başlıktan hariç, özeti incelenen, özetten hariç (kod dağılımıyla),
  geçen, tam metin için seçilen, yedek (tam metni değerlendirilmeyen). Sayılar Zotero durumlarından + etiketlerden;
  karar dosyasıyla tutmazsa uyarı.
- "Karar bekleyen" uyarısı yedekleri saymaz (yedekler ayrı kutu). Seçilip tam metin kararı almamış olanlar sayılır.
- DOI tekrar adayı sayımından erişilemez (birleştirilmiş) öğeler çıkarılır (0.7.x'teki yanlış uyarı).
- LiteraturMatrisi Hariç sayfası değişmez: yalnız tam metinde hariç tutulanlar (kılavuz).
- İsteğe bağlı: `05_Teslim/OEC-1017_O2_PRISMA.pdf` akış şeması (Tarama Raporu'na eklenmek üzere).

### E. Eleme çalışma Excel'i
- `03_Calisma/Eleme/Eleme_Calisma.xlsx` karar dosyasından üretilir (Ozet, TamMetin_85, Yedek, Haric_BaslikOzet,
  Olcutler). Açık dosyanın üzerine yazılmaz; `_v02` sürümü yazılır. "Özeti okunmayan" 0 ise o sayfa çıkmaz.

### F. Belgeler ve sürüm
- `docs/ELEME_AKTARIM.md` (hazırlık → kullanım), `docs/KILAVUZ.md` (adım adım), README kısa paragraf,
  `docs/releases/v0.8.0.md`, `docs/MANUEL_TEST.md` kabul adımları.
- Kullanıcı kabulünden sonra: package.json, package-lock.json, literature/__init__.py → 0.8.0; push → CI → Release.

## Kabul testi (kullanıcı, Windows)
1. Önce **Deneme** projesinde ve Deneme Zotero koleksiyonlarıyla küçük bir karar dosyası (5–10 kayıt) uygulanır.
2. Asıl projede: proje yedeği + Zotero yedeği (zotero.sqlite kopyası) → Denetle → Onayla → Uygula.
3. Kontrol: 05_Haric_BaslikOzet 1.262, 02_BaslikOzet_Gecen 1.626, 06_Erisim_Kontrol 54; rastgele 10 notun içeriği;
   "Zotero'dan oku" sonrası teslim kontrolündeki PRISMA sayıları karar dosyasıyla aynı.

## Kullanıcının karar vereceği noktalar (varsayılan önerilerle)
1. Onay yöntemi: yönetim ekranında onay kutusu + düğme (öneri) / JSON'u elle düzenleme.
2. Geçen 1.626 kayda kısa not yazılsın mı: **hayır** (öneri; notlar Eleme_Calisma.xlsx'te kalır).
3. 06_Erisim_Kontrol koleksiyonu oluşturulsun mu: **evet** (öneri).
4. PRISMA PDF şeması: **evet** (öneri; rapora görsel olarak eklenir).

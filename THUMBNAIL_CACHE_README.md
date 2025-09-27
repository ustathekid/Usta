# PDF Thumbnail Cache System - Index-Only Generation

## Genel Bakış

Bu sistem, PDF dosyaları için küçük resim (thumbnail) oluşturma ve önbellekleme işlemlerini **sadece indeks alımında** gerçekleştirir. Functional group klasörleri altında **her PDF dosyası için ayrı thumbnail** saklanır.

## Yeni Özellikler (Sadece İndeks Alımında Oluşturma)

### 1. Sadece İndeks Alımında Thumbnail Oluşturma
- **Otomatik Oluşturma İptal**: Aramalarda arka planda thumbnail oluşturulmaz
- **İndeks Tabanlı**: Sadece manuel/otomatik indeks güncellemelerinde oluşturulur
- **Performans**: Arama sırasında hiç gecikme yok
- **Kontrollü Oluşturma**: Thumbnail oluşturma zamanı kontrol edilebilir

### 2. Functional Group Bazlı Klasör Yapısı
- **Ana Klasör**: `thumbnails/` 
- **Alt Klasörler**: Her functional group (10, 11, 76, 85, vb.) için ayrı klasör
- **Tüm PDF'ler**: Her PDF dosyası için ayrı thumbnail (sayfa numaraları dahil)
- **Tam Kapsama**: Hiçbir PDF atlanmaz

### 3. Kapsamlı Thumbnail Sistemi
- **Her PDF için Thumbnail**: `9.MW276.20.0_1.pdf` → `9.MW276.20.0_1_w220.png`
- **Sayfa Numaraları**: `_1`, `_2` gibi sayfalar da ayrı thumbnail alır
- **Dosya Adı Korunması**: Orijinal PDF adı thumbnail adında saklanır

## Özellikler

### 1. Thumbnail Önbellek Sistemi
- **Klasör**: `thumbnails/` klasöründe tüm thumbnaillar saklanır
- **Format**: PNG formatında kaydedilir
- **Boyut**: Varsayılan 220px genişlik, özelleştirilebilir (50-500px arası)
- **Adlandırma**: `{relative_path}_w{width}.png` formatında

### 2. Otomatik Cache Kontrolü
- **Geçerlilik Kontrolü**: Thumbnail'ın PDF'den daha yeni olup olmadığı kontrol edilir
- **Otomatik Yenileme**: PDF güncellendiğinde thumbnail otomatik yenilenir
- **Performans**: Cache varsa direkt dosyadan servis edilir, yoksa oluşturulur

### 3. Functional Groups Entegrasyonu
- **Arka Plan İşleme**: Arama sonuçları döndürüldükten sonra thumbnaillar arka planda oluşturulur
- **Component Search**: 2.3199.115.0 formatındaki aramalar sonrasında otomatik thumbnail oluşturma
- **Group Code Search**: 9.x formatındaki aramalar sonrasında otomatik thumbnail oluşturma

### 4. İndeks Güncelleme Entegrasyonu
- **Otomatik Temizlik**: İndeks güncellendiğinde eski thumbnaillar temizlenir
- **Yeniden Oluşturma**: Sonraki aramalarda thumbnaillar yeniden oluşturulur

## API Endpoints

### `/api/pdf-thumbnail`
PDF thumbnail'ı oluşturur ve servis eder.

**Parametreler:**
- `f`: PDF dosyası token'ı (zorunlu)
- `w`: Thumbnail genişliği (opsiyonel, varsayılan: 200px)

**Örnekler:**
```
/api/pdf-thumbnail?f=<token>&w=220
/api/pdf-thumbnail?f=<token>
```

### `/api/thumbnail-cache-stats` (YENİ)
Thumbnail cache istatistiklerini getirir.

**Response:**
```json
{
  "success": true,
  "stats": {
    "total_groups": 3,
    "total_thumbnails": 12,
    "total_size_mb": 2.5,
    "groups": {
      "9.GR789.00.0": {
        "thumbnails": 4,
        "size_bytes": 102400
      }
    }
  }
}
```

### `/api/clear-thumbnail-cache` (YENİ)
Thumbnail cache'ini temizler.

**Method:** POST  
**Body:**
```json
{
  "functional_groups": ["10", "11", "76"],    // Functional group bazlı temizleme
  "group_codes": ["9.GR789.00.0"]           // 9.x kod bazlı temizleme (opsiyonel)
}
```

**Örnekler:**
- Belirli functional groups temizle: `{"functional_groups": ["10", "76"]}`
- Belirli 9.x kodları temizle: `{"group_codes": ["9.GR789.00.0"]}`
- Tümünü temizle: `{}` (boş body)

## Cache Fonksiyonları

### Temel Fonksiyonlar
- **`_get_functional_group_from_nine_code(nine_code)`**: 9.x kodundan functional group numarası bulur
- **`_get_thumbnail_cache_path(pdf_path, width)`**: Functional group bazlı cache dosya yolunu oluşturur
- **`_is_thumbnail_cache_valid(cache_path, pdf_path)`**: Cache'in geçerli olup olmadığını kontrol eder
- **`_generate_and_cache_thumbnail(pdf_path, width)`**: Thumbnail oluşturur ve cache'e kaydeder
- **`_get_cached_thumbnail(pdf_path, width)`**: Cache'den thumbnail getirir veya yeni oluşturur

### Functional Group Yönetim Fonksiyonları
- **`_update_thumbnails_for_group_codes(group_codes)`**: Belirtilen 9.x kodları için thumbnailları arka planda oluşturur
- **`_clear_thumbnails_for_functional_groups(functional_groups)`**: Belirli functional grouplar için cache'i temizler
- **`_clear_thumbnails_for_group_codes(group_codes)`**: Belirli 9.x kodları için cache'i temizler (functional group üzerinden)
- **`_get_thumbnail_cache_stats()`**: Cache istatistiklerini getirir (functional group bazlı)

## Performans Avantajları

1. **Hızlı Yükleme**: Cache'deki thumbnaillar anında yüklenir
2. **Sunucu Yükü Azalması**: Tekrar eden isteklerde PDF işleme yapılmaz
3. **Arka Plan İşleme**: Kullanıcı deneyimi kesintisiz devam eder
4. **Otomatik Güncelleme**: PDF değiştiğinde cache otomatik güncellenir

## Klasör Yapısı

Thumbnaillar functional group kodlarına göre organize edilir ve **her PDF için ayrı thumbnail** saklanır:

```
thumbnails/
├── 10/
│   ├── 9.GR123.00.0_w220.png         # Ana PDF
│   ├── 9.GR123.00.0_1_w220.png       # Sayfa 1
│   └── 9.AB456.00.0_w220.png         # Başka bir 9.x kodu
├── 76/
│   ├── 9.MW276.20.0_1_w220.png       # Sayfa 1
│   ├── 9.MW276.20.0_2_w220.png       # Sayfa 2
│   ├── 9.MW676.20.0_w220.png         # Ana PDF
│   └── 9.MW676.20.0_1_w220.png       # Sayfa 1
├── 85/
│   ├── 9.GR685.20.0_w220.png
│   ├── 9.MW285.05.0_w220.png
│   └── 9.MW285.10.0_w220.png
└── 9.UNKNOWN.00.0/
    └── 9.UNKNOWN.00.0_w220.png       # Functional group bulunamayan
```

### Avantajları:
- **Tam Kapsama**: Her PDF dosyası için thumbnail (sayfa numaraları dahil)
- **Functional Group Organizasyonu**: 10, 11, 76 gibi gruplar kendi klasörlerinde
- **Kontrollü Oluşturma**: Sadece indeks alımında, otomatik değil
- **Performans**: Arama sırasında gecikme yok
- **Depolama Verimliliği**: Sadece ihtiyaç olduğunda oluşturulur

## Bakım ve Yönetim

### Cache Temizleme
İndeks güncellendiğinde thumbnaillar otomatik temizlenir. Manuel temizlik için:
```python
# thumbnails/ klasörünü silin veya içeriğini boşaltın
```

### Disk Alanı
Thumbnail dosyaları yaklaşık 10-50KB boyutundadır. Büyük veri setleri için disk alanını izleyin.

### Hata Durumları
- PyMuPDF yüklü değilse sistem graceful failover yapar
- Cache oluşturulamazsa direct generation'a geçer
- Dosya izinleri sorunlarında hata loglanır

## Gelecek Geliştirmeler

1. **Boyut Optimizasyonu**: Farklı kalite seçenekleri
2. **Cache Limiti**: Maksimum cache boyutu kontrolü
3. **İstatistikler**: Cache hit/miss oranları
4. **Batch İşleme**: Toplu thumbnail oluşturma
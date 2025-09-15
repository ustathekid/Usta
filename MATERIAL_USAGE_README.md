# Material Usage Analysis - Kullanım Kılavuzu

## Genel Bakış

Material Usage Analysis (Malzeme Kullanım Analizi) modülü, parça kodlarını analiz ederek bunların üretim hiyerarşisindeki yerini izler ve hangi departmanlarda kullanıldığını belirler.

## Hiyerarşi Yapısı

Sistem aşağıdaki hiyerarşik yapıyı takip eder:

```
Parça Kodu → 9 Haneli Grup Kodu → Model → MGroup → Workcenter → Departman → MIX Kodu
```

### Örnek Hiyerarşi:
- **Parça Kodu**: 2.3199.115.0
- **9 Haneli Grup Kodu**: 9.5430.234.1
- **Model**: Hidrolik model
- **MGroup**: 102B0001
- **Workcenter**: MTC004
- **Departman**: Second Line
- **MIX Kodu**: MIX00001

## Ana Özellikler

### 1. Parça Analizi
- **Çoklu Parça Girişi**: Birden fazla parça kodunu aynı anda analiz edebilir
- **Otomatik Arama**: partcodes klasöründeki JSON dosyalarında parça kodlarını arar
- **Hiyerarşi İzleme**: Her parça için tam hiyerarşi yolunu belirler

### 2. Departman Analizi
- **Departman Özeti**: Hangi departmanların etkilendiğini gösterir
- **Workcenter Dağılımı**: Parçaların hangi workcenterler'da kullanıldığını listeler
- **MGroup Analizi**: MGroup seviyesinde detaylı analiz sağlar

### 3. Raporlama
- **Gerçek Zamanlı İlerleme**: Analiz sürecini canlı takip
- **Detaylı Loglar**: Her adımın kaydını tutar
- **Export İşlevi**: Sonuçları JSON formatında dışa aktarır

## Kullanım

### 1. Parça Kodları Girişi
- Material Usage sayfasına gidin
- "Part Code Input" alanına parça kodlarını girin (her satırda bir kod)
- Excel'den kopyala-yapıştır desteklenir

### 2. Analiz Başlatma
- "Start Analysis" butonuna tıklayın
- İlerleme çubuğundan durumu takip edin
- Log alanından detayları izleyin

### 3. Sonuçları İnceleme
- **Results** sekmesinde özet bilgileri görün
- **Hierarchy** sekmesinde detaylı hiyerarşi bilgilerini inceleyin
- Bulunan/bulunamayan parçaların istatistiklerini kontrol edin

## Teknik Detaylar

### Veri Kaynakları
1. **partcodes klasörü**: JSON formatındaki parça veritabanı
2. **mgroups.json**: MGroup-Workcenter-Departman eşleştirmeleri
3. **mix.json**: Model-MIX kodu ilişkileri

### Arama Algoritması
1. Parça kodu partcodes JSON dosyalarında aranır
2. Eşleşen 9 haneli grup kodları bulunur
3. Model bilgileri çıkarılır
4. MGroup ve workcenter bilgileri mgroups.json'dan alınır
5. Departman bilgileri workcenter'dan çıkarılır
6. MIX kodları mix.json'dan eşleştirilir

### Performans Optimizasyonları
- **Paralel İşleme**: Birden fazla parça aynı anda işlenir
- **Önbellek Kullanımı**: Sık kullanılan veriler bellekte tutulur
- **İnkremental Loglar**: Büyük analizlerde bellek tasarrufu

## Hata Durumları

### Yaygın Problemler
1. **Parça Bulunamadı**: Parça kodu veritabanında yok
2. **Eksik Hiyerarşi**: MGroup veya Workcenter eşleştirmesi bulunamadı
3. **Model Eşleştirmesi**: MIX kodu bulunamadı

### Sorun Giderme
- partcodes klasörünün dolu olduğundan emin olun
- mgroups.json dosyasının güncel olduğunu kontrol edin
- mix.json dosyasındaki hiyerarşik yapının doğruluğunu teyit edin

## API Endpoints

### Analiz İşlemleri
- `POST /api/material_usage/analyze` - Analiz başlat
- `GET /api/material_usage/progress` - İlerleme durumu
- `GET /api/material_usage/results` - Analiz sonuçları
- `POST /api/material_usage/cancel` - Analizi iptal et

### Raporlama
- `GET /api/material_usage/download_log` - Log dosyası indir
- `GET /api/material_usage/export` - Sonuçları JSON olarak indir

## Güvenlik

- **Kullanıcı Doğrulama**: Tüm işlemler oturum açmış kullanıcılar için
- **Dosya Güvenliği**: Sadece belirtilen dizinlere erişim
- **Log Kaydı**: Tüm işlemler kullanıcı bilgisiyle loglanır

## Konfigürasyon

### Ortam Ayarları
Material Usage modülü mevcut Schemini yapılandırmasını kullanır:
- partcodes klasörü konumu
- mgroups.json dosyası
- mix.json hiyerarşik verileri

### Özelleştirme
Mgroups.json dosyasına yeni utility fonksiyonlar eklenmiştir:
- `get_hierarchy_path(mgroup)` - Tam hiyerarşi yolu
- `export_to_json()` - JSON uyumlu veri
- `validate_data()` - Veri tutarlılığı kontrolü

## Gelecek Özellikler

1. **Excel Import**: Parça listelerini Excel'den import
2. **Görsel Haritalar**: Departman kullanım haritaları
3. **Trend Analizi**: Geçmiş analiz verilerinin karşılaştırması
4. **Otomatik Raporlar**: Zamanlanmış analiz raporları

## Teknik Destek

Herhangi bir sorun durumunda:
1. Log dosyalarını kontrol edin
2. Sistem durumunu Settings sayfasından inceleyin
3. Parça kodu formatının doğru olduğundan emin olun

---

**Not**: Bu modül mgroups.json ve mix.json dosyalarının güncel kalması için düzenli bakım gerektirir.

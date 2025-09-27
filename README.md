# Schemini Manager Web Application

🚀 **Professional File Management System** - Flask Web Edition

## 📋 Proje Açıklaması

Schemini Manager, gelişmiş dosya yönetimi, karşılaştırma, senkronizasyon ve malzeme kullanım analizi işlemleri için tasarlanmış profesyonel bir web uygulamasıdır. CustomTkinter masaüstü uygulamasından Flask web uygulamasına dönüştürülmüştür ve modern web teknolojileri ile güçlendirilmiştir.

## ✨ Özellikler

### 🔍 Dosya Karşılaştırma (File Comparison)
- İki klasör arasında detaylı karşılaştırma
- Eşleşmeyen dosyaların tespit edilmesi
- I-prefix dosya desteği
- Kapsamlı raporlama sistemi

### ⚡ Akıllı Güncelleme (Smart Update)
- Referans klasöründeki dosyaları yeni sürümlerle güncelleme
- Otomatik yedekleme (.backup uzantısı)
- Zaman damgası kontrolü
- Güvenli güncelleme işlemleri

### 📁 Dosya Entegrasyonu (File Integration)
- MIX kod tabanlı dosya ekleme
- Excel dosyalarından MIX kod içe aktarma
- Otomatik klasör organizasyonu
- Toplu dosya işlemleri

### 📊 Malzeme Kullanım Analizi (Material Usage Analysis)
- Parça kod listesi analizi
- Başarı oranı görselliği (kırmızıdan yeşile renk skalası)
- Bulunan ve bulunmayan kodların detaylı raporlaması
- Departman, MIX ve MGroup filtreleme
- ZIP indirme ve otomatik kopyalama özellikleri

### � Fonksiyonel Gruplar (Functional Groups)
- Fonksiyonel grupların yönetimi ve görüntüleme
- PDF'lerin fonksiyonel gruplara göre sınıflandırılması
- Grupların düzenleme ve güncelleme işlemleri
- Otomatik gruplandırma ve filtreleme özellikleri
- Grup bazlı PDF erişimi ve organizasyonu

### �🔧 Otomatik İndeksleme ve Küçük Resim Oluşturma
- Tam ve artımlı indeksleme modları
- Otomatik thumbnail oluşturma ve önbellekleme
- Zamanlanmış indeksleme (günlük iki slot)
- Hızlı arama ve görüntüleme için JSON tabanlı indeksler

### ⚙️ Ayarlar ve Yapılandırma
- Schemini ana klasörü yapılandırması
- Tema ve dil seçenekleri
- Log yönetimi
- Ayarları içe/dışa aktarma
- Sabit ayar yöneticisi (web_settings_manager_fixed.py) kullanımı

## 🛠️ Teknoloji Yığını

- **Backend**: Python Flask
- **Frontend**: Bootstrap 5, HTML5, CSS3, JavaScript, jQuery
- **UI Framework**: Bootstrap Icons
- **Veritabanı**: JSON tabanlı yapılandırma ve indeksler
- **Excel Desteği**: pandas, openpyxl
- **PDF İşleme**: PyMuPDF (fitz), Pillow
- **Görüntü İşleme**: OCR için pytesseract

## 🚀 Kurulum ve Çalıştırma

### Gereksinimler
- Python 3.8+
- Flask, Flask-CORS
- pandas, openpyxl
- PyMuPDF, Pillow, pytesseract (isteğe bağlı)
- Diğer bağımlılıklar için `requirements.txt`

### Kurulum Adımları

1. **Projeyi klonlayın veya indirin**
   ```bash
   git clone <repository-url>
   cd schemini-manager-web
   ```

2. **Sanal ortam oluşturun ve aktifleştirin**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # veya
   source .venv/bin/activate  # Linux/Mac
   ```

3. **Gerekli paketleri yükleyin**
   ```bash
   pip install -r requirements.txt
   ```

4. **Uygulamayı başlatın**
   ```bash
   python app.py
   ```

5. **Web tarayıcısında açın**
   ```
   http://localhost:5001
   ```

## 📱 Kullanım

### İlk Kurulum
1. **Settings** sayfasından Schemini ana klasörünüzü yapılandırın
2. Klasör yolunu seçin ve kaydedin
3. Sistem bilgilerini kontrol edin

### Dosya Karşılaştırma
1. **File Comparison** sayfasına gidin
2. Ana klasör (referans) ve hedef klasörü seçin
3. **Start Comparison** butonuna tıklayın
4. Sonuçları analiz edin ve gerekirse raporları indirin

### Akıllı Güncelleme
1. **Smart Update** sayfasına gidin
2. Referans klasör ve güncelleme klasörünü seçin
3. **Start Update** ile işlemi başlatın
4. Yedekleme dosyalarını kontrol edin

### Dosya Entegrasyonu
1. **File Integration** sayfasına gidin
2. Ana klasör ve ekleme klasörünü seçin
3. **Scan MIX Codes** ile kodları tarayın
4. İstediğiniz kodları seçin ve **Add Files** ile işlemi başlatın

### Malzeme Kullanım Analizi
1. **Material Usage** sayfasına gidin
2. Parça kodlarını girin veya yükleyin
3. Departman, MIX ve MGroup filtrelerini seçin
4. **Start Analysis** ile analizi başlatın
5. Özet (Başarı Oranı) ve Detaylar (Bulunan/Bulunmayan) bölümlerini inceleyin
6. ZIP indirme veya otomatik kopyalama ile sonuçları dışa aktarın

### Fonksiyonel Gruplar
1. **Functional Groups** sayfasına gidin
2. Mevcut fonksiyonel grupları görüntüleyin
3. Grupları düzenleyin veya yeni gruplar ekleyin
4. PDF'leri gruplara göre filtreleyin ve yönetin
5. Grup bazlı raporları inceleyin ve dışa aktarın

## 📊 Özellikler Detayı

### Gerçek Zamanlı İzleme
- Canlı ilerleme çubukları
- Detaylı operasyon logları
- Anlık durum güncellemeleri
- Hata yakalama ve raporlama

### Profesyonel Raporlama
- Detaylı HTML raporları
- İndirilebilir log dosyaları
- Sistem bilgisi entegrasyonu
- Zaman damgalı kayıtlar

### Modern Web Arayüzü
- Responsive tasarım
- Dark tema
- Bootstrap 5 bileşenleri
- Animasyonlu geçişler
- Dinamik renk skalaları ve görseller

### Otomatik İşlemler
- Arka plan görevleri
- Zamanlanmış indeksleme
- Küçük resim önbellekleme
- Sistem kaynak yönetimi

## 🔧 Yapılandırma

### Ana Yapılandırma Dosyası
```json
{
  "schemini_klasoru": "C:/path/to/your/schemini/folder",
  "app_settings": {
    "theme": "dark",
    "language": "en",
    "auto_backup": true,
    "log_level": "info",
    "auto_indexing": {
      "enabled": true,
      "primary_time": "07:55",
      "secondary_time": "15:55"
    }
  }
}
```

### Log Dosyaları
- **Konum**: `logs/` klasörü
- **Format**: `{operation}_{timestamp}.log`
- **İçerik**: Detaylı operasyon raporu ve sistem bilgileri

## 🔒 Güvenlik

- CORS desteği
- Input validasyonu
- Güvenli dosya işlemleri
- Otomatik yedekleme
- Hata yakalama ve loglama
- Kullanıcı kimlik doğrulama

## 📝 API Endpoints

### Klasör İşlemleri
- `POST /api/select-folder` - Klasör seçimi
- `POST /api/scan-folders` - Klasör tarama
- `POST /api/update-files` - Dosya güncelleme
- `POST /api/add-files` - Dosya ekleme

### Malzeme Analizi
- `GET /api/material_usage/departments` - Departman verisi
- `POST /material_usage/analyze_filtered` - Filtrelenmiş analiz
- `GET /material_usage/progress` - İlerleme durumu
- `GET /material_usage/results` - Analiz sonuçları

### Fonksiyonel Gruplar
- `GET /functional-groups` - Fonksiyonel gruplar sayfası
- `GET /api/functional_groups` - Grup verilerini alma
- `POST /api/functional_groups/update` - Grup güncelleme
- `POST /api/functional_groups/add` - Yeni grup ekleme

### İzleme ve Raporlama
- `GET /api/get-progress/{operation}` - İlerleme durumu
- `GET /api/get-logs/{operation}` - Operasyon logları
- `GET /api/download-log/{file}` - Log dosyası indirme

### Sistem ve Ayarlar
- `GET /api/system-info` - Sistem bilgileri
- `GET/POST /api/settings` - Ayarlar yönetimi
- `GET /api/get_app_settings` - Uygulama ayarları

## 🎨 Tema ve Özelleştirme

### CSS Değişkenleri
```css
:root {
    --primary-color: #0d6efd;
    --secondary-color: #6c757d;
    --success-color: #198754;
    --warning-color: #ffc107;
    --danger-color: #dc3545;
    --info-color: #0dcaf0;
}
```

### JavaScript Modülleri
- `ScheminiManager.showNotification()` - Bildirim sistemi
- `ScheminiManager.setLoadingState()` - Yükleme durumu
- `ScheminiManager.startProgressMonitoring()` - İlerleme izleme

## 🐛 Hata Ayıklama

### Debug Modu
```bash
export FLASK_DEBUG=1  # Linux/Mac
set FLASK_DEBUG=1     # Windows
python app.py
```

### Log Seviyeleri
- **DEBUG**: Detaylı hata ayıklama bilgileri
- **INFO**: Genel bilgilendirme mesajları
- **WARNING**: Uyarı mesajları
- **ERROR**: Hata mesajları

## 📞 Destek ve İletişim

- **Geliştirici**: Cafer T. Usta
- **Versiyon**: 1.1.0 Web Edition (Güncel)
- **Lisans**: Professional Edition
- **Tarih**: Eylül 2025

## 🔄 Güncellemeler

### v1.1.0 Web Edition (Güncel)
- ✅ Malzeme Kullanım Analizi eklendi
- ✅ Başarı oranı renk skalası (kırmızı-yeşil)
- ✅ Detaylarda bulunmayan kodların gösterimi
- ✅ Otomatik indeksleme ve thumbnail oluşturma
- ✅ Sabit ayar yöneticisi entegrasyonu
- ✅ Gradient arka planların kaldırılması ve sabit renkler
- ✅ Sistem kaynak yönetimi iyileştirmesi
- ✅ Fonksiyonel Gruplar yönetimi eklendi

### v1.0.0 Web Edition
- ✅ CustomTkinter'dan Flask'a tam dönüşüm
- ✅ Modern web arayüzü
- ✅ Gerçek zamanlı ilerleme izleme
- ✅ Bootstrap 5 entegrasyonu
- ✅ CORS desteği
- ✅ Responsive tasarım

### Gelecek Özellikler
- 🔄 Light tema desteği
- 🔄 Çoklu dil desteği
- 🔄 REST API genişletmesi
- 🔄 Docker konteynerizasyonu
- 🔄 Veritabanı entegrasyonu
- 🔄 Gelişmiş arama ve filtreleme

## 📁 Proje Yapısı

```
schemini-manager-web/
│
├── app.py                          # Ana Flask uygulaması
├── web_base_manager.py             # Temel manager sınıfı
├── web_scan_manager.py             # Tarama işlemleri
├── web_update_manager.py           # Güncelleme işlemleri
├── web_file_add_manager.py         # Dosya ekleme işlemleri
├── web_settings_manager_fixed.py   # Sabit ayar yöneticisi
├── web_material_usage_manager.py   # Malzeme kullanım analizi
├── system_resource_manager.py      # Sistem kaynak yönetimi
├── schemini_config.json            # Yapılandırma dosyası
│
├── templates/                      # HTML şablonları
│   ├── base.html
│   ├── index.html
│   ├── material_usage.html
│   ├── functional_groups.html
│   ├── scan.html
│   ├── update.html
│   ├── file_add.html
│   ├── settings.html
│   └── error.html
│
├── static/                        # Statik dosyalar
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
│
├── databases/                     # JSON indeks ve yapılandırma
│   ├── mix.json
│   ├── mgroups.json
│   ├── functional_groups.json
│   └── schemini_config.json
│
├── logs/                          # Log dosyaları
│   └── *.log
│
└── __pycache__/                   # Python önbellek
```

---

**🎯 Schemini Manager Web - Profesyonel Dosya Yönetimi ve Analiz Çözümü**

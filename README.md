# Schemini Manager Web Application

🚀 **Professional File Management System** - Flask Web Edition

## 📋 Proje Açıklaması

Schemini Manager, gelişmiş dosya yönetimi, karşılaştırma ve senkronizasyon işlemleri için tasarlanmış profesyonel bir web uygulamasıdır. CustomTkinter masaüstü uygulamasından Flask web uygulamasına dönüştürülmüştür.

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

### ⚙️ Ayarlar ve Yapılandırma
- Schemini ana klasörü yapılandırması
- Tema ve dil seçenekleri
- Log yönetimi
- Ayarları içe/dışa aktarma

## 🛠️ Teknoloji Yığını

- **Backend**: Python Flask
- **Frontend**: Bootstrap 5, HTML5, CSS3, JavaScript
- **UI Framework**: Bootstrap Icons
- **Veritabanı**: JSON tabanlı yapılandırma
- **Excel Desteği**: pandas, openpyxl

## 🚀 Kurulum ve Çalıştırma

### Gereksinimler
- Python 3.8+
- Flask
- Flask-CORS
- pandas (Excel desteği için)
- openpyxl (Excel dosyaları için)

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
   pip install flask flask-cors pandas openpyxl werkzeug jinja2
   ```

4. **Uygulamayı başlatın**
   ```bash
   python app.py
   ```

5. **Web tarayıcısında açın**
   ```
   http://localhost:5000
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

## 🔧 Yapılandırma

### Ana Yapılandırma Dosyası
```json
{
  "schemini_klasoru": "C:/path/to/your/schemini/folder",
  "app_settings": {
    "theme": "dark",
    "language": "en",
    "auto_backup": true,
    "log_level": "info"
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

## 📝 API Endpoints

### Klasör İşlemleri
- `POST /api/select-folder` - Klasör seçimi
- `POST /api/scan-folders` - Klasör tarama
- `POST /api/update-files` - Dosya güncelleme
- `POST /api/add-files` - Dosya ekleme

### İzleme ve Raporlama
- `GET /api/get-progress/{operation}` - İlerleme durumu
- `GET /api/get-logs/{operation}` - Operasyon logları
- `GET /api/download-log/{file}` - Log dosyası indirme

### Sistem ve Ayarlar
- `GET /api/system-info` - Sistem bilgileri
- `GET/POST /api/settings` - Ayarlar yönetimi

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
- **Versiyon**: 1.0.0 Web Edition
- **Lisans**: Professional Edition
- **Tarih**: Ağustos 2025

## 🔄 Güncellemeler

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

## 📁 Proje Yapısı

```
schemini-manager-web/
│
├── app.py                 # Ana Flask uygulaması
├── web_base_manager.py    # Temel manager sınıfı
├── web_scan_manager.py    # Tarama işlemleri
├── web_update_manager.py  # Güncelleme işlemleri
├── web_file_add_manager.py # Dosya ekleme işlemleri
├── web_settings_manager.py # Ayarlar yönetimi
├── schemini_config.json   # Yapılandırma dosyası
│
├── templates/             # HTML şablonları
│   ├── base.html
│   ├── index.html
│   ├── homepage.html
│   ├── scan.html
│   ├── update.html
│   ├── file_add.html
│   ├── settings.html
│   └── error.html
│
├── static/               # Statik dosyalar
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
│
└── logs/                 # Log dosyaları
    └── *.log
```

---

**🎯 Schemini Manager Web - Profesyonel Dosya Yönetimi Çözümü**

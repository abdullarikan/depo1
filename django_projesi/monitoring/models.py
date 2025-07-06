from django.db import models
from django.contrib.auth.models import User

# ==============================================================================
# TEMEL MODBUS MODELLERİ
# ==============================================================================

class Device(models.Model):

    STATUS_CHOICES = [
        ("online", "Çevrimiçi"),
        ("offline", "Çevrimdışı"),
    ]


    name = models.CharField(max_length=100, unique=True, help_text="Cihazın adı veya tanımı (Örn: Kazan Dairesi PLC)")
    connection_host = models.CharField(max_length=100, help_text="Cihazın bağlantı adresi (IP veya hostname)")
    port = models.IntegerField(default=502, help_text="Modbus TCP portu")
    slave_id = models.IntegerField(default=1, verbose_name="Slave ID / Unit ID")
    is_active = models.BooleanField(default=True, help_text="Bu cihazdan veri okunacak mı?")

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="offline", verbose_name="Cihaz Durumu")
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Son Görülme")

    def __str__(self):
        return self.name
    class Meta:
        verbose_name = "Cihaz"
        verbose_name_plural = "Cihazlar"
        ordering = ['name']

class Register(models.Model):
    REGISTER_TYPE_CHOICES = [
        ('holding', 'Holding Register'),
        ('coil', 'Coil'),
        ('input', 'Input Register'),
        ('discrete_input', 'Discrete Input'),
    ]
    DATA_TYPE_CHOICES = [
        ('UINT16', '16-bit Unsigned Int'),
        ('INT16', '16-bit Signed Int'),
        ('UINT32', '32-bit Unsigned Int'),    # YENİ
        ('INT32', '32-bit Signed Int'),
        ('FLOAT32', '32-bit Float'),
        ('STRING', 'String (Metin)'),        # YENİ
    ]
    BYTE_ORDER_CHOICES = [
        ('BIG', 'Big-Endian (ABCD)'),
        ('LITTLE', 'Little-Endian (DCBA)'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='registers')
    name = models.CharField(max_length=100, help_text="Register'ın tanımı (Örn: Sıcaklık, Basınç)")
    address = models.IntegerField(help_text="Register adresi (örn: 40001, 1)")
    register_type = models.CharField(max_length=20, choices=REGISTER_TYPE_CHOICES)
    is_writable = models.BooleanField(default=False, help_text="Bu register'a yazma işlemi yapılabilir mi?")

    data_type = models.CharField(max_length=10, choices=DATA_TYPE_CHOICES, default='UINT16', verbose_name="Veri Tipi")
    byte_order = models.CharField(max_length=10, choices=BYTE_ORDER_CHOICES, default='BIG', verbose_name="Byte/Word Sırası")

    min_value = models.FloatField(null=True, blank=True, verbose_name="Minimum Değer", help_text="Kadran/Bar için alt limit (opsiyonel)")
    max_value = models.FloatField(null=True, blank=True, verbose_name="Maksimum Değer", help_text="Kadran/Bar için üst limit (opsiyonel)")

    show_on_statusbar = models.BooleanField(default=False, verbose_name="Durum Çubuğunda Göster")
    icon_name = models.CharField(
        max_length=50, 
        blank=True, null=True, 
        verbose_name="Bootstrap İkon Adı",
        help_text="Örn: bi-thermometer-half. Boş bırakılabilir."
    )

    # YENİ EKLENEN ALAN
    scaling_factor = models.FloatField(
        default=1.0, 
        verbose_name="Değer Çarpanı",
        help_text="Gelen ham değeri bu sayıyla çarp. 10'a bölmek için 0.1, 100'e bölmek için 0.01 girin."
    )


    # --- YENİ EKLENEN ALAN ---
    invert_value = models.BooleanField(
        default=False,
        verbose_name="Değeri Tersle (0->1, 1->0)",
        help_text="İşaretlenirse, bu register'dan okunan 0 değeri 1, 1 değeri ise 0 olarak işlenir. Sadece Coil ve Discrete Input için geçerlidir."
    )
    # --- BİTİŞ ---


    # --- YENİ EKLENEN ALAN ---
    string_length = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="String Uzunluğu (Register)",
        help_text="Eğer Veri Tipi 'String' ise, kaç register'lık veri okunacağını belirtir."
    )

    # --- YENİ EKLENEN ALAN ---
    DISPLAY_CHOICES = [
        ('numeric', 'Sayısal Gösterim'),
        ('enum', 'Metin Eşleştirme (Enum)'),
    ]
    display_preference = models.CharField(
        max_length=20,
        choices=DISPLAY_CHOICES,
        default='numeric',
        verbose_name="Gösterim Tercihi"
    )
    # --- BİTİŞ ---


    def __str__(self):
        return f"{self.device.name}: {self.name}"



class EnumValue(models.Model):
    """
    Bir register'ın belirli bir sayısal değerinin, hangi metin etiketine
    karşılık geldiğini saklar. (Örn: 7 -> "K8: Kontaktör Testi")
    """
    register = models.ForeignKey(
        Register, 
        on_delete=models.CASCADE, 
        related_name='enum_values',
        verbose_name="Ana Register",
        # Bu, admin panelinde sadece metin eşleştirmesi olarak seçilen register'ları gösterir.
        limit_choices_to={'display_preference': 'enum'}
    )
    raw_value = models.IntegerField(verbose_name="Gelen Ham Değer")
    label = models.CharField(max_length=100, verbose_name="Gösterilecek Etiket")

    class Meta:
        # Bir register için her sayısal değerin tek bir anlamı olabilir
        unique_together = ('register', 'raw_value')
        ordering = ['raw_value']
        verbose_name = "Numaralandırılmış Değer Eşleşmesi"
        verbose_name_plural = "Numaralandırılmış Değer Eşleşmeleri"

    def __str__(self):
        return f"{self.register.name}: {self.raw_value} -> '{self.label}'"





# ==============================================================================
# YENİ TEST YÖNETİM SİSTEMİ MODELLERİ
# ==============================================================================

class TestRun(models.Model):
    """Her bir 5000 saatlik test seansını temsil eden ana model."""
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Başlamadı'),
        ('RUNNING', 'Çalışıyor'),
        ('PAUSED', 'Duraklatıldı'),
        ('COMPLETED', 'Tamamlandı'),
        ('ABORTED', 'İptal Edildi'),
    ]
    
    test_name = models.CharField(max_length=200, verbose_name="Test Adı")
    customer_name = models.CharField(max_length=200, verbose_name="Müşteri Adı", blank=True, null=True)
    product_details = models.TextField(verbose_name="Test Edilen Ürün Detayları", blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NOT_STARTED')
    
    target_duration_seconds = models.PositiveIntegerField(default=(5000 * 3600), verbose_name="Hedef Süre (saniye)")
    elapsed_seconds = models.PositiveIntegerField(default=0, verbose_name="Geçen Toplam Süre (saniye)")

    start_time = models.DateTimeField(null=True, blank=True, verbose_name="Başlangıç Zamanı")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="Bitiş Zamanı")
    last_resumed_time = models.DateTimeField(null=True, blank=True, verbose_name="Son Devam Etme Zamanı")

    control_coil = models.ForeignKey(
        Register, 
        on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'register_type': 'coil', 'is_writable': True},
        verbose_name="Test Kontrol Coili"
    )

    class Meta:
        verbose_name = "Test Seansı"
        verbose_name_plural = "Test Seansları"
        ordering = ['-start_time']

    def __str__(self):
        return f"[{self.id}] {self.test_name} ({self.get_status_display()})"


class TestEventLog(models.Model):
    """Bir test seansı sırasındaki önemli olayları kaydeden seyir defteri."""
    EVENT_CHOICES = [
        ('START', 'Test Başlatıldı'),
        ('PAUSE', 'Test Duraklatıldı'),
        ('RESUME', 'Test Devam Ettirildi'),
        ('COMPLETE', 'Test Tamamlandı'),
        ('ABORT', 'Test İptal Edildi'),
    ]
    
    test_run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name='event_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    notes = models.TextField(blank=True, verbose_name="Notlar")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Test Olay Kaydı"
        verbose_name_plural = "Test Olay Kayıtları"
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.test_run.test_name}] - {self.get_event_type_display()}"


class DataPoint(models.Model):
    """Her bir veri okumasını temsil eder."""
    register = models.ForeignKey(Register, on_delete=models.CASCADE, related_name='datapoints')
    value = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    test_run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name='datapoints')
    
    def __str__(self):
        return f"{self.register.name} -> {self.value}"



class ScheduledTask(models.Model):
    """Her bir AÇ/KAPAT görevini saklayan basit zamanlama modelimiz."""
    ACTION_CHOICES = [(True, 'AÇIK'), (False, 'KAPALI')]
    register = models.ForeignKey(Register, on_delete=models.CASCADE, limit_choices_to={'register_type': 'coil', 'is_writable': True})
    time_to_run = models.TimeField()
    action = models.BooleanField(choices=ACTION_CHOICES, default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        action_str = "AÇ" if self.action else "KAPAT"
        return f"{self.register.name} için saat {self.time_to_run.strftime('%H:%M')} itibarıyla '{action_str}' görevi"







class DashboardWidget(models.Model):
    PAGE_CHOICES = [
        ('status_panel', 'Durum Paneli'),
        ('mosaic_dashboard', 'Mozaik Pano'),
    ]



    WIDGET_TYPE_CHOICES = [
        ('line_chart', 'Çizgi Grafik'),
        ('gauge', 'Kadran (Gauge)'),
        ('digital', 'Sayısal Gösterge'),
        ('indicator', 'Durum Işığı'),
        ('enum_display', 'Metin Eşleştirme (Enum)'),
        ('event_log', 'Canlı Olay Akışı'),
    ]
    
    
    
    
    STYLE_CHOICES = [
        ('primary', 'Normal (Mavi)'),
        ('secondary', 'İkincil (Gri)'),
        ('warning', 'Uyarı (Sarı)'),
        ('danger', 'Tehlike (Kırmızı)'),
    ]

    target_page = models.CharField(max_length=20, choices=PAGE_CHOICES, default='mosaic_dashboard', verbose_name="Hedef Sayfa")
    name = models.CharField(max_length=100, verbose_name="Panel Başlığı")
    order = models.PositiveIntegerField(default=100, verbose_name="Görünüm Sırası", help_text="Düşük numaralar daha üstte görünür.")
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPE_CHOICES, default='digital', verbose_name="Gösterim Tipi")
    style = models.CharField(max_length=20, choices=STYLE_CHOICES, default='primary', verbose_name="Panel Stili")

    # --- YENİ EKLENEN GRID ALANLARI ---
    grid_x = models.PositiveIntegerField(default=0, verbose_name="Grid X Konumu")
    grid_y = models.PositiveIntegerField(default=0, verbose_name="Grid Y Konumu")
    grid_width = models.PositiveIntegerField(default=4, verbose_name="Grid Genişliği (1-12 arası)")
    grid_height = models.PositiveIntegerField(default=4, verbose_name="Grid Yüksekliği")
    # --- BİTİŞ ---

    # --- YENİ EKLENEN ALAN ---
    THEME_CHOICES = [
        ('none', 'Yok (Standart)'),
        ('rain-1', 'Yağmur Teması'),
        ('rain-2', 'Yağmur Teması - Pencere'),
        ('solar-1', 'Güneş Teması'),
        ('sis-1', 'Sis Teması - puslu'),
        ('nem-1', 'Nem Teması - deneme'),
        ('sicaklik-1', 'Sicak Teması - deneme'),
        ('tema1', 'tema1 Teması'),
        ('tema2', 'tema2 Teması'),
        ('kritik', 'Kritik Durum Teması'),
        ('yagmur', 'Yağmur Teması'),
        ('solar', 'Güneş Teması'),
        ('nem', 'Nem Teması'),
        ('sis', 'Sis Teması'),
        ('sicaklik', 'Sıcaklık Teması'),
    ]
    background_theme = models.CharField(
        max_length=20, 
        choices=THEME_CHOICES, 
        default='none', 
        verbose_name="Arka Plan Teması"
    )
    # --- BİTİŞ ---

    trigger_register = models.ForeignKey(
        Register,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='triggered_widgets',
        help_text="Bu panelin görünmesi için hangi register'ın AÇIK (1) olması gerekir? Boş bırakılırsa her zaman görünür.",
        limit_choices_to={'register_type': 'coil'}
    )

    registers = models.ManyToManyField(
        Register, blank=True,
        related_name='widgets',
        verbose_name="Panele Dahil Edilecek Register'lar"
    )

    class Meta:
        ordering = ['order']
        verbose_name = "Pano Bileşeni"  # Daha genel bir isim
        verbose_name_plural = "Pano Bileşenleri" # Daha genel bir isim

    def __str__(self):
        return self.name


# ==============================================================================
# ALARIM YÖNETİM SİSTEMİ MODELLERİ
# ==============================================================================




class AlarmRule(models.Model):
    CONDITION_CHOICES = [
        ('gt', 'Büyüktür'),
        ('lt', 'Küçüktür'),
        ('eq', 'Eşittir'),
    ]
    # YENİ: 4 Seviyeli Alarm Tipi
    SEVERITY_CHOICES = [
        ('info', 'Bilgi'),
        ('warning', 'Uyarı'),
        ('critical', 'Kritik'),
        ('fault', 'Hata'),
    ]

    name = models.CharField(max_length=150, verbose_name="Kural Adı")
    register = models.ForeignKey(Register, on_delete=models.CASCADE, related_name='alarm_rules')
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, verbose_name="Koşul")
    threshold = models.FloatField(verbose_name="Eşik Değeri")
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='warning', verbose_name="Önem Seviyesi")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")

    def __str__(self):
        return f"{self.name} ({self.register.name} {self.get_condition_display()} {self.threshold})"

class AlarmLog(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE_UNACK', 'Aktif, Onaylanmamış'),
        ('ACTIVE_ACK', 'Aktif, Onaylanmış'),
        ('CLEARED_UNACK', 'Normale Döndü, Onaylanmamış'),
        ('CLEARED_ACK', 'Normale Döndü, Onaylandı'), # <-- YENİ EKLENEN DURUM
    ]
    alarm_rule = models.ForeignKey(AlarmRule, on_delete=models.CASCADE, related_name='logs')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE_UNACK')
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    acknowledged_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Alarm: {self.alarm_rule.name} - Durum: {self.get_status_display()}"



class RegisterMapping(models.Model):
    """
    Bir register'daki değer değişikliğinin, başka bir register'ı tetiklemesi
    kuralını tanımlar. (Master/Slave mantığı)
    """
    name = models.CharField(
        max_length=150, 
        verbose_name="Kural Adı", 
        help_text="Bu senkronizasyon kuralı için açıklayıcı bir isim (örn: Ana Pompa -> Yedek Pompa)."
    )

    source_register = models.ForeignKey(
        Register,
        on_delete=models.CASCADE,
        related_name='source_mappings',
        verbose_name="Kaynak Register (Değişimi İzlenecek)"
    )

    destination_register = models.ForeignKey(
        Register,
        on_delete=models.CASCADE,
        related_name='destination_mappings',
        verbose_name="Hedef Register (Değeri Güncellenecek)",
        limit_choices_to={'is_writable': True} # Sadece yazılabilir register'lar hedef olabilir
    )

    is_active = models.BooleanField(default=True, verbose_name="Bu Kural Aktif mi?")

    class Meta:
        verbose_name = "Register Eşleştirmesi"
        verbose_name_plural = "Register Eşleştirmeleri"
        # Bir kaynak register'ın, aynı hedefi birden fazla kez tetiklemesini engeller
        unique_together = ('source_register', 'destination_register')

    def __str__(self):
        return f"'{self.source_register}' değiştiğinde -> '{self.destination_register}' güncellenir"



from django.contrib import admin
from .models import Device, Register, DataPoint, TestRun, TestEventLog, ScheduledTask, DashboardWidget, AlarmRule, AlarmLog, RegisterMapping, EnumValue

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'connection_host', 'port', 'slave_id', 'is_active')
    list_editable = ('is_active', 'connection_host', 'port', 'slave_id')
    search_fields = ('name',)


# YENİ: Bu sınıf, EnumValue'ları Register sayfasının içinde bir tablo olarak gösterir
class EnumValueInline(admin.TabularInline):
    model = EnumValue
    extra = 1 # Varsayılan olarak 1 tane boş satır gösterir
    fields = ('raw_value', 'label') # Sadece bu alanlar gösterilsin
    verbose_name = "Değer-Metin Eşleşmesi"
    verbose_name_plural = "Değer-Metin Eşleşmeleri"



@admin.register(Register)
class RegisterAdmin(admin.ModelAdmin):
    list_display = ('name', 'device', 'address', 'register_type', 'data_type', 'display_preference', 'is_writable')
    list_filter = ('device', 'register_type', 'data_type', 'display_preference')
    list_editable = ('is_writable', 'data_type', 'display_preference')
    search_fields = ('name', 'device__name')
    # --- YENİ EKLENEN SATIR ---
    inlines = [EnumValueInline]





@admin.register(DataPoint)
class DataPointAdmin(admin.ModelAdmin):
    list_display = ('register', 'value', 'timestamp', 'test_run')
    list_filter = ('register__device', 'test_run')
    readonly_fields = ('register', 'value', 'timestamp', 'test_run')
    search_fields = ('register__name', 'test_run__test_name')

# Test olaylarını, ait oldukları Test Seansı sayfasında satır olarak göstermek için
class TestEventLogInline(admin.TabularInline):
    model = TestEventLog
    extra = 0 # Yeni boş olay kaydı ekleme alanı gösterme
    readonly_fields = ('timestamp', 'event_type', 'notes', 'user')
    can_delete = False
    ordering = ('-timestamp',)

@admin.register(ScheduledTask)
class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_to_run', 'action', 'is_active')
    list_filter = ('is_active', 'register__device')
    list_editable = ('is_active', 'time_to_run', 'action')

@admin.register(TestRun)
class TestRunAdmin(admin.ModelAdmin):
    list_display = ('test_name', 'status', 'start_time', 'end_time', 'customer_name')
    list_filter = ('status', 'customer_name')
    readonly_fields = ('elapsed_seconds', 'last_resumed_time')
    search_fields = ('test_name', 'customer_name')
    # Olay kayıtlarını Test Seansı detay sayfasının altında göster
    inlines = [TestEventLogInline]

@admin.register(TestEventLog)
class TestEventLogAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'timestamp', 'user')
    list_filter = ('test_run', 'event_type', 'user')
    search_fields = ('test_run__test_name', 'notes')



@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ('name', 'target_page', 'widget_type', 'order', 'trigger_register', 'grid_x', 'grid_y', 'grid_width', 'grid_height')
    list_filter = ('target_page', 'widget_type', 'style')
    list_editable = ('order', 'widget_type')
    ordering = ('order',)
    filter_horizontal = ('registers',)




@admin.register(AlarmRule)
class AlarmRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'register', 'condition', 'threshold', 'severity', 'is_active')
    list_filter = ('is_active', 'severity', 'register__device')
    list_editable = ('is_active', 'threshold', 'severity')

@admin.register(AlarmLog)
class AlarmLogAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'start_time', 'end_time', 'status', 'acknowledged_by')
    list_filter = ('status', 'alarm_rule__register__device')
    readonly_fields = ('alarm_rule', 'start_time', 'end_time', 'status', 'acknowledged_by', 'acknowledged_time')



@admin.register(RegisterMapping)
class RegisterMappingAdmin(admin.ModelAdmin):
    list_display = ('name', 'source_register', 'destination_register', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'source_register__name', 'destination_register__name')
    list_editable = ('is_active',)
    # Çok sayıda register olduğunda, seçim yapmayı kolaylaştıran bir arayüz sunar
    raw_id_fields = ('source_register', 'destination_register')




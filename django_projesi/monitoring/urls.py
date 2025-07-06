from django.urls import path
from . import views

app_name = 'monitoring'

urlpatterns = [

    # Ana sayfa artık Test Kontrol Merkezi olacak
    path('', views.test_center_view, name='test_center'),

    # --- YENİ TEST AKIŞI URL'LERİ ---
    path('test/new/', views.new_test_view, name='new_test'),
    path('test/<int:pk>/start/', views.start_test_view, name='start_test'),
    # --- BİTİŞ ---

    # --- YENİ EKLENEN SATIRLAR ---
    path('test/<int:pk>/pause/', views.pause_test_view, name='pause_test'),
    path('test/<int:pk>/resume/', views.resume_test_view, name='resume_test'),
    path('test/<int:pk>/abort/', views.abort_test_view, name='abort_test'),
    # --- BİTİŞ ---

    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('registers/<int:pk>/details/', views.register_detail_view, name='register_detail'),

    
    # Cihaz Yönetimi URL'leri
    path('devices/', views.DeviceListView.as_view(), name='device_list'),
    path('devices/add/', views.DeviceCreateView.as_view(), name='device_add'),
    path('devices/<int:pk>/edit/', views.DeviceUpdateView.as_view(), name='device_edit'),
    path('devices/<int:pk>/delete/', views.DeviceDeleteView.as_view(), name='device_delete'),

    # Register Yönetimi URL'leri
    path('registers/', views.RegisterListView.as_view(), name='register_list'),
    path('registers/add/', views.RegisterCreateView.as_view(), name='register_add'),
    path('registers/<int:pk>/edit/', views.RegisterUpdateView.as_view(), name='register_edit'),
    path('registers/<int:pk>/delete/', views.RegisterDeleteView.as_view(), name='register_delete'),

    # Raporlama ve PDF URL'leri (Bunlar kalıyor, daha sonra güncelleyeceğiz)
    path('reports/', views.historical_data_view, name='historical_data'),
    path('reports/export-pdf/', views.export_pdf_view, name='export_pdf'), 

    path('status-panel/', views.status_panel_view, name='status_panel'),

    path('mosaic-dashboard/', views.mosaic_dashboard_view, name='mosaic_dashboard'),

    path('schedule-designer/', views.schedule_designer_view, name='schedule_designer'),

    path('alarms/', views.alarm_log_view, name='alarm_log'),

   
    
    # API URL'leri (Sadece manuel coil yazma API'si kaldı)
    path('api/write-coil/<int:register_id>/', views.WriteCoilView.as_view(), name='write_coil'),

    path('api/save-widget-layout/', views.save_widget_layout_view, name='save_widget_layout'),

    path('api/update-schedule/<int:register_id>/', views.UpdateScheduleAPIView.as_view(), name='api_update_schedule'),

    path('api/available-coils/', views.AvailableCoilsAPIView.as_view(), name='api_available_coils'),

]

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

# Yeni modellere göre importları güncelliyoruz, ScheduledTask'ı siliyoruz
from .models import Device, Register, DataPoint, TestRun, TestEventLog, ScheduledTask, DashboardWidget, AlarmRule, AlarmLog
from .forms import DeviceForm, RegisterForm, TestRunForm
from .tasks import write_coil_value
from django.core.paginator import Paginator
from django.db.models import Q
from weasyprint import HTML


# Not: dashboard, status_panel, schedule_designer view'leri
# yeni Test Yönetim Sistemi mantığıyla yeniden yazılacağı için şimdilik kaldırıldı.

# Cihaz CRUD View'leri (Aynı kalıyor)
# ==================================
# Cihaz ve Register CRUD View'leri
# ==================================

class DeviceListView(LoginRequiredMixin, ListView):
    model = Device
    template_name = 'monitoring/device_list.html'
    context_object_name = 'devices'

class DeviceCreateView(LoginRequiredMixin, CreateView):
    model = Device
    form_class = DeviceForm
    template_name = 'monitoring/generic_form.html'
    success_url = reverse_lazy('monitoring:device_list')
    extra_context = {'page_title': 'Yeni Cihaz Ekle'}

class DeviceUpdateView(LoginRequiredMixin, UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = 'monitoring/generic_form.html'
    success_url = reverse_lazy('monitoring:device_list')
    extra_context = {'page_title': 'Cihazı Düzenle'}

class DeviceDeleteView(LoginRequiredMixin, DeleteView):
    model = Device
    template_name = 'monitoring/confirm_delete.html'
    success_url = reverse_lazy('monitoring:device_list')

class RegisterListView(LoginRequiredMixin, ListView):
    model = Register
    template_name = 'monitoring/register_list.html'
    context_object_name = 'registers'

class RegisterCreateView(LoginRequiredMixin, CreateView):
    model = Register
    form_class = RegisterForm
    template_name = 'monitoring/generic_form.html'
    success_url = reverse_lazy('monitoring:register_list')
    extra_context = {'page_title': 'Yeni Register Ekle'}

class RegisterUpdateView(LoginRequiredMixin, UpdateView):
    model = Register
    form_class = RegisterForm
    template_name = 'monitoring/generic_form.html'
    success_url = reverse_lazy('monitoring:register_list')
    extra_context = {'page_title': 'Register\'ı Düzenle'}

class RegisterDeleteView(LoginRequiredMixin, DeleteView):
    model = Register
    template_name = 'monitoring/confirm_delete.html'
    success_url = reverse_lazy('monitoring:register_list')




# Raporlama 
@login_required
def historical_data_view(request):
    selected_test_id = request.GET.get('test_run_id', None)
    status_filter = request.GET.get('status_filter', 'all')
    selected_register_id = request.GET.get('register_id', None)
    value_operator = request.GET.get('value_operator', 'gt')
    filter_value_analog = request.GET.get('filter_value_analog', '')
    filter_value_binary = request.GET.get('filter_value_binary', '')
    start_datetime = request.GET.get('start_datetime', '')
    end_datetime = request.GET.get('end_datetime', '')

    datapoints_list = DataPoint.objects.none()
    test_run = None
    all_registers_in_test = Register.objects.none()
    selected_register = None

    if selected_test_id:
        test_run = get_object_or_404(TestRun, pk=selected_test_id)
        datapoints_list = DataPoint.objects.filter(test_run=test_run)
        all_registers_in_test = Register.objects.filter(datapoints__test_run_id=selected_test_id).distinct()

        # Durum filtresi "Tümü" değilse, zaman aralıklarını hesapla
        if status_filter in ['RUNNING', 'PAUSED']:
            events = test_run.event_logs.order_by('timestamp')
            time_ranges = []
            last_event_time = None
            last_event_type = None

            for event in events:
                if last_event_time:
                    # İki event arasındaki zaman aralığının durumunu belirle
                    # Örneğin, bir önceki event START ise, bu aralık RUNNING durumundadır.
                    interval_status = 'RUNNING' if last_event_type in ['START', 'RESUME'] else 'PAUSED'

                    # Eğer kullanıcının aradığı durum, bu aralığın durumuyla eşleşiyorsa listeye ekle
                    if interval_status == status_filter:
                        time_ranges.append((last_event_time, event.timestamp))

                last_event_time = event.timestamp
                last_event_type = event.event_type

            # Eğer test hala bitmediyse, son olaydan şimdiki zamana kadar olan aralığı da hesaba kat
            if last_event_time and test_run.status in ['RUNNING', 'PAUSED']:
                if test_run.status == status_filter:
                    time_ranges.append((last_event_time, timezone.now()))

            # Oluşturulan zaman aralıklarına uyan tüm verileri filtrele
            q_objects = Q()
            for start, end in time_ranges:
                q_objects |= Q(timestamp__range=(start, end))

            datapoints_list = datapoints_list.filter(q_objects)

        # YENİ: Register filtresini uygula
        if selected_register_id:
            datapoints_list = datapoints_list.filter(register_id=selected_register_id)
            selected_register = get_object_or_404(Register, pk=selected_register_id)

            # Analog filtre için 'filter_value_analog' kullan
            if selected_register.register_type in ['holding', 'input'] and filter_value_analog:
                try:
                    numeric_value = float(filter_value_analog)
                    if value_operator == 'gt': datapoints_list = datapoints_list.filter(value__gt=numeric_value)
                    elif value_operator == 'lt': datapoints_list = datapoints_list.filter(value__lt=numeric_value)
                    elif value_operator == 'exact': datapoints_list = datapoints_list.filter(value=numeric_value)
                except (ValueError, TypeError): pass

            # Binary filtre için 'filter_value_binary' kullan
            elif selected_register.register_type in ['coil', 'discrete_input'] and filter_value_binary:
                datapoints_list = datapoints_list.filter(value=float(filter_value_binary))
            

        # Zaman aralığı filtresi
        if start_datetime: datapoints_list = datapoints_list.filter(timestamp__gte=start_datetime)
        if end_datetime: datapoints_list = datapoints_list.filter(timestamp__lte=end_datetime)


    all_tests = TestRun.objects.all().order_by('-id')
    ordered_datapoints = datapoints_list.order_by('-timestamp')
    paginator = Paginator(datapoints_list.order_by('-timestamp'), 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_title': 'Gelişmiş Raporlama', 
        'page_obj': page_obj, 
        'all_tests': all_tests,
        'all_registers_in_test': all_registers_in_test, 
        'selected_test_id': selected_test_id,
        'selected_register_id': selected_register_id, 
        'selected_register': selected_register,
        'status_filter': status_filter, 
        'value_operator': value_operator,
        'filter_value_analog': filter_value_analog,
        'filter_value_binary': filter_value_binary, 
        'start_datetime': start_datetime, 
        'end_datetime': end_datetime,
    }
    return render(request, 'monitoring/historical_data.html', context)





#pdf indir

@login_required
def export_pdf_view(request):
    # URL'den filtreleri al
    selected_test_id = request.GET.get('test_run_id', None)
    status_filter = request.GET.get('status_filter', 'all')

    datapoints_list = DataPoint.objects.none()
    test_run = None

    if selected_test_id:
        test_run = get_object_or_404(TestRun, pk=selected_test_id)
        datapoints_list = DataPoint.objects.filter(test_run=test_run)

        # historical_data_view'deki durum filtresi mantığının aynısını uygula
        if status_filter in ['RUNNING', 'PAUSED']:
            events = test_run.event_logs.order_by('timestamp')
            time_ranges, last_event_time, last_event_type = [], None, None
            for event in events:
                if last_event_time:
                    interval_status = 'RUNNING' if last_event_type in ['START', 'RESUME'] else 'PAUSED'
                    if interval_status == status_filter:
                        time_ranges.append((last_event_time, event.timestamp))
                last_event_time, last_event_type = event.timestamp, event.event_type
            if last_event_time and test_run.status == status_filter:
                time_ranges.append((last_event_time, timezone.now()))

            q_objects = Q()
            for start, end in time_ranges: q_objects |= Q(timestamp__range=(start, end))
            datapoints_list = datapoints_list.filter(q_objects) if time_ranges else DataPoint.objects.none()

    # PDF'i oluştur
    html_string = render_to_string('monitoring/report_pdf.html', {
        'datapoints': datapoints_list.order_by('timestamp'),
        'test_run': test_run
    })

    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapor_test_{selected_test_id}.pdf"'
    return response




@login_required
def test_center_view(request):
    """Ana kontrol merkezi. Aktif testi ve geçmiş testleri gösterir."""
    # En son oluşturulan Test Seansını bul
    latest_test = TestRun.objects.first()
    # Tamamlanmış veya iptal edilmiş testleri bul
    past_tests = TestRun.objects.all() # BU SATIRI GÜNCELLEYİN
    
    context = {
        'page_title': 'Test Kontrol Merkezi',
        'latest_test': latest_test,
        'past_tests': past_tests # Yeni context
    }
    return render(request, 'monitoring/test_center.html', context)





@login_required
def new_test_view(request):
    """Yeni bir test seansı oluşturma formunu gösterir ve işler."""
    # Devam eden bir test var mı diye kontrol et
    active_test = TestRun.objects.filter(status__in=['RUNNING', 'PAUSED']).first()
    if active_test:
        # Eğer varsa, yeni test oluşturmaya izin verme, ana merkeze yönlendir.
        # (Daha sonra buraya bir uyarı mesajı ekleyebiliriz)
        return redirect('monitoring:test_center')

    form = TestRunForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        test_run = form.save(commit=False)
        test_run.status = 'NOT_STARTED' # Testi "Başlamadı" olarak kaydet
        test_run.save()

        # Bir olay kaydı oluştur
        TestEventLog.objects.create(
            test_run=test_run,
            event_type='START', # Bu yeni bir event tipi olabilir
            notes=f"Test seansı '{request.user.username}' tarafından yeni test seansı oluşturuldu.",
            user=request.user
        )
        # Şimdilik doğrudan test merkezine yönlendiriyoruz
        return redirect('monitoring:test_center')

    context = {
        'form': form,
        'page_title': 'Yeni Test Seansı Başlat'
    }
    return render(request, 'monitoring/generic_form.html', context)



@login_required
def start_test_view(request, pk):
    """Oluşturulmuş bir testi 'Çalışıyor' durumuna getirir."""
    test_run = get_object_or_404(TestRun, pk=pk)
    if request.method == 'POST' and test_run.status == 'NOT_STARTED':
        test_run.status = 'RUNNING'
        test_run.start_time = timezone.now()
        test_run.last_resumed_time = timezone.now()
        test_run.save()

        TestEventLog.objects.create(
            test_run=test_run, event_type='START',
            notes="Test başlatıldı.", user=request.user
        )

        if test_run.control_coil:
            write_coil_value.delay(register_id=test_run.control_coil.id, value=True)

        return redirect('monitoring:test_center')


@login_required
def pause_test_view(request, pk):
    """Çalışan bir testi duraklatır."""
    test_run = get_object_or_404(TestRun, pk=pk)
    if request.method == 'POST' and test_run.status == 'RUNNING':
        # Geçen süreyi hesapla ve toplam süreye ekle
        time_since_resume = timezone.now() - test_run.last_resumed_time
        test_run.elapsed_seconds += time_since_resume.total_seconds()

        # Durumu güncelle
        test_run.status = 'PAUSED'
        test_run.save()

        TestEventLog.objects.create(
            test_run=test_run, event_type='PAUSE',
            notes="Test kullanıcı tarafından duraklatıldı.", user=request.user
        )

        # Kontrol coil'ini KAPAT
        if test_run.control_coil:
            write_coil_value.delay(register_id=test_run.control_coil.id, value=False)

    return redirect('monitoring:test_center')

@login_required
def resume_test_view(request, pk):
    """Duraklatılmış bir testi devam ettirir."""
    test_run = get_object_or_404(TestRun, pk=pk)
    if request.method == 'POST' and test_run.status == 'PAUSED':
        test_run.status = 'RUNNING'
        test_run.last_resumed_time = timezone.now() # Geri sayım için başlangıç noktasını güncelle
        test_run.save()

        TestEventLog.objects.create(
            test_run=test_run, event_type='RESUME',
            notes="Test devam ettirildi.", user=request.user
        )

        # Kontrol coil'ini AÇ
        if test_run.control_coil:
            write_coil_value.delay(register_id=test_run.control_coil.id, value=True)

    return redirect('monitoring:test_center')

@login_required
def abort_test_view(request, pk):
    """Aktif bir testi vaktinden önce sonlandırır."""
    test_run = get_object_or_404(TestRun, pk=pk)
    if request.method == 'POST' and test_run.status in ['RUNNING', 'PAUSED']:
        # Eğer test çalışıyorsa, son geçen süreyi de hesaba kat
        if test_run.status == 'RUNNING':
            time_since_resume = timezone.now() - test_run.last_resumed_time
            test_run.elapsed_seconds += time_since_resume.total_seconds()

        test_run.status = 'ABORTED' # Durumu "İptal Edildi" yap
        test_run.end_time = timezone.now()
        test_run.save()

        TestEventLog.objects.create(
            test_run=test_run, event_type='ABORT',
            notes="Test kullanıcı tarafından sonlandırıldı.", user=request.user
        )

        # Kontrol coil'ini KAPAT
        if test_run.control_coil:
            write_coil_value.delay(register_id=test_run.control_coil.id, value=False)

    return redirect('monitoring:test_center')






@login_required
def dashboard_view(request):
    # Sadece okunabilir ve sayısal olan register'ları grafikler için al
    readable_registers = Register.objects.filter(
        device__is_active=True,
        register_type__in=['holding', 'input']
    ).select_related('device')

    # Sadece yazılabilir olan coil'leri switch'ler için al
    writable_coils = Register.objects.filter(
        device__is_active=True,
        register_type='coil',
        is_writable=True
    ).select_related('device')

    # Her bir coil'in son durumunu bul (switch'lerin başlangıç durumu için)
    for coil in writable_coils:
        latest_datapoint = DataPoint.objects.filter(register=coil).order_by('-timestamp').first()
        coil.latest_value = bool(latest_datapoint.value) if latest_datapoint else False

    # Grafiklerin JavaScript'te oluşturulması için JSON verisi hazırla
    registers_for_js = [{'pk': r.pk, 'name': r.name} for r in readable_registers]

    context = {
        'page_title': 'Ana Kontrol Paneli',
        'registers': readable_registers,
        'coils': writable_coils,
        'registers_json': json.dumps(registers_for_js),
    }
    return render(request, 'monitoring/dashboard.html', context)


@login_required
def register_detail_view(request, pk):
    register = get_object_or_404(Register.objects.select_related('device'), pk=pk)

    # O register'a ait tüm veri noktalarını alıyoruz
    # Not: Eğer bu register bir teste bağlıysa, sadece o testin verilerini de alabiliriz.
    datapoints = DataPoint.objects.filter(register=register).order_by('timestamp')

    # ApexCharts'ın anlayacağı formata çeviriyoruz
    chart_data = [[int(dp.timestamp.timestamp() * 1000), dp.value] for dp in datapoints]

    context = {
        'page_title': f"{register.name} - Detaylı Grafik",
        'register': register,
        'chart_data_json': json.dumps(chart_data)
    }
    return render(request, 'monitoring/register_detail.html', context)


@login_required
def schedule_designer_view(request):
    """Görsel zamanlama planlayıcısı sayfasını gösterir."""
    # Zamanlaması yapılmış olan register'ları bul
    scheduled_coils = Register.objects.filter(
        id__in=ScheduledTask.objects.values_list('register_id', flat=True)
    ).distinct().select_related('device')

    schedules_data = {}
    for coil in scheduled_coils:
        tasks = ScheduledTask.objects.filter(register=coil).order_by('time_to_run')
        schedule_state = [False] * 12 # 24 saati 2'şer saatlik 12 dilime bölüyoruz

        # Her bir dilimin durumunu hesapla
        for i in range(12):
            slot_hour = i * 2
            last_task_before_slot = tasks.filter(time_to_run__hour__lt=slot_hour).last()
            task_at_slot_start = tasks.filter(time_to_run__hour=slot_hour).first()

            current_slot_action = False
            if last_task_before_slot:
                current_slot_action = last_task_before_slot.action
            if task_at_slot_start:
                current_slot_action = task_at_slot_start.action
            schedule_state[i] = current_slot_action

        schedules_data[coil.id] = { 'id': coil.id, 'name': str(coil), 'schedule_state': schedule_state }

    context = {
        'page_title': 'Otomasyon Tasarımcısı',
        'saved_schedules_json': json.dumps(schedules_data)
    }
    return render(request, 'monitoring/schedule_designer.html', context)




@login_required
def status_panel_view(request):
    widgets = DashboardWidget.objects.filter(target_page='status_panel').prefetch_related('registers')
    latest_values = {dp['register_id']: dp['value'] for dp in DataPoint.objects.order_by('register_id', '-timestamp').distinct('register_id').values('register_id', 'value')}

    for widget in widgets:
        for register in widget.registers.all():
            register.latest_value = latest_values.get(register.id)

    context = {'page_title': 'Akıllı Durum Paneli', 'widgets': widgets}
    return render(request, 'monitoring/status_panel.html', context)





@login_required
def mosaic_dashboard_view(request):
    widgets = DashboardWidget.objects.filter(target_page='mosaic_dashboard').prefetch_related('registers__device', 'registers__enum_values')

    # Sadece son değerleri ve enumları alıyoruz. Grafik için geçmiş veri hazırlamıyoruz.
    all_needed_register_ids = {r.id for w in widgets for r in w.registers.all()}
    latest_values = {dp['register_id']: dp['value'] for dp in DataPoint.objects.filter(register_id__in=all_needed_register_ids).order_by('register_id', '-timestamp').distinct('register_id').values('register_id', 'value')}
    enum_maps = {ev.id: {em.raw_value: em.label for em in ev.enum_values.all()} for ev in Register.objects.filter(display_preference='enum', id__in=all_needed_register_ids)}

    for widget in widgets:
        for register in widget.registers.all():
            register.latest_value = latest_values.get(register.id)
            if register.display_preference == 'enum' and register.latest_value is not None:
                try:
                    register.display_label = enum_maps.get(register.id, {}).get(int(register.latest_value))
                except (ValueError, TypeError):
                    register.display_label = "Hatalı Değer"

    context = {
        'page_title': 'Mozaik Pano',
        'widgets': widgets
    }
    return render(request, 'monitoring/mosaic_dashboard.html', context)






@require_POST
@login_required
def save_widget_layout_view(request):
    try:
        layout_data = json.loads(request.body)
        for item in layout_data:
            DashboardWidget.objects.filter(pk=item.get('id')).update(
                grid_x=item.get('x'),
                grid_y=item.get('y'),
                grid_width=item.get('w'),
                grid_height=item.get('h')
            )
        return JsonResponse({'status': 'success', 'message': 'Düzen kaydedildi.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)








class AvailableCoilsAPIView(APIView):
    """Zaman çizelgesine eklenmemiş, yazılabilir tüm coilleri listeler."""
    def get(self, request, format=None):
        used_register_ids = ScheduledTask.objects.values_list('register_id', flat=True)
        available_coils = Register.objects.filter(
            register_type='coil', is_writable=True
        ).exclude(id__in=used_register_ids)
        data = [{'id': coil.id, 'name': str(coil)} for coil in available_coils]
        return Response(data)

class UpdateScheduleAPIView(APIView):
    """Görsel zaman çizelgesinden gelen veriyi alıp ScheduledTask'ları günceller."""
    def post(self, request, register_id, format=None):
        events = request.data.get('events', [])
        try:
            with transaction.atomic():
                ScheduledTask.objects.filter(register_id=register_id).delete()
                for event in events:
                    # YENİ: Dakika bilgisini de al, eğer yoksa 0 olarak kabul et
                    hour = event['time']
                    minute = event.get('minute', 0)

                    ScheduledTask.objects.create(
                        register_id=register_id,
                        time_to_run=f"{hour:02d}:{minute:02d}:00", # Saati HH:MM:SS formatına getir
                        action=event['action'],
                        is_active=True
                    )       
            return Response({"status": "success", "message": "Zaman çizelgesi kaydedildi."})
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# API View'leri
class WriteCoilView(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request, register_id, format=None):
        value = request.data.get('value')
        if value is None:
            return Response({"error": "Value not provided"}, status=status.HTTP_400_BAD_REQUEST)
        write_coil_value.delay(register_id=register_id, value=bool(value))
        return Response({"status": "success", "message": "Write command sent."}, status=status.HTTP_200_OK)




@login_required
def alarm_log_view(request):
    # Eğer bir alarmı onaylamak için POST isteği geldiyse
    if request.method == 'POST':
        log_id_to_ack = request.POST.get('log_id')
        if log_id_to_ack:
            log = get_object_or_404(AlarmLog, pk=log_id_to_ack)

            # Alarmın son durumuna göre onayı işle
            if log.status == 'ACTIVE_UNACK':
                log.status = 'ACTIVE_ACK'
            elif log.status == 'CLEARED_UNACK':
                log.status = 'CLEARED_ACK'

            log.acknowledged_by = request.user
            log.acknowledged_time = timezone.now()
            log.save()
        return redirect('monitoring:alarm_log') # Sayfayı yenile

    # GET isteği için alarmları listele
    alarm_list = AlarmLog.objects.select_related('alarm_rule__register__device', 'acknowledged_by').order_by('-start_time')

    paginator = Paginator(alarm_list, 25) # Sayfa başına 25 alarm
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_title': 'Alarm Kayıtları',
        'page_obj': page_obj
    }
    return render(request, 'monitoring/alarm_log.html', context)
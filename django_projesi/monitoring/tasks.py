import logging
import time
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils import timezone
from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from .models import AlarmRule, AlarmLog, RegisterMapping

# Yeni modellerimizi import ediyoruz
from .models import DataPoint, Device, Register, TestRun, ScheduledTask

logger = logging.getLogger(__name__)
last_known_values = {} # YENİ SATIR eşleşme coili için değer tanımladık.

# --- YARDIMCI FONKSİYONLAR ---

def send_device_status(device_id, status):
    """Cihaz durumunu WebSocket kanalına gönderir."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'live_data_group',
        {'type': 'send_device_status', 'data': {'device_id': device_id, 'status': status}}
    )




def get_pdu_address(register):
    # Bu fonksiyon doğru, aynı kalıyor
    addr = register.address
    if register.register_type == 'coil' and 1 <= addr < 10000: return addr - 1
    if register.register_type == 'discrete_input' and 10001 <= addr < 20000: return addr - 10001
    if register.register_type == 'input' and 30001 <= addr < 40000: return addr - 30001
    if register.register_type == 'holding' and 40001 <= addr < 50000: return addr - 40001
    return addr

def send_websocket_message(msg_type, data):
    """WebSocket kanalına belirli bir formatta mesaj gönderir."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'live_data_group',
        {'type': msg_type, 'data': data}
    )

# --- CELERY GÖREVLERİ ---

@shared_task
def read_modbus_data():
    """Aktif bir test seansı varsa, tüm cihazları ve register'ları okur."""
    active_test_run = TestRun.objects.filter(status__in=['RUNNING', 'PAUSED']).first()
    if not active_test_run:
        return "Çalışan veya duraklatılmış test seansı bulunamadı. Veri okunmuyor."

    active_devices = Device.objects.filter(is_active=True)
    for device in active_devices:
        client = None
        try:
            client = ModbusTcpClient(device.connection_host, port=device.port, timeout=2)
            if not client.connect():
                if device.status == 'online':
                    device.status = 'offline'
                    device.save(update_fields=['status'])
                    send_device_status(device.id, 'offline')
                logger.warning(f"!!! BAĞLANTI HATASI: {device.name} cihazına bağlanılamadı.")
                continue
            
            if device.status == 'offline':
                device.status = 'online'
                device.save(update_fields=['status'])
                send_device_status(device.id, 'online')

            device.last_seen = timezone.now()
            device.save(update_fields=['last_seen'])

            for register in device.registers.all():
                try:
                    pdu_address = get_pdu_address(register)
                    value = None
                    result = None
                    
                    # --- BU BLOK TAMAMEN YENİLENİYOR ---
                    if register.register_type in ['holding', 'input']:
                        # Adım 1: Okunacak register sayısını belirle
                        if register.data_type in ['FLOAT32', 'INT32', 'UINT32']:
                            count = 2
                        elif register.data_type == 'STRING':
                            count = register.string_length
                        else:
                            count = 1
                        
                        # Adım 2: Veriyi oku
                        if register.register_type == 'holding':
                            result = client.read_holding_registers(address=pdu_address, count=count, slave=device.slave_id)
                        else:
                            result = client.read_input_registers(address=pdu_address, count=count, slave=device.slave_id)
                        
                        # Adım 3: Gelen veriyi çöz
                        if not result.isError():
                            # NOT: Bu kısım hala eski BinaryPayloadDecoder kullanıyor. 
                            # Önce çalışmasını sağlıyoruz, sonra modernize edeceğiz.
                            byteorder = Endian.BIG if register.byte_order == 'BIG' else Endian.LITTLE
                            wordorder = Endian.BIG if register.byte_order == 'BIG' else Endian.LITTLE
                            decoder = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=byteorder, wordorder=wordorder)
                            
                            # Yeni veri tiplerini de içeren if/elif bloğu
                            if register.data_type == 'STRING':
                                value = decoder.decode_string(count * 2).rstrip(b'\x00').decode('utf-8', 'ignore')
                            elif register.data_type == 'UINT16': value = decoder.decode_16bit_uint()
                            elif register.data_type == 'INT16': value = decoder.decode_16bit_int()
                            elif register.data_type == 'UINT32': value = decoder.decode_32bit_uint()
                            elif register.data_type == 'INT32': value = decoder.decode_32bit_int()
                            elif register.data_type == 'FLOAT32': value = decoder.decode_32bit_float()

                    elif register.register_type in ['coil', 'discrete_input']:
                        if register.register_type == 'coil':
                            result = client.read_coils(address=pdu_address, count=1, slave=device.slave_id)
                        else:
                            result = client.read_discrete_inputs(address=pdu_address, count=1, slave=device.slave_id)
                        
                        if not result.isError() and result.bits:
                            value = float(result.bits[0])
                    
                    # --- GÜNCELLEME BİTİŞİ ---

                    

                    if value is not None:
                        # Değeri işle (tersleme ve çarpan)
                        processed_value = value
                        is_string = isinstance(processed_value, str)

                        if not is_string:
                            if register.register_type in ['coil', 'discrete_input'] and register.invert_value:
                                processed_value = 1.0 - value
                            processed_value = processed_value * register.scaling_factor

                        # --- YENİ ENUM KONTROLÜ ---
                        display_label = None
                        if register.display_preference == 'enum' and not is_string:
                            try:
                                # Not: veritabanı sorgusunu azaltmak için bu bilgi önbelleğe alınabilir
                                enum_match = register.enum_values.filter(raw_value=int(processed_value)).first()
                                if enum_match:
                                    display_label = enum_match.label
                            except (ValueError, TypeError):
                                pass # Değer sayıya çevrilemezse yoksay
                        # --- BİTİŞ ---
                        
                    
                        # Veritabanına kaydet ve WebSocket'e gönder
                        if active_test_run:
                            # String değerleri kaydetmiyoruz, sadece sayısal olanları
                            if not is_string:
                                DataPoint.objects.create(register=register, value=processed_value, test_run=active_test_run)

                        send_websocket_message('send_live_data', {
                            'register_id': register.id, 
                            'value': processed_value, 
                            'timestamp': timezone.now().isoformat(),
                            'label': display_label # Metin etiketini de ekliyoruz
                        })
                        # --- YENİ EKLENEN ALARM KONTROLÜ ---
                        check_and_update_alarms(register, processed_value)
                        # --- BİTİŞ ---
                        # Register'ın ID'sini bir anahtar olarak kullanalım
                        register_key = str(register.id)
                        # Bu register'ın değeri gerçekten değişti mi?
                        # Önceki değeri al, eğer yoksa mevcut değerden farklı bir şey varsay
                        previous_value = last_known_values.get(register_key, None)

                        # Sadece değer değişmişse tetikleme yap
                        if processed_value != previous_value:
                            # Yeni değeri hafızaya al
                            last_known_values[register_key] = processed_value

                            # Eşleştirme kurallarını bul ve çalıştır
                            mappings = RegisterMapping.objects.filter(source_register=register, is_active=True)
                            if mappings.exists():
                                logger.info(f"==> DEĞİŞİKLİK TESPİT EDİLDİ: '{register.name}' değeri {previous_value}'dan {processed_value}'a değişti. {mappings.count()} kural çalıştırılıyor.")
                                for mapping in mappings:
                                    write_coil_value.delay(
                                        register_id=mapping.destination_register.id, 
                                        value=processed_value
                                    )
                        # --- BİTİŞ ---

                except Exception as e:
                    if device.status == 'online':
                        device.status = 'offline'
                        device.save(update_fields=['status'])
                        send_device_status(device.id, 'offline')
                    logger.error(f"!!! GENEL HATA: {device.name} işlenirken hata oluştu: {e}")

        
        finally:
            if client and client.is_socket_open():
                client.close()
        time.sleep(0.5)



def check_and_update_alarms(register, current_value):
    """Bir register için tanımlı alarmları kontrol eder ve logları günceller."""
    for rule in register.alarm_rules.filter(is_active=True):
        # Mevcut aktif (henüz bitmemiş) bir alarm var mı?
        active_log = AlarmLog.objects.filter(alarm_rule=rule, end_time__isnull=True).first()

        # Kural ihlal ediliyor mu?
        is_violated = False
        if rule.condition == 'gt' and current_value > rule.threshold: is_violated = True
        elif rule.condition == 'lt' and current_value < rule.threshold: is_violated = True
        elif rule.condition == 'eq' and current_value == rule.threshold: is_violated = True

        if is_violated:
            if not active_log:
                new_log = AlarmLog.objects.create(alarm_rule=rule, status='ACTIVE_UNACK')
                logger.warning(f"!!! YENİ ALARM ({rule.get_severity_display()}): {rule.name} !!!")
                send_websocket_message('send_alarm_update', {
                    'log_id': new_log.id, 'rule_name': rule.name,
                    'severity': rule.severity, 'status': new_log.status
                })
        else:
            if active_log:
                active_log.end_time = timezone.now()
                # DÜZELTME: Alarm aktifken onaylandıysa bile, normale döndüğünde tekrar onay bekle
                if active_log.status in ['ACTIVE_UNACK', 'ACTIVE_ACK']:
                    active_log.status = 'CLEARED_UNACK'
                active_log.save()
                logger.info(f"--- ALARM NORMALE DÖNDÜ: {rule.name} ---")
                send_websocket_message('send_alarm_update', {
                    'log_id': active_log.id, 'status': active_log.status, 'cleared': True
                })







@shared_task
def write_coil_value(register_id, value):
    """Belirli bir coil register'ına değer (True/False) yazar ve durumu yayınlar."""
    try:
        register = Register.objects.get(id=register_id, register_type='coil', is_writable=True)
        device = register.device

        client = ModbusTcpClient(device.connection_host, port=device.port, timeout=3)
        client.connect()

        pdu_address = get_pdu_address(register)

        logger.info(f"--> YAZILIYOR: Register '{register.name}' (PDU: {pdu_address}) < Değer: {value}")
        client.write_coil(address=pdu_address, value=bool(value), slave=device.slave_id)
        client.close()

        logger.info(f"BAŞARILI: '{register.name}' için değer {value} olarak yazıldı.")

        # --- YENİ EKLENEN BÖLÜM ---
        # Yazma işlemi başarılı olduğuna göre, bu yeni durumu hemen arayüze bildir.
        # Sahte bir DataPoint gibi davranarak anlık güncelleme yapıyoruz.
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'live_data_group',
            {
                'type': 'send_live_data',
                'data': {
                    'register_id': register_id,
                    'value': float(value), # True/False değerini 1.0/0.0'a çevir
                    'timestamp': timezone.now().isoformat() # O anki zamanı kullan
                }
            }
        )
        # --- BİTİŞ ---

        return {"status": "success", "message": f"Value written to {register.name}."}

    except Exception as e:
        logger.error(f"!!! YAZMA HATASI: Register ID {register_id} yazılamadı. Hata: {e}")
        return {"status": "error", "message": str(e)}



@shared_task
def check_scheduled_tasks():
    """Her dakika çalışarak ScheduledTask tablosunu kontrol eder ve görevleri tetikler."""

    # Zamanı, projenin ayarlarındaki yerel saat dilimine göre alıyoruz. Bu, en sağlam yöntemdir.
    now_local = timezone.localtime(timezone.now())

    # O anki saate ve dakikaya uyan tüm aktif görevleri bul
    tasks_to_run = ScheduledTask.objects.filter(
        is_active=True,
        time_to_run__hour=now_local.hour,
        time_to_run__minute=now_local.minute
    )

    if not tasks_to_run:
        # Bu mesajı loglarda görüyorsanız, o dakika için bir görev yok demektir.
        return "Zamanı gelmiş bir görev bulunamadı."

    logger.info(f"--- {tasks_to_run.count()} adet otomasyon görevi çalıştırılıyor ---")
    for task in tasks_to_run:
        # Herhangi bir test durumu kontrolü yapmıyoruz. Görev her zaman çalışır.
        logger.info(f"Otomasyon: {task}")
        # İlgili coil'e AÇ/KAPAT komutunu gönder
        write_coil_value.delay(register_id=task.register.id, value=task.action)

    return f"{tasks_to_run.count()} adet görev başarıyla tetiklendi."


    
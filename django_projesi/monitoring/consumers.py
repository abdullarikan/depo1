import json
from channels.generic.websocket import AsyncWebsocketConsumer

class LiveDataConsumer(AsyncWebsocketConsumer):
    """
    WebSocket bağlantılarını yöneten ve Celery'den gelen mesajları
    doğru formatta tarayıcıya ileten sınıf.
    """
    async def connect(self):
        self.group_name = "live_data_group"
        # Gruba katıl
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Gruptan ayrıl
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # 'send_live_data' tipinde bir olay geldiğinde bu fonksiyon çalışır
    async def send_live_data(self, event):
        # Tarayıcıya olayın tamamını ('type' ve 'data' dahil) JSON olarak gönder
        await self.send(text_data=json.dumps(event))

    # 'send_device_status' tipinde bir olay geldiğinde bu fonksiyon çalışır
    async def send_device_status(self, event):
        # Tarayıcıya olayın tamamını ('type' ve 'data' dahil) JSON olarak gönder
        await self.send(text_data=json.dumps(event))

    # --- YENİ EKLENECEK FONKSİYON ---
    async def send_alarm_update(self, event):
        """
        'send_alarm_update' tipindeki mesajları işler ve istemciye gönderir.
        """
        data = event["data"]
        await self.send(text_data=json.dumps({
            "type": "send_alarm_update",
            "data": data
        }))
    # --- BİTİŞ ---
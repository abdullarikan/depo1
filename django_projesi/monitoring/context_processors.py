from .models import Register, DataPoint

def status_bar_processor(request):
    """Her şablona, durum çubuğunda gösterilecek register'ları ve son değerlerini gönderir."""

    # Sadece giriş yapmış kullanıcılarda çalışsın
    if not request.user.is_authenticated:
        return {'statusbar_items': []}

    items = []
    registers_to_show = Register.objects.filter(show_on_statusbar=True, device__is_active=True).select_related('device')

    for register in registers_to_show:
        latest_datapoint = DataPoint.objects.filter(register=register).order_by('-timestamp').first()
        items.append({
            'id': register.id,
            'name': register.name,
            'icon': register.icon_name,
            'type': register.register_type,
            'value': latest_datapoint.value if latest_datapoint else None
        })

    return {'statusbar_items': items}
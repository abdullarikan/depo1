from django import forms
from .models import Device, Register, TestRun

class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['name', 'connection_host', 'port', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'connection_host': forms.TextInput(attrs={'class': 'form-control'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class RegisterForm(forms.ModelForm):
    class Meta:
        model = Register
        # Hangi alanların formda görüneceğini belirtiyoruz
        fields = ['device', 'name', 'address', 'register_type', 'is_writable', 'data_type', 'byte_order', 'min_value', 'max_value', 'icon_name', 'show_on_statusbar', 'icon_name']
        # Bootstrap sınıflarını ekleyerek formu güzelleştiriyoruz
        widgets = {
            'device': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.NumberInput(attrs={'class': 'form-control'}),
            'register_type': forms.Select(attrs={'class': 'form-select'}),
            'is_writable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'data_type': forms.Select(attrs={'class': 'form-select'}),
            'byte_order': forms.Select(attrs={'class': 'form-select'}),
            # Yeni widget'ları ekliyoruz
            'icon_name': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'show_on_statusbar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'icon_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'örn: bi-cloud-rain-fill'}),
        }


class TestRunForm(forms.ModelForm):
    class Meta:
        model = TestRun
        # Kullanıcının dolduracağı alanları belirtiyoruz
        fields = ['test_name', 'customer_name', 'product_details', 'control_coil']
        widgets = {
            'test_name': forms.TextInput(attrs={'class': 'form-control'}),
            'customer_name': forms.TextInput(attrs={'class': 'form-control'}),
            'product_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'control_coil': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'control_coil': "Test Başlat/Durdur Coili" # Etiketi daha anlaşılır yapalım
        }
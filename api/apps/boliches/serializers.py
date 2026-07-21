from rest_framework import serializers

from .models import Boliche


class BolicheSerializer(serializers.ModelSerializer):
    mp_connected = serializers.BooleanField(read_only=True)

    class Meta:
        model = Boliche
        fields = ['id', 'nombre', 'direccion', 'mp_connected', 'created_at']
        read_only_fields = ['id', 'created_at', 'mp_connected']

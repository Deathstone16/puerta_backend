from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Usuario


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extiende el serializer estándar de SimpleJWT para incluir el campo
    'rol' como claim en el JWT y como campo extra en la respuesta JSON.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Agregar claim personalizado al payload del JWT
        token['rol'] = user.rol
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Agregar campos extra a la respuesta JSON
        data['rol'] = self.user.rol
        nombre = f"{self.user.first_name} {self.user.last_name}".strip()
        data['nombre'] = nombre if nombre else self.user.username
        data['id'] = self.user.id

        # For staff roles (guardia, cajera), include their active event assignment
        if self.user.rol in ('guardia', 'cajera'):
            data['evento'] = self._get_staff_evento()
            data['evento_id'] = data['evento']['id'] if data['evento'] else None

        return data

    def _get_staff_evento(self):
        """Resolve the active event assignment for guardia/cajera."""
        from apps.cuentas.models import AsignacionStaff

        asignacion = AsignacionStaff.objects.filter(
            usuario=self.user, activa=True,
        ).select_related('evento').first()

        if not asignacion:
            return None

        evento = asignacion.evento
        return {
            'id': evento.id,
            'nombre': evento.nombre,
            'fecha': str(evento.fecha) if evento.fecha else None,
            'precio_publicado': float(evento.precio_base) if hasattr(evento, 'precio_base') else 0,
        }


class OrganizadorListSerializer(serializers.ModelSerializer):
    """Serializer para listar organizadores (rol dueño)."""

    nombre = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ['id', 'username', 'nombre', 'email', 'telefono', 'is_active', 'date_joined']
        read_only_fields = fields

    def get_nombre(self, obj):
        nombre = f"{obj.first_name} {obj.last_name}".strip()
        return nombre if nombre else obj.username


class OrganizadorCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear un organizador (usuario con rol dueño)."""

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = Usuario
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'email', 'telefono']

    def validate_username(self, value):
        if Usuario.objects.filter(username=value).exists():
            raise serializers.ValidationError('Ya existe un usuario con ese nombre de usuario.')
        return value

    def validate_email(self, value):
        if value and Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError('Ya existe un usuario con ese email.')
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = Usuario(**validated_data, rol='dueno', is_active=True)
        user.set_password(password)
        user.save()
        return user


class OrganizadorUpdateSerializer(serializers.ModelSerializer):
    """Serializer para editar un organizador."""

    password = serializers.CharField(write_only=True, min_length=8, required=False)

    class Meta:
        model = Usuario
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'email', 'telefono', 'is_active']

    def validate_username(self, value):
        if Usuario.objects.filter(username=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('Ya existe un usuario con ese nombre de usuario.')
        return value

    def validate_email(self, value):
        if value and Usuario.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('Ya existe un usuario con ese email.')
        return value

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

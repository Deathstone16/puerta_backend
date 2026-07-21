from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


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
        return data

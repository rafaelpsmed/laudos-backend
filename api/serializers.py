from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Metodo, ModeloLaudo, Frase, Variavel

CustomUser = get_user_model()

class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'password', 'nome_completo', 'telefone']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        validated_data['username'] = validated_data['email']
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            nome_completo=validated_data['nome_completo'],
            telefone=validated_data['telefone'],
            username=validated_data['username']
        )
        return user

class MetodoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Metodo
        fields = ['id', 'metodo']

class ModeloLaudoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeloLaudo
        fields = ['id', 'titulo', 'texto', 'metodo', 'usuario', 'criado_em', 'atualizado_em']
        read_only_fields = ['usuario', 'criado_em', 'atualizado_em']

class FraseSerializer(serializers.ModelSerializer):
    modelos_laudo = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=ModeloLaudo.objects.all(),
        required=False
    )

    class Meta:
        model = Frase
        fields = ['id', 'categoriaFrase', 'tituloFrase', 'frase', 'modelos_laudo', 'usuario', 'criado_em', 'atualizado_em']
        read_only_fields = ['usuario', 'criado_em', 'atualizado_em']

class VariavelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variavel
        fields = ['id', 'tituloVariavel', 'variavel', 'usuario', 'criado_em', 'atualizado_em']
        read_only_fields = ['usuario', 'criado_em', 'atualizado_em']

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        try:
            user = CustomUser.objects.get(email=data['email'])
            if user.check_password(data['password']):
                if user.is_active:
                    return user
                else:
                    raise serializers.ValidationError("Usuário inativo.")
            else:
                raise serializers.ValidationError("Senha incorreta.")
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Usuário não encontrado.")
        except Exception as e:
            raise serializers.ValidationError(f"Erro durante login: {str(e)}") 
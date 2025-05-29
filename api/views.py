from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Metodo, ModeloLaudo, Frase, Variavel
from .serializers import (
    MetodoSerializer, ModeloLaudoSerializer,
    FraseSerializer, VariavelSerializer, LoginSerializer, CustomUserSerializer
)

# Create your views here.

class MetodoViewSet(viewsets.ModelViewSet):
    queryset = Metodo.objects.all()
    serializer_class = MetodoSerializer
    permission_classes = [permissions.IsAuthenticated]

class ModeloLaudoViewSet(viewsets.ModelViewSet):
    queryset = ModeloLaudo.objects.all()
    serializer_class = ModeloLaudoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

class FraseViewSet(viewsets.ModelViewSet):
    queryset = Frase.objects.all()
    serializer_class = FraseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    def get_queryset(self):
        queryset = Frase.objects.all()
        categoria = self.request.query_params.get('categoria', None)
        titulo_frase = self.request.query_params.get('titulo_frase', None)
        
        if categoria and titulo_frase:
            queryset = queryset.filter(
                categoriaFrase=categoria,
                tituloFrase=titulo_frase
            )
            
        return queryset

    @action(detail=False, methods=['get'])
    def categorias_sem_metodos(self, request):
        try:
            # Busca categorias que não têm frases associadas a nenhum modelo
            categorias = Frase.objects.filter(
                modelos_laudo__isnull=True
            ).values_list(
                'categoriaFrase', 
                flat=True
            ).distinct()
            
            return Response({
                'categorias': list(categorias)
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def categorias(self, request):
        modelo_laudo_id = request.query_params.get('modelo_laudo_id', None)
        
        if not modelo_laudo_id:
            return Response(
                {'error': 'modelo_laudo_id é obrigatório'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Busca categorias que têm frases associadas ao modelo
            categorias = Frase.objects.filter(
                modelos_laudo__id=modelo_laudo_id
            ).values_list(
                'categoriaFrase', 
                flat=True
            ).distinct()
            
            return Response({
                'categorias': list(categorias)
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def titulos_frases(self, request):
        categoria = request.query_params.get('categoria', None)
        modelo_laudo_id = request.query_params.get('modelo_laudo_id', None)
        
        if not categoria:
            return Response(
                {'error': 'categoria é obrigatória'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Busca títulos que têm frases na categoria especificada
            queryset = Frase.objects.filter(categoriaFrase=categoria)
            
            if modelo_laudo_id:
                queryset = queryset.filter(modelo_laudo_id=modelo_laudo_id)
                
            titulos = queryset.values_list('tituloFrase', flat=True).distinct()
            
            return Response({
                'titulos_frases': list(titulos)
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def frases(self, request):
        titulo_frase = request.query_params.get('titulo_frase', None)
        categoria = request.query_params.get('categoria', None)
        
        if not titulo_frase or not categoria:
            return Response(
                {'error': 'titulo_frase e categoria são obrigatórios'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Busca frases com os filtros especificados
            queryset = Frase.objects.filter(
                tituloFrase=titulo_frase,
                categoriaFrase=categoria
            )
                
            # Serializa as frases encontradas
            serializer = self.get_serializer(queryset, many=True)
            
            return Response({
                'frases': serializer.data
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VariavelViewSet(viewsets.ModelViewSet):
    queryset = Variavel.objects.all()
    serializer_class = VariavelSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    def get_queryset(self):
        queryset = Variavel.objects.all()
        titulo = self.request.query_params.get('tituloVariavel', None)
        if titulo is not None:
            queryset = queryset.filter(tituloVariavel=titulo)
        return queryset

class AuthViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = CustomUserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'nome_completo': user.nome_completo
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'nome_completo': user.nome_completo
                }
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def me(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Usuário não autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
        
        return Response({
            'id': request.user.id,
            'email': request.user.email,
            'nome_completo': request.user.nome_completo
        })

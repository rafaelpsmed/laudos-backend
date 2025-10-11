from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import Metodo, ModeloLaudo, Frase, Variavel
from .serializers import (
    MetodoSerializer, ModeloLaudoSerializer,
    FraseSerializer, VariavelSerializer, LoginSerializer, CustomUserSerializer
)
from .services import generate_radiology_report

# Create your views here.

class MetodoViewSet(viewsets.ModelViewSet):
    queryset = Metodo.objects.all()
    serializer_class = MetodoSerializer
    permission_classes = [permissions.IsAuthenticated]

class ModeloLaudoViewSet(viewsets.ModelViewSet):
    serializer_class = ModeloLaudoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Retorna apenas os modelos do usuário logado
        return ModeloLaudo.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

class FraseViewSet(viewsets.ModelViewSet):
    serializer_class = FraseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    def get_queryset(self):
        # Retorna apenas as frases do usuário logado
        queryset = Frase.objects.filter(usuario=self.request.user)
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
                queryset = queryset.filter(modelos_laudo__id=modelo_laudo_id)
                
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

    @action(detail=False, methods=['POST'], permission_classes=[permissions.IsAuthenticated], url_path='gerenciar-entre-modelos')
    def gerenciar_entre_modelos(self, request):
        """
        Gerencia frases entre modelos de laudo.
        Suporta três modos: copiar, mover e duplicar.
        """
        modelo_origem_id = request.data.get('modelo_origem_id')
        modelo_destino_id = request.data.get('modelo_destino_id')
        frases_ids = request.data.get('frases_ids', [])
        modo_operacao = request.data.get('modo_operacao')  # 'copiar', 'mover' ou 'duplicar'
        
        # Validações básicas
        if not modelo_origem_id or not modelo_destino_id:
            return Response(
                {'error': 'modelo_origem_id e modelo_destino_id são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not frases_ids or not isinstance(frases_ids, list):
            return Response(
                {'error': 'frases_ids deve ser uma lista não vazia'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if modo_operacao not in ['copiar', 'mover', 'duplicar']:
            return Response(
                {'error': 'modo_operacao deve ser "copiar", "mover" ou "duplicar"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if modelo_origem_id == modelo_destino_id:
            return Response(
                {'error': 'Modelo de origem e destino devem ser diferentes'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Verifica se os modelos existem e pertencem ao usuário
            modelo_origem = ModeloLaudo.objects.filter(
                id=modelo_origem_id,
                usuario=request.user
            ).first()
            
            modelo_destino = ModeloLaudo.objects.filter(
                id=modelo_destino_id,
                usuario=request.user
            ).first()
            
            if not modelo_origem:
                return Response(
                    {'error': 'Modelo de origem não encontrado ou você não tem permissão'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if not modelo_destino:
                return Response(
                    {'error': 'Modelo de destino não encontrado ou você não tem permissão'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Busca as frases que pertencem ao modelo de origem
            frases = Frase.objects.filter(
                id__in=frases_ids,
                modelos_laudo=modelo_origem,
                usuario=request.user
            )
            
            if frases.count() != len(frases_ids):
                return Response(
                    {'error': 'Algumas frases não foram encontradas ou não pertencem ao modelo de origem'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Estatísticas da operação
            stats = {
                'total_frases': len(frases_ids),
                'processadas': 0,
                'ja_existiam': 0,
                'duplicadas': 0,
                'erros': []
            }
            
            # Executa a operação baseada no modo
            if modo_operacao == 'copiar':
                # COPIAR: Mantém no modelo origem e adiciona ao modelo destino
                for frase in frases:
                    if modelo_destino in frase.modelos_laudo.all():
                        stats['ja_existiam'] += 1
                    else:
                        frase.modelos_laudo.add(modelo_destino)
                        stats['processadas'] += 1
            
            elif modo_operacao == 'mover':
                # MOVER: Remove do modelo origem e adiciona ao modelo destino
                for frase in frases:
                    frase.modelos_laudo.remove(modelo_origem)
                    if modelo_destino not in frase.modelos_laudo.all():
                        frase.modelos_laudo.add(modelo_destino)
                    stats['processadas'] += 1
            
            elif modo_operacao == 'duplicar':
                # DUPLICAR: Cria cópias independentes e vincula ao modelo destino
                for frase in frases:
                    nova_frase = Frase.objects.create(
                        categoriaFrase=frase.categoriaFrase,
                        tituloFrase=frase.tituloFrase,
                        frase=frase.frase,
                        usuario=request.user
                    )
                    nova_frase.modelos_laudo.add(modelo_destino)
                    stats['duplicadas'] += 1
                    stats['processadas'] += 1
            
            # Mensagem de sucesso
            mensagem = self._gerar_mensagem_sucesso(modo_operacao, stats)
            
            return Response({
                'success': True,
                'mensagem': mensagem,
                'estatisticas': stats
            })
        
        except Exception as e:
            return Response(
                {'error': f'Erro ao processar operação: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _gerar_mensagem_sucesso(self, modo_operacao, stats):
        """Gera mensagem de sucesso personalizada baseada no modo e estatísticas"""
        if modo_operacao == 'copiar':
            mensagem = f"Operação concluída! {stats['processadas']} frase(s) copiada(s) com sucesso."
            if stats['ja_existiam'] > 0:
                mensagem += f" {stats['ja_existiam']} frase(s) já existia(m) no modelo de destino."
        
        elif modo_operacao == 'mover':
            mensagem = f"Operação concluída! {stats['processadas']} frase(s) movida(s) com sucesso."
        
        elif modo_operacao == 'duplicar':
            mensagem = f"Operação concluída! {stats['duplicadas']} frase(s) duplicada(s) com sucesso."
        
        return mensagem

    @action(detail=False, methods=['get'])
    def por_modelo(self, request):
        """
        Retorna todas as frases associadas a um modelo de laudo específico.
        Útil para a interface de transferência de frases.
        """
        modelo_laudo_id = request.query_params.get('modelo_laudo_id')
        
        if not modelo_laudo_id:
            return Response(
                {'error': 'modelo_laudo_id é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Verifica se o modelo existe e pertence ao usuário
            modelo = ModeloLaudo.objects.filter(
                id=modelo_laudo_id,
                usuario=request.user
            ).first()
            
            if not modelo:
                return Response(
                    {'error': 'Modelo de laudo não encontrado ou você não tem permissão'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Busca frases associadas ao modelo
            frases = Frase.objects.filter(
                modelos_laudo=modelo,
                usuario=request.user
            ).order_by('categoriaFrase', 'tituloFrase')
            
            serializer = self.get_serializer(frases, many=True)
            
            return Response({
                'frases': serializer.data,
                'total': frases.count()
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VariavelViewSet(viewsets.ModelViewSet):
    serializer_class = VariavelSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    def get_queryset(self):
        # Retorna apenas as variáveis do usuário logado
        queryset = Variavel.objects.filter(usuario=self.request.user)
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

    @action(detail=False, methods=['post'])
    def refresh(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {'error': 'Refresh token é obrigatório'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Valida o refresh token
            refresh = RefreshToken(refresh_token)
            
            # Gera um novo access token
            access_token = refresh.access_token
            
            return Response({
                'access': str(access_token),
                'refresh': str(refresh)
            })
            
        except TokenError as e:
            return Response(
                {'error': 'Token inválido ou expirado'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class IAViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def gerar_laudo_radiologia(self, request):
        """
        Gera laudo radiológico usando IA baseada nas informações fornecidas
        """
        texto = request.data.get('texto', '').strip()

        if not texto:
            return Response(
                {'error': 'Texto com informações do exame é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Prompt específico para laudos radiológicos conforme solicitado
            prompt = f"""
            Sou Radiologista e quero que vc me ajude a agilizar a minha confecção de laudos. Quando eu pedir para vc fazer um laudo, ele deve vim nesse formato:
            Fonte de todo o texto: Arial 12
            Se eu falar o nome do paciente, vc coloca antes de tudo Nome: e o nome que eu falar. Se eu não falar nada, não precisa colocar
            Titulo em Negrito e Maiúsculo, centralizado
            Depois vc escreve Indicação Clínica em negrito e maíusculo. Se nenhuma indicação for fornecida, vc coloca "Avaliação Clínica"
            para colocar a técnica do exame, vc escreve TÉCNICA em negrito e maiúsculo, dois pontos e depois escreve a técnica do exame. em exames de ultrassonografia, descrever a técnica em modo B e apenas citar o uso ou não do estudo com doppler se for mencionado.
            Depois coloca laudo: , em maiúsculo e negrito
            No laudo deve ser colocada a descrição de todas as estruturas que a região estudada contém, e não apenas as alterações.
            Depois o laudo, sem hífens ou bullets nos parágrafos. se for preciso, usar numeros para enumerar achados.
            Depois vc escreve impressão diagnóstica: em negrito e maiúsculo e depois faz um resumo dos achados do laudo.
            Cada achado deve ficar em uma linha separada e não é preciso repetir as medidas do achado na conclusão.
            Na conclusão não é para colocar nenhuma medida

            Considerações específicas para cada laudo:
            1. Em laudos de ultrassonografia de mamas, as descrições dos nódulos devem seguir o léxico do birads. Deve-se colocar, abaixo da conclusão: BI-RADS: X (X é o birads do exame de acordo com os achados). Abaixo disso colocar as Recomendações de acordo com o BIRADS e com o documento do ACR BIRADS
            2. não é para falar nada de próstata em ultrassonografia do aparelho urinário exceto se for dito o contrário
            3. não falar de ligamentos cruzados e meniscos em ultrassonografia de joelho

            Informações fornecidas pelo médico:
            {texto}

            Gere o laudo radiológico completo seguindo rigorosamente o formato especificado acima.
            """

            # Gera o laudo usando o serviço de IA
            laudo_gerado = generate_radiology_report(prompt, service_name="openrouter")

            if laudo_gerado and not laudo_gerado.startswith("Erro"):
                return Response({
                    'laudo': laudo_gerado
                })
            else:
                return Response(
                    {'error': laudo_gerado or 'Erro ao gerar laudo radiológico'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            print(f"Erro ao gerar laudo radiológico: {e}")
            return Response(
                {'error': 'Erro interno do servidor ao gerar laudo'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

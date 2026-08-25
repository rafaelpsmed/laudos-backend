from django.shortcuts import render
import logging
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import Metodo, ModeloLaudo, Frase, Variavel
from .serializers import (
    MetodoSerializer, ModeloLaudoSerializer,
    FraseSerializer, VariavelSerializer, LoginSerializer, CustomUserSerializer
)
from .services import (
    generate_or_edit_radiology_report,
    GroqService,
    APIKeyMissingError,
    ia_error_http_status,
    normalize_chat_history,
    get_frases_for_modelo,
    build_frase_catalog_entry,
    match_frases_from_chat,
)
from .models import ModeloLaudo

logger = logging.getLogger(__name__)

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

    def update(self, request, *args, **kwargs):
        """
        Atualiza uma variável e, se o título mudou, atualiza todas as frases
        que usam essa variável.
        """
        instance = self.get_object()
        titulo_antigo = instance.tituloVariavel
        titulo_novo = request.data.get('tituloVariavel', titulo_antigo)
        
        # Chama o método update padrão
        response = super().update(request, *args, **kwargs)
        
        # Se o título mudou, atualiza todas as frases que usam essa variável
        if titulo_antigo != titulo_novo and response.status_code == status.HTTP_200_OK:
            try:
                frases_atualizadas = self._atualizar_frases_com_variavel(
                    titulo_antigo, 
                    titulo_novo, 
                    request.user
                )
                
                # Adiciona informação sobre as frases atualizadas na resposta
                response.data['frases_atualizadas'] = frases_atualizadas
                response.data['mensagem'] = (
                    f'Variável atualizada com sucesso! '
                    f'{frases_atualizadas} frase(s) foram atualizada(s) automaticamente.'
                )
            except Exception as e:
                # Log do erro mas não falha a atualização da variável
                # print(f'Erro ao atualizar frases com variável: {e}')
                response.data['aviso'] = (
                    'Variável atualizada, mas houve um erro ao atualizar as frases. '
                    'Algumas frases podem ainda usar o título antigo.'
                )
        
        return response

    def _atualizar_frases_com_variavel(self, titulo_antigo, titulo_novo, usuario):
        """
        Atualiza todas as frases do usuário que contêm a variável com o título antigo.
        Retorna o número de frases atualizadas.
        """
        # Padrão a ser procurado: {tituloAntigo}
        padrao_antigo = f'{{{titulo_antigo}}}'
        padrao_novo = f'{{{titulo_novo}}}'
        
        # Busca todas as frases do usuário
        frases = Frase.objects.filter(usuario=usuario)
        
        frases_atualizadas = 0
        
        for frase in frases:
            # Verifica se a frase contém o padrão antigo no campo fraseBase
            frase_base = frase.frase.get('fraseBase', '')
            
            if padrao_antigo in frase_base:
                # Substitui todas as ocorrências do padrão antigo pelo novo
                nova_frase_base = frase_base.replace(padrao_antigo, padrao_novo)
                
                # Atualiza o campo fraseBase
                frase.frase['fraseBase'] = nova_frase_base
                frase.save()
                
                frases_atualizadas += 1
        
        return frases_atualizadas

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
        Gera ou edita laudo radiológico usando IA.
        Se laudo_atual estiver presente, aplica edição incremental.
        """
        texto = request.data.get('texto', '').strip()
        laudo_atual = request.data.get('laudo_atual', '').strip()
        historico = normalize_chat_history(request.data.get('historico'))
        modo_catalogo = bool(request.data.get('modo_catalogo'))
        frases_aplicadas = request.data.get('frases_aplicadas') or []
        pedido_complementar = request.data.get('pedido_complementar', '').strip()

        if not texto:
            return Response(
                {'error': 'Texto com informações do exame é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            laudo_gerado, modo = generate_or_edit_radiology_report(
                user_text=texto,
                laudo_atual=laudo_atual,
                historico=historico,
                service_name="openrouter",
                modo_catalogo=modo_catalogo,
                frases_aplicadas=frases_aplicadas,
                pedido_complementar=pedido_complementar,
            )

            if laudo_gerado and not laudo_gerado.startswith("Erro"):
                payload = {
                    'laudo': laudo_gerado,
                    'modo': modo,
                }
                if modo_catalogo:
                    payload['acrescimos'] = laudo_gerado
                    payload['modo'] = 'complementar'
                return Response(payload)

            error_msg = laudo_gerado or 'Erro ao gerar laudo radiológico'
            return Response(
                {'error': error_msg.replace('Erro: ', '', 1) if error_msg.startswith('Erro: ') else error_msg},
                status=ia_error_http_status(error_msg),
            )

        except APIKeyMissingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            logger.exception("Erro ao gerar laudo radiológico")
            return Response(
                {'error': 'Erro interno do servidor ao gerar laudo'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def resolver_frases(self, request):
        """
        Interpreta pedido do chat e retorna IDs de frases cadastradas a aplicar.
        """
        modelo_id = request.data.get('modelo_id')
        texto = request.data.get('texto', '').strip()
        historico = normalize_chat_history(request.data.get('historico'))

        if not modelo_id:
            return Response(
                {'error': 'modelo_id é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not texto:
            return Response(
                {'error': 'Texto do pedido é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            modelo = ModeloLaudo.objects.get(id=modelo_id, usuario=request.user)
        except ModeloLaudo.DoesNotExist:
            return Response(
                {'error': 'Modelo não encontrado'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            frases = get_frases_for_modelo(request.user, modelo)
            catalog = [build_frase_catalog_entry(f) for f in frases]
            catalog_by_id = {f.id: f for f in frases}

            resultado = match_frases_from_chat(
                user_text=texto,
                catalog_entries=catalog,
                historico=historico,
                service_name='openrouter',
            )

            if resultado.get('error'):
                return Response(
                    {'error': resultado['error']},
                    status=ia_error_http_status(resultado['error']),
                )

            frases_resposta = []
            for item in resultado.get('frases', []):
                frase_obj = catalog_by_id.get(item['id'])
                if not frase_obj:
                    continue
                frases_resposta.append({
                    **item,
                    'tituloFrase': frase_obj.tituloFrase,
                    'categoriaFrase': frase_obj.categoriaFrase,
                    'frase': frase_obj.frase,
                })

            return Response({
                'frases': frases_resposta,
                'pedido_complementar': resultado.get('pedido_complementar', ''),
                'mensagem_assistente': resultado.get('mensagem_assistente', ''),
                'catalogo_total': len(catalog),
            })

        except APIKeyMissingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            logger.exception('Erro ao resolver frases')
            return Response(
                {'error': 'Erro interno ao interpretar frases'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['post'])
    def corrigir_texto(self, request):
        """
        Corrige texto transcrito usando Groq
        Especializado em correção de transcrições de laudos médicos radiológicos
        """
        texto = request.data.get('texto', '').strip()
        deve_capitalizar = request.data.get('deve_capitalizar', False)

        if not texto:
            return Response(
                {'error': 'Texto é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            groq_service = GroqService()
            texto_corrigido = groq_service.correct_text(texto, deve_capitalizar)

            if texto_corrigido:
                return Response({
                    'texto_corrigido': texto_corrigido
                })
            else:
                detail = groq_service.api_error_message()
                return Response(
                    {'error': detail},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        except APIKeyMissingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Erro ao corrigir texto")
            return Response(
                {'error': 'Erro interno do servidor ao corrigir texto'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def transcrever_audio(self, request):
        """
        Transcreve áudio com Groq whisper-large-v3-turbo.
        Motor paralelo ao Web Speech API (Google) do frontend.
        """
        audio = request.FILES.get('audio')
        if not audio:
            return Response(
                {'error': 'Arquivo de áudio é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_bytes = 25 * 1024 * 1024
        if audio.size > max_bytes:
            return Response(
                {'error': 'Áudio excede o limite de 25MB'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            groq_service = GroqService()
            texto = groq_service.transcribe_audio(
                audio.read(),
                filename=audio.name or 'audio.webm',
                content_type=audio.content_type or 'audio/webm',
            )

            if texto:
                return Response({'texto': texto})

            detail = groq_service.api_error_message()
            return Response(
                {'error': detail},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except APIKeyMissingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            logger.exception("Erro ao transcrever áudio")
            return Response(
                {'error': 'Erro interno do servidor ao transcrever áudio'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

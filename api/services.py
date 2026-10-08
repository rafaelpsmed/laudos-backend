"""
Serviços para integração com APIs de IA
"""
import json
import logging
import re
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

MAX_CHAT_HISTORY = 10

RADIOLOGY_REPORT_RULES = """
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
Na conclusão não é para colocar nenhuma medida.

Considerações específicas para cada laudo:
1. Em laudos de ultrassonografia de mamas, as descrições dos nódulos devem seguir o léxico do birads. Deve-se colocar, abaixo da conclusão: BI-RADS: X (X é o birads do exame de acordo com os achados). Abaixo disso colocar as Recomendações de acordo com o BIRADS e com o documento do ACR BIRADS
2. não é para falar nada de próstata em ultrassonografia do aparelho urinário exceto se for dito o contrário
3. não falar de ligamentos cruzados e meniscos em ultrassonografia de joelho
""".strip()

RADIOLOGY_EDIT_RULES = """
Regras de edição:
1. O laudo abaixo é a versão atual — não invente achados novos salvo se o usuário pedir explicitamente.
2. Aplique SOMENTE as alterações solicitadas pelo usuário.
3. Não reescreva seções não mencionadas no pedido.
4. Retorne o laudo COMPLETO atualizado (não diff, sem comentários ou explicações).
5. Preserve medidas, BI-RADS e formatação já corretos.
6. Se o pedido for ambíguo, prefira a alteração mínima necessária.
7. Mantenha a estrutura: título, indicação clínica, técnica, laudo, impressão diagnóstica.
""".strip()

CATALOGO_COMPLEMENTO_RULES = """
Modo catálogo — complemento APÓS frases padronizadas já inseridas no laudo:

PRIORIDADE ABSOLUTA: NÃO ALTERAR O QUE JÁ ESTÁ NO LAUDO
8. O "Laudo atual" contém frases do catálogo com variáveis JÁ preenchidas — esse texto é DEFINITIVO.
9. PROIBIDO alterar, reescrever, parafrasear, corrigir ortografia, trocar sinônimos ou substituir
   QUALQUER trecho que já exista no laudo atual (ex.: descrição de esteatose já inserida).
10. PROIBIDO usar o pedido de complemento para redescrever achados já presentes no laudo
    por frase cadastrada — considere essa parte do pedido original como JÁ ATENDIDA.
11. Sua ÚNICA tarefa nesta etapa: ACRESCENTAR texto novo para o que ainda NÃO consta no laudo
    (ex.: medidas renais, dimensões, achados avulsos sem frase cadastrada).
12. Preserve o laudo atual palavra por palavra nos trechos existentes; insira apenas linhas/parágrafos
    novos nos locais anatômicos adequados (ex.: após fígado, descrever rins).
13. Se o complemento pedir medidas renais e o laudo já descreve esteatose, mantenha a esteatose
    exatamente como está e adicione somente as medidas renais.
14. Não duplique achados. Não remova conteúdo existente.
15. Retorne o laudo completo = laudo atual (inalterado) + acréscimos necessários.

IMPORTANTE — FORMATO DA RESPOSTA NESTA ETAPA:
16. Retorne APENAS o texto NOVO a acrescentar (acréscimos), em texto puro.
17. NÃO retorne o laudo completo. NÃO repita trechos já presentes no laudo atual.
18. Sem markdown, sem cabeçalhos (título, técnica, impressão). Apenas parágrafos/linhas novos.
""".strip()


class APIKeyMissingError(ValueError):
    """Chave de API ausente ou placeholder no .env."""


def _normalize_api_key(api_key):
    """Retorna None se a chave estiver vazia ou for placeholder de template."""
    if not api_key or not str(api_key).strip():
        return None
    key = str(api_key).strip()
    if key.startswith('your_') or key.endswith('_here'):
        return None
    return key


class AIService:
    """Classe base para serviços de IA"""

    def __init__(self, api_key, base_url=None, service_name="ai"):
        self.service_name = service_name
        self.last_error = None
        normalized_key = _normalize_api_key(api_key)
        if not normalized_key:
            raise APIKeyMissingError(
                f"Chave de API não configurada para {service_name}. "
                f"Defina a variável correspondente em laudos_backend/.env e reinicie o servidor."
            )
        self.api_key = normalized_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        })

    def make_request(self, endpoint, data, method='POST'):
        """Faz uma requisição para a API"""
        self.last_error = None
        try:
            url = f"{self.base_url}/{endpoint}" if self.base_url else endpoint
            response = self.session.request(method, url, json=data, timeout=120)

            if response.status_code == 200:
                return response.json()

            self.last_error = f"HTTP {response.status_code}: {response.text[:500]}"
            logger.warning("Falha na API %s: %s", self.service_name, self.last_error)
            return None

        except requests.RequestException as e:
            self.last_error = str(e)
            logger.exception("Erro na requisição %s", self.service_name)
            return None

    def api_error_message(self):
        if self.last_error:
            return f"Erro na API {self.service_name}: {self.last_error}"
        return f"Erro na API {self.service_name}: resposta vazia ou inválida"


class OpenAIService(AIService):
    """Serviço para integração com OpenAI"""

    def __init__(self):
        super().__init__(
            api_key=settings.OPENAI_API_KEY,
            base_url="https://api.openai.com/v1",
            service_name="OpenAI",
        )

    def generate_text(self, prompt, model="gpt-3.5-turbo", max_tokens=1000):
        """Gera texto usando GPT"""
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        response = self.make_request("chat/completions", data)

        if response and 'choices' in response:
            return response['choices'][0]['message']['content']
        return None


class OpenRouterService(AIService):
    """Serviço para integração com OpenRouter"""

    def __init__(self):
        super().__init__(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            service_name="OpenRouter",
        )
    # teste de modelos
    # anthropic/claude-3.7-sonnet - melhor até agora, porem caro
    # anthropic/claude-sonnet-4 - melhor até agora, porem caro
    # deepseek/deepseek-chat-v3.1 - bom; free
    # deepseek/deepseek-chat-v3-0324 - não ficou bom
    # deepseek/deepseek-chat-v3.1 - não ficou bom
    # openai/gpt-4.1-mini - não ficou bom
    # moonshotai/kimi-k2-0905 - bom, porem precisa de ajuste no prompt pq gera o texto todo junto

    def chat(self, messages, model="anthropic/claude-sonnet-4", max_tokens=20000, temperature=0.7):
        """Gera texto usando OpenRouter com conversa multi-turn."""
        data = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        response = self.make_request("chat/completions", data)

        if response and 'choices' in response:
            return response['choices'][0]['message']['content']
        return None

    def generate_text(self, prompt, model="anthropic/claude-sonnet-4", max_tokens=20000):
        """Gera texto usando OpenRouter"""
        return self.chat(
            [{"role": "user", "content": prompt}],
            model=model,
            max_tokens=max_tokens,
        )


class AnthropicService(AIService):
    """Serviço para integração com Anthropic/Claude"""

    def __init__(self):
        super().__init__(
            api_key=settings.ANTHROPIC_API_KEY,
            base_url="https://api.anthropic.com/v1",
            service_name="Anthropic",
        )

    def generate_text(self, prompt, model="claude-3-haiku-20240307", max_tokens=1000):
        """Gera texto usando Claude"""
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        response = self.make_request("messages", data)

        if response and 'content' in response:
            return response['content'][0]['text']
        return None


class GroqService(AIService):
    """Serviço para integração com Groq"""

    def __init__(self):
        super().__init__(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            service_name="Groq",
        )

    def correct_text(self, texto, deve_capitalizar=False):
        """
        Corrige texto transcrito usando Groq
        Especializado em correção de transcrições de laudos médicos radiológicos
        """
        system_prompt = """Você é um assistente especialista em corrigir transcrições de laudos médicos radiológicos em português. 
Sua tarefa é apenas pontuar corretamente, e corrigir a gramática e os termos técnicos radiológicos do texto fornecido.
Regras:
1. NÃO adicione nenhum texto extra, explicação ou "Aqui está". Retorne APENAS o texto corrigido.
2. Mantenha o sentido técnico médico e radiológico.
3. Insira vírgulas, pontos e outros sinais de pontuação onde gramaticalmente necessário.
4. As medidas devem ser em centímetros, a menos que seja especificado outro tipo de medida, e devem estar no seguinte formato: A x B cm (A e B são as medidas). Ordenar as medidas da maior para a menor.
5. Se o usuário pedir uma descrição detalhada de uma estrutura ou alteração patológica, deve ser colocada a descrição detalhada da estrutura e/ou da alteração.
6. {capitalizacao}"""

        capitalizacao_texto = 'Comece a frase com letra Maiúscula.' if deve_capitalizar else 'Mantenha a caixa alta/baixa original da primeira palavra, a menos que seja nome próprio.'
        system_prompt = system_prompt.format(capitalizacao=capitalizacao_texto)

        data = {
            "model": "openai/gpt-oss-120b",
            # "model": "whisper-large-v3-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": texto
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1024
        }

        response = self.make_request("chat/completions", data)

        if response and 'choices' in response and len(response['choices']) > 0:
            return response['choices'][0]['message']['content'].strip()
        return None

    def transcribe_audio(self, audio_bytes, filename="audio.webm", content_type="audio/webm"):
        """
        Transcreve áudio com Groq Whisper (whisper-large-v3-turbo).
        Multipart separado do chat JSON — não usa a session com Content-Type application/json.
        """
        self.last_error = None
        url = f"{self.base_url}/audio/transcriptions"
        files = {
            "file": (filename, audio_bytes, content_type or "application/octet-stream"),
        }
        data = {
            "model": "whisper-large-v3-turbo",
            "language": "pt",
            "response_format": "json",
            "temperature": "0",
            "prompt": (
                "Laudo radiológico em português. "
                "fígado, pâncreas, baço, rim, pulmão, coração, vesícula biliar, "
                "nódulo, cisto, lesão, calcificação, hipodenso, hiperdenso, "
                "tomografia, ressonância, ultrassom, centímetros."
            ),
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            response = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=120,
            )
            if response.status_code == 200:
                payload = response.json()
                texto = (payload.get("text") or "").strip()
                return texto or None

            self.last_error = f"HTTP {response.status_code}: {response.text[:500]}"
            logger.warning("Falha na transcrição Groq Whisper: %s", self.last_error)
            return None
        except requests.RequestException as e:
            self.last_error = str(e)
            logger.exception("Erro na transcrição Groq Whisper")
            return None


def get_ai_service(service_name="openai"):
    """
    Retorna o serviço de IA apropriado baseado na configuração
    """
    services = {
        "openai": OpenAIService,
        "openrouter": OpenRouterService,
        "anthropic": AnthropicService
    }

    service_class = services.get(service_name.lower())
    if not service_class:
        raise ValueError(f"Serviço '{service_name}' não suportado")

    return service_class()


def generate_medical_text(prompt, service_name="openrouter", use_medical_context=True):
    """
    Função principal para gerar texto médico usando IA
    """
    try:
        service = get_ai_service(service_name)

        # Cache para evitar chamadas desnecessárias
        cache_key = f"ai_response_{hash(prompt + service_name)}"
        cached_response = cache.get(cache_key)

        if cached_response:
            return cached_response

        final_prompt = prompt
        if use_medical_context:
            # Prompt específico para contexto médico
            final_prompt = f"""
            Contexto: {prompt}
            Retorne o texto em Markdown com as respectivas formatações.

            Usando o contexto acima, gere o laudo radiológico completo seguindo rigorosamente as instruções abaixo:            
            Fonte do texto: Arial 12      
            Titulo do laudo em Negrito e Maiúsculo, centralizado
            Depois vc escreve Indicação Clínica em negrito e maíusculo. Se nenhuma indicação for fornecida, vc coloca "Avaliação Clínica"
            para colocar a técnica do exame, vc escreve TÉCNICA em negrito e maiúsculo, dois pontos e depois escreve a técnica do exame. em exames de ultrassonografia, descrever a técnica em modo B e apenas citar o uso ou não do estudo com doppler se for mencionado. 
            Depois coloca laudo: , em maiúsculo e negrito
            No laudo deve ser colocada a descrição de todas as estruturas que a região estudada contém, e não apenas as alterações.
            Depois o laudo, sem hífens ou bullets nos parágrafos. se for preciso, usar numeros para enumerar achados.
            Depois vc escreve impressão diagnóstica: em negrito e maiúsculo e depois faz um resumo dos achados do laudo. 
            Cada achado deve ficar em uma linha separada e não é preciso repetir as medidas do achado na conclusão.
            Na conclusão não é para colocar nenhuma medida.

            


            Considerações específicas para cada laudo:
            1. Em laudos de ultrassonografia de mamas, as descrições dos nódulos devem seguir o léxico do birads. Deve-se colocar, abaixo da conclusão: BI-RADS: X (X é o birads do exame de acordo com os achados). Abaixo disso colocar as Recomendações de acordo com o BIRADS e com o documento do ACR BIRADS
            2. não é para falar nada de próstata em ultrassonografia do aparelho urinário exceto se for dito o contrário
            3. não falar de ligamentos cruzados e meniscos em ultrassonografia de joelho
            """

            # f"""
            # Você é um assistente médico especializado em radiologia.
            # Forneça uma resposta profissional, técnica e precisa.

            # Contexto: {prompt}

            # Responda de forma concisa e profissional, seguindo as melhores práticas médicas.
            # """


        response = service.generate_text(final_prompt)

        if response:
            # Cache por 1 hora
            cache.set(cache_key, response, 3600)
            return response

        return f"Erro: {service.api_error_message()}"

    except APIKeyMissingError as e:
        return f"Erro: {e}"
    except Exception as e:
        logger.exception("Erro no serviço de IA (%s)", service_name)
        return f"Erro: {str(e)}"


def generate_radiology_report(prompt, service_name="openrouter"):
    """
    Função específica para gerar laudos radiológicos
    """
    return generate_medical_text(prompt, service_name, use_medical_context=False)


def normalize_chat_history(historico):
    """Valida e normaliza histórico de chat para envio à IA."""
    if not historico:
        return []

    normalized = []
    for item in historico[-MAX_CHAT_HISTORY:]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        content = item.get('content', '')
        if role not in ('user', 'assistant'):
            continue
        if not isinstance(content, str):
            continue
        content = content.strip()
        if not content:
            continue
        normalized.append({'role': role, 'content': content})

    return normalized[-MAX_CHAT_HISTORY:]


def generate_or_edit_radiology_report(
    user_text,
    laudo_atual=None,
    historico=None,
    service_name="openrouter",
    modo_catalogo=False,
    frases_aplicadas=None,
    pedido_complementar=None,
):
    """
    Gera laudo radiológico do zero ou edita laudo existente conforme contexto.
    Retorna tupla (resultado, modo) onde modo é 'gerar' ou 'editar'.
    """
    user_text = (user_text or '').strip()
    laudo_atual = (laudo_atual or '').strip()
    historico = normalize_chat_history(historico)
    frases_aplicadas = [f for f in (frases_aplicadas or []) if f]
    pedido_complementar = (pedido_complementar or '').strip()
    complemento = pedido_complementar if modo_catalogo and pedido_complementar else user_text
    modo = 'editar' if laudo_atual else 'gerar'

    try:
        service = get_ai_service(service_name)
        if not isinstance(service, OpenRouterService):
            raise ValueError(f"Serviço '{service_name}' não suporta chat multi-turn")

        use_cache = modo == 'gerar' and not historico
        cache_key = f"ai_radiology_{hash(user_text + service_name + modo)}"
        if use_cache:
            cached_response = cache.get(cache_key)
            if cached_response:
                return cached_response, modo

        if modo == 'gerar':
            system_prompt = f"""Sou Radiologista e quero que vc me ajude a agilizar a minha confecção de laudos.
Quando eu pedir para vc fazer um laudo, ele deve vim neste formato:

{RADIOLOGY_REPORT_RULES}

Retorne APENAS o laudo radiológico completo, sem explicações adicionais."""

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(historico)
            messages.append({
                "role": "user",
                "content": (
                    f"Informações fornecidas pelo médico:\n{user_text}\n\n"
                    "Gere o laudo radiológico completo seguindo rigorosamente o formato especificado acima."
                ),
            })
            response = service.chat(messages)
        elif modo_catalogo:
            edit_rules = f"{RADIOLOGY_EDIT_RULES}\n\n{CATALOGO_COMPLEMENTO_RULES}"

            system_prompt = f"""Sou Radiologista. Nesta etapa você produz APENAS o texto NOVO a acrescentar ao laudo.
Frases padronizadas do catálogo já foram inseridas no editor — NÃO as inclua na resposta.

Contexto de formatação do laudo:

{RADIOLOGY_REPORT_RULES}

{edit_rules}

Retorne SOMENTE os acréscimos (texto puro a inserir), sem repetir o laudo existente."""

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(historico)

            frases_txt = ', '.join(frases_aplicadas) if frases_aplicadas else 'nenhuma'

            user_content = (
                f"Laudo atual (NÃO incluir na resposta — apenas contexto):\n"
                f"{laudo_atual}\n\n"
                f"Frases do catálogo já aplicadas (NÃO incluir na resposta): {frases_txt}\n\n"
                f"Complemento solicitado:\n{complemento}\n\n"
                "Escreva APENAS o texto novo a acrescentar ao laudo (ex.: medidas renais). "
                "Não retorne o laudo completo."
            )

            messages.append({
                "role": "user",
                "content": user_content,
            })
            response = service.chat(messages, temperature=0.1)
        else:
            system_prompt = f"""Sou Radiologista e quero que vc me ajude a editar laudos radiológicos.
O laudo deve seguir este formato:

{RADIOLOGY_REPORT_RULES}

{RADIOLOGY_EDIT_RULES}

Retorne APENAS o laudo radiológico completo atualizado, sem explicações adicionais."""

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(historico)
            messages.append({
                "role": "user",
                "content": (
                    f"Laudo atual:\n{laudo_atual}\n\n"
                    f"Pedido de alteração:\n{user_text}\n\n"
                    "Aplique somente as alterações solicitadas e retorne o laudo completo atualizado."
                ),
            })
            response = service.chat(messages)

        if response:
            if use_cache:
                cache.set(cache_key, response, 3600)
            return response, modo

        return f"Erro: {service.api_error_message()}", modo

    except APIKeyMissingError as e:
        return f"Erro: {e}", modo
    except Exception as e:
        logger.exception("Erro no serviço de IA (%s)", service_name)
        return f"Erro: {str(e)}", modo


def get_frases_for_modelo(user, modelo):
    """Frases associadas ao modelo + frases gerais filtradas por método."""
    from .models import Frase

    catalog = []
    seen_ids = set()
    metodo_id = modelo.metodo_id

    for frase in Frase.objects.filter(usuario=user).prefetch_related('modelos_laudo', 'metodos'):
        model_ids = list(frase.modelos_laudo.values_list('id', flat=True))
        if modelo.id in model_ids:
            if frase.id not in seen_ids:
                catalog.append(frase)
                seen_ids.add(frase.id)
            continue

        if model_ids:
            continue

        metodo_ids = list(frase.metodos.values_list('id', flat=True))
        if not metodo_ids or metodo_id in metodo_ids:
            if frase.id not in seen_ids:
                catalog.append(frase)
                seen_ids.add(frase.id)

    return catalog


def build_frase_catalog_entry(frase):
    """Resumo compacto de uma frase para envio à LLM."""
    frase_json = frase.frase or {}
    frase_base = frase_json.get('fraseBase', '') or ''
    return {
        'id': frase.id,
        'tituloFrase': frase.tituloFrase,
        'categoriaFrase': frase.categoriaFrase,
        'resumo_fraseBase': frase_base[:200],
        'tem_substituicao': bool(frase_json.get('substituicaoFraseBase')),
        'tem_variavel': '$' in frase_base or '[[LOCAL:' in frase_base or '[LOCAL:' in frase_base,
    }


def _parse_llm_json(raw_text):
    """Extrai e valida JSON retornado pela LLM."""
    if not raw_text:
        return None

    text = raw_text.strip()
    fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
    return None


def match_frases_from_chat(user_text, catalog_entries, historico=None, service_name='openrouter'):
    """
    Usa LLM apenas para escolher frases do catálogo.
    Retorna dict com frases, mensagem_assistente ou erro.
    """
    historico = normalize_chat_history(historico)
    valid_ids = {entry['id'] for entry in catalog_entries}

    if not catalog_entries:
        return {
            'frases': [],
            'mensagem_assistente': 'Nenhuma frase cadastrada para este modelo.',
        }

    try:
        service = get_ai_service(service_name)
        if not isinstance(service, OpenRouterService):
            raise ValueError(f"Serviço '{service_name}' não suporta chat multi-turn")

        catalog_json = json.dumps(catalog_entries, ensure_ascii=False, indent=2)
        system_prompt = """Você é um assistente que interpreta pedidos de radiologistas e escolhe frases de um catálogo pré-cadastrado.

REGRAS OBRIGATÓRIAS:
1. NÃO escreva texto médico nem laudo.
2. Retorne APENAS um JSON válido, sem markdown, no formato:
{
  "frases": [
    { "id": 123, "confianca": "alta", "medida": null }
  ],
  "pedido_complementar": "Trecho do pedido que NÃO será coberto pelas frases do catálogo (ex.: medidas avulsas, achados sem frase). Texto literal do médico. String vazia se nada restar.",
  "mensagem_assistente": "Breve confirmação em português"
}
3. Use somente IDs presentes no catálogo fornecido.
4. Se nenhuma frase corresponder, retorne "frases": [] e coloque todo o pedido em pedido_complementar.
5. Se o pedido mencionar medida para frase do catálogo (ex.: hérnia 0,8 cm), inclua em "medida" da frase — NÃO repita esse achado em pedido_complementar.
6. pedido_complementar deve conter SOMENTE instruções que as frases do catálogo NÃO atendem (ex.: medidas renais quando só há frase de esteatose).
7. confianca deve ser "alta", "media" ou "baixa"."""

        messages = [{'role': 'system', 'content': system_prompt}]
        messages.extend(historico)
        messages.append({
            'role': 'user',
            'content': (
                f"Catálogo de frases disponíveis:\n{catalog_json}\n\n"
                f"Pedido do médico:\n{user_text}\n\n"
                "Retorne o JSON com as frases a aplicar."
            ),
        })

        response = service.chat(messages, temperature=0.1)
        if not response:
            return {'error': service.api_error_message()}

        parsed = _parse_llm_json(response)
        if not parsed or not isinstance(parsed, dict):
            return {'error': 'Resposta inválida da IA ao interpretar frases.'}

        raw_frases = parsed.get('frases') or []
        if not isinstance(raw_frases, list):
            raw_frases = []

        frases_validas = []
        for item in raw_frases:
            if not isinstance(item, dict):
                continue
            frase_id = item.get('id')
            if frase_id not in valid_ids:
                continue
            frases_validas.append({
                'id': frase_id,
                'confianca': item.get('confianca') or 'media',
                'medida': item.get('medida'),
            })

        mensagem = parsed.get('mensagem_assistente') or ''
        pedido_complementar = parsed.get('pedido_complementar')
        if pedido_complementar is None:
            pedido_complementar = ''
        elif not isinstance(pedido_complementar, str):
            pedido_complementar = str(pedido_complementar)
        pedido_complementar = pedido_complementar.strip()

        if not frases_validas and not mensagem:
            mensagem = 'Não encontrei frase cadastrada correspondente ao pedido.'
        if not frases_validas and not pedido_complementar:
            pedido_complementar = user_text.strip()

        return {
            'frases': frases_validas,
            'pedido_complementar': pedido_complementar,
            'mensagem_assistente': mensagem,
        }

    except APIKeyMissingError as e:
        return {'error': str(e)}
    except Exception as e:
        logger.exception('Erro ao interpretar frases do chat')
        return {'error': str(e)}


def escolher_opcoes_frases(user_text, frases, service_name='openrouter'):
    """
    Escolhe opções já cadastradas a partir do que o médico falou.
    Não inventa texto clínico: só devolve ids de campos/opções do payload.
    """
    if not isinstance(frases, list) or not frases:
        return {'frases': []}

    try:
        service = get_ai_service(service_name)
        if not isinstance(service, OpenRouterService):
            raise ValueError(f"Serviço '{service_name}' não suporta chat multi-turn")

        payload = json.dumps(frases, ensure_ascii=False, indent=2)
        system_prompt = """Você preenche opções de frases de laudo a partir do que o médico falou.

REGRAS:
1. NÃO escreva laudo. Retorne APENAS JSON válido, sem markdown:
{
  "frases": [
    {
      "id": 123,
      "escolhas": [
        { "campo": "c0", "opcoes": ["o1"] },
        { "campo": "c1", "opcoes": ["o0", "o2"] },
        { "campo": "m0", "texto": "0,8 cm" }
      ]
    }
  ]
}
2. Use somente ids de frase, campo e opção presentes no payload.
3. tipo "unica" ou "grupo": no máximo uma opção, e só se o texto deixar claro.
4. tipo "multipla": todas as opções claramente citadas; lista vazia se nenhuma.
5. tipo "medida": "texto" com a medida dita (ex.: "0,8 cm"). Omita o campo se não houver medida.
6. Se o texto não mencionar o campo, NÃO chute: omita esse campo.
7. Uma fala pode cobrir várias frases; distribua cada trecho na frase certa."""

        messages = [
            {'role': 'system', 'content': system_prompt},
            {
                'role': 'user',
                'content': (
                    f"Frases e opções:\n{payload}\n\n"
                    f"O que o médico falou:\n{user_text}\n\n"
                    "Retorne o JSON das escolhas."
                ),
            },
        ]
        response = service.chat(messages, temperature=0.1)
        if not response:
            return {'error': service.api_error_message()}

        parsed = _parse_llm_json(response)
        if not parsed or not isinstance(parsed, dict):
            return {'error': 'Resposta inválida da IA ao escolher opções.'}

        valid_frases = {}
        for frase in frases:
            if not isinstance(frase, dict):
                continue
            try:
                frase_id = int(frase.get('id'))
            except (TypeError, ValueError):
                continue
            campos = {}
            for campo in frase.get('campos') or []:
                if not isinstance(campo, dict) or not campo.get('id'):
                    continue
                opcoes = {
                    op.get('id')
                    for op in (campo.get('opcoes') or [])
                    if isinstance(op, dict) and op.get('id')
                }
                campos[campo['id']] = {
                    'tipo': campo.get('tipo') or 'unica',
                    'opcoes': opcoes,
                }
            valid_frases[frase_id] = campos

        frases_ok = []
        for item in parsed.get('frases') or []:
            if not isinstance(item, dict):
                continue
            try:
                frase_id = int(item.get('id'))
            except (TypeError, ValueError):
                continue
            if frase_id not in valid_frases:
                continue
            escolhas = []
            for escolha in item.get('escolhas') or []:
                if not isinstance(escolha, dict):
                    continue
                campo_id = escolha.get('campo')
                campo = valid_frases[frase_id].get(campo_id)
                if not campo:
                    continue
                if campo['tipo'] == 'medida':
                    texto_medida = str(escolha.get('texto') or '').strip()
                    if texto_medida:
                        escolhas.append({'campo': campo_id, 'texto': texto_medida})
                    continue
                opcoes = [
                    op for op in (escolha.get('opcoes') or [])
                    if op in campo['opcoes']
                ]
                if campo['tipo'] != 'multipla':
                    opcoes = opcoes[:1]
                if opcoes:
                    escolhas.append({'campo': campo_id, 'opcoes': opcoes})
            frases_ok.append({'id': frase_id, 'escolhas': escolhas})

        return {'frases': frases_ok}
    except APIKeyMissingError as e:
        return {'error': str(e)}
    except Exception as e:
        logger.exception('Erro ao escolher opções das frases')
        return {'error': str(e)}


def localizar_frases_no_laudo(paragrafos, frases, service_name='openrouter'):
    """
    Escolhe em qual parágrafo do corpo do laudo cada frase entra.
    Não reescreve texto. Índice -1 = não identificado (inserir no início do laudo).
    """
    if not isinstance(frases, list) or not frases:
        return {'frases': []}
    if not isinstance(paragrafos, list) or not paragrafos:
        return {'frases': [{'id': f.get('id'), 'paragrafo': -1} for f in frases if isinstance(f, dict)]}

    try:
        service = get_ai_service(service_name)
        if not isinstance(service, OpenRouterService):
            raise ValueError(f"Serviço '{service_name}' não suporta chat multi-turn")

        lista = []
        for i, texto in enumerate(paragrafos):
            lista.append({'indice': i, 'texto': str(texto)[:400]})

        system_prompt = """Você indica ONDE encaixar frases já escritas num laudo. Não reescreva nada.

Retorne APENAS JSON:
{
  "frases": [
    { "id": 123, "paragrafo": 2 }
  ]
}

REGRAS:
1. "paragrafo" é o índice do parágrafo que descreve o mesmo órgão ou estrutura da frase.
   Ex.: cisto renal -> parágrafo dos rins; cálculo vesicular -> vesícula; esteatose -> fígado.
2. A frase deve entrar junto desse parágrafo, não no lugar dele.
3. Se nenhum parágrafo corresponder, use -1.
4. Não invente índice. Use só os índices da lista.
5. Não escreva texto de laudo."""

        messages = [
            {'role': 'system', 'content': system_prompt},
            {
                'role': 'user',
                'content': (
                    f"Parágrafos do laudo:\n{json.dumps(lista, ensure_ascii=False)}\n\n"
                    f"Frases:\n{json.dumps(frases, ensure_ascii=False)}\n\n"
                    "Retorne o JSON com o índice de cada frase."
                ),
            },
        ]
        response = service.chat(messages, temperature=0)
        if not response:
            return {'error': service.api_error_message()}

        parsed = _parse_llm_json(response)
        if not parsed or not isinstance(parsed, dict):
            return {'error': 'Resposta inválida da IA ao localizar parágrafos.'}

        max_idx = len(paragrafos) - 1
        por_id = {}
        for item in parsed.get('frases') or []:
            if not isinstance(item, dict):
                continue
            try:
                frase_id = int(item.get('id'))
                indice = int(item.get('paragrafo'))
            except (TypeError, ValueError):
                continue
            if indice < 0 or indice > max_idx:
                indice = -1
            por_id[frase_id] = indice

        saida = []
        for frase in frases:
            if not isinstance(frase, dict):
                continue
            try:
                frase_id = int(frase.get('id'))
            except (TypeError, ValueError):
                continue
            saida.append({'id': frase_id, 'paragrafo': por_id.get(frase_id, -1)})
        return {'frases': saida}
    except APIKeyMissingError as e:
        return {'error': str(e)}
    except Exception as e:
        logger.exception('Erro ao localizar frases no laudo')
        return {'error': str(e)}


def complementar_laudo_estruturado(
    linhas,
    pedido,
    frases_aplicadas=None,
    historico=None,
    service_name='openrouter',
):
    """
    Produz os acréscimos do modo catálogo já posicionados:
    cada item diz se substitui uma linha com '#', entra após uma linha
    ou vai para a conclusão. Nunca reescreve o que já está no laudo.
    """
    pedido = (pedido or '').strip()
    if not pedido:
        return {'acrescimos': []}
    if not isinstance(linhas, list) or not linhas:
        return {'error': 'Laudo sem linhas para posicionar o complemento.'}

    historico = normalize_chat_history(historico)
    frases_aplicadas = [f for f in (frases_aplicadas or []) if f]

    try:
        service = get_ai_service(service_name)
        if not isinstance(service, OpenRouterService):
            raise ValueError(f"Serviço '{service_name}' não suporta chat multi-turn")

        lista = [{'indice': i, 'texto': str(t)[:400]} for i, t in enumerate(linhas)]
        frases_txt = ', '.join(frases_aplicadas) if frases_aplicadas else 'nenhuma'

        system_prompt = f"""Sou Radiologista. Você complementa um laudo que já tem frases padronizadas inseridas.
Sua tarefa é escrever SOMENTE o que ainda falta e dizer ONDE cada trecho entra.

Contexto de formatação:
{RADIOLOGY_REPORT_RULES}

Retorne APENAS JSON válido, sem markdown:
{{
  "acrescimos": [
    {{ "texto": "Rim Direito mede: 12,0 x 5,0 cm. Parênquima/Cortical: 1,5 cm.", "substitui_linha": 7, "apos_linha": -1, "conclusao": false }},
    {{ "texto": "- Presença de lesão nodular hiperecogênica no segmento IV, medindo 1,1 cm, compatível com hemangioma.", "substitui_linha": -1, "apos_linha": 3, "conclusao": false }},
    {{ "texto": "- Hemangioma hepático.", "substitui_linha": -1, "apos_linha": -1, "conclusao": true }}
  ]
}}

REGRAS:
1. As linhas do laudo estão numeradas. Linhas com "#" são campos a preencher (ex.: "Rim Direito mede: # cm").
   Se o pedido traz esse dado, devolva a linha COMPLETA com os valores no lugar do "#", mantendo o texto original,
   e informe o índice em "substitui_linha".
2. Para um achado novo, escreva o parágrafo e informe em "apos_linha" o índice da linha que descreve o MESMO órgão
   (ex.: hemangioma -> linha do fígado; cisto renal -> linha dos rins). Use -1 só se nenhuma linha corresponder.
3. Todo achado novo relevante deve ter também um item com "conclusao": true (frase curta para a conclusão).
   Itens de conclusão usam substitui_linha -1 e apos_linha -1.
4. NÃO repita nem reescreva nada que já esteja no laudo. Não inclua os achados já cobertos por: {frases_txt}.
5. Não altere linhas sem "#" — para elas use apenas "apos_linha".
6. Use somente índices existentes na lista. Sem cabeçalhos, sem título, sem a palavra CONCLUSÃO.
7. Medidas sempre com unidade uma única vez (ex.: "1,0 cm", nunca "1,0 cm cm").
8. Se nada faltar, retorne {{"acrescimos": []}}."""

        messages = [{'role': 'system', 'content': system_prompt}]
        messages.extend(historico)
        messages.append({
            'role': 'user',
            'content': (
                f"Linhas do laudo atual:\n{json.dumps(lista, ensure_ascii=False)}\n\n"
                f"Complemento solicitado pelo médico:\n{pedido}\n\n"
                "Retorne o JSON com os acréscimos posicionados."
            ),
        })
        response = service.chat(messages, temperature=0.1)
        if not response:
            return {'error': service.api_error_message()}

        parsed = _parse_llm_json(response)
        if not parsed or not isinstance(parsed, dict):
            return {'error': 'Resposta inválida da IA ao complementar o laudo.'}

        max_idx = len(linhas) - 1

        def _idx(valor):
            try:
                i = int(valor)
            except (TypeError, ValueError):
                return -1
            return i if 0 <= i <= max_idx else -1

        acrescimos = []
        for item in parsed.get('acrescimos') or []:
            if not isinstance(item, dict):
                continue
            texto = str(item.get('texto') or '').strip()
            if not texto:
                continue
            acrescimos.append({
                'texto': texto,
                'substitui_linha': _idx(item.get('substitui_linha')),
                'apos_linha': _idx(item.get('apos_linha')),
                'conclusao': bool(item.get('conclusao')),
            })
        return {'acrescimos': acrescimos}
    except APIKeyMissingError as e:
        return {'error': str(e)}
    except Exception as e:
        logger.exception('Erro ao complementar laudo (estruturado)')
        return {'error': str(e)}


REVISAO_TIPOS = {
    'ortografia',
    'concordancia',
    'lateralidade',
    'medida',
    'duplicidade',
    'inconsistencia',
    'placeholder',
    'outro',
}

# Tipos em que a IA só alerta: a decisão é do médico, nunca aplicar automaticamente.
REVISAO_TIPOS_SEM_APLICAR = {'lateralidade', 'inconsistencia', 'duplicidade'}


def revisar_laudo_estruturado(linhas, texto_ditado='', service_name='openrouter'):
    """
    Revisa o laudo linha a linha e devolve pendências pontuais
    (ortografia, concordância, lateralidade, medidas, coerência descrição x conclusão).
    Não reescreve o laudo: cada item traz trecho exato e sugestão.
    """
    if not isinstance(linhas, list) or not linhas:
        return {'pendencias': []}

    texto_ditado = (texto_ditado or '').strip()

    try:
        service = get_ai_service(service_name)
        if not isinstance(service, OpenRouterService):
            raise ValueError(f"Serviço '{service_name}' não suporta chat multi-turn")

        lista = [{'indice': i, 'texto': str(t)[:600]} for i, t in enumerate(linhas)]

        system_prompt = """Você revisa laudos radiológicos em português do Brasil. Você NÃO reescreve o laudo:
aponta problemas pontuais, cada um com o trecho exato e a correção sugerida.

Retorne APENAS JSON válido, sem markdown:
{
  "pendencias": [
    {
      "linha": 12,
      "tipo": "concordancia",
      "trecho": "Cisto renal simples à no rim direito",
      "sugestao": "Cisto renal simples no rim direito",
      "motivo": "\"à\" sem função antes de \"no\"."
    }
  ]
}

TIPOS permitidos: ortografia, concordancia, lateralidade, medida, duplicidade, inconsistencia, placeholder, outro.

REGRAS:
1. "trecho" deve ser cópia EXATA de um pedaço contíguo da linha indicada (mesmas letras, acentos e pontuação),
   o menor possível que isole o problema. "sugestao" é o texto que substitui esse trecho.
2. "linha" é o índice da lista fornecida. Não invente índices.
3. lateralidade: descrição e conclusão citando lados diferentes para o mesmo achado, ou lado diferente do que o
   médico ditou. Nesses casos "sugestao" pode ser vazia; descreva o conflito em "motivo". Não escolha o lado.
4. inconsistencia: achado descrito no corpo sem conclusão correspondente, ou conclusão sem achado no corpo.
   Marque a linha envolvida, "sugestao" vazia, explique em "motivo".
5. duplicidade: mesmo achado descrito duas vezes. Marque a segunda ocorrência.
6. medida: unidade repetida ("1,0 cm cm"), medida sem unidade, formato fora de "A x B cm".
7. placeholder: restos como "#", "$", "{...}", "[LOCAL: ...]".
8. NÃO aponte estilo, sinônimos, ordem de parágrafos nem frases padronizadas corretas. Não sugira reescrever.
9. Terminologia radiológica consagrada não é erro (ex.: "ecotextura", "córtico-medular", "hepatocolédoco").
10. Se não houver problemas, retorne {"pendencias": []}."""

        conteudo = f"Linhas do laudo:\n{json.dumps(lista, ensure_ascii=False)}\n"
        if texto_ditado:
            conteudo += f"\nO que o médico ditou (para conferir lateralidade e achados):\n{texto_ditado}\n"
        conteudo += "\nRetorne o JSON de pendências."

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': conteudo},
        ]
        response = service.chat(messages, temperature=0)
        if not response:
            return {'error': service.api_error_message()}

        parsed = _parse_llm_json(response)
        if not parsed or not isinstance(parsed, dict):
            return {'error': 'Resposta inválida da IA ao revisar o laudo.'}

        max_idx = len(linhas) - 1
        pendencias = []
        for item in parsed.get('pendencias') or []:
            if not isinstance(item, dict):
                continue
            trecho = str(item.get('trecho') or '').strip()
            motivo = str(item.get('motivo') or '').strip()
            if not trecho and not motivo:
                continue
            try:
                linha = int(item.get('linha'))
            except (TypeError, ValueError):
                linha = -1
            if linha < 0 or linha > max_idx:
                linha = -1
            tipo = str(item.get('tipo') or 'outro').strip().lower()
            if tipo not in REVISAO_TIPOS:
                tipo = 'outro'
            sugestao = str(item.get('sugestao') or '').strip()
            # Só é aplicável se o trecho existir de fato na linha indicada.
            existe = linha >= 0 and trecho and trecho in str(linhas[linha])
            aplicavel = bool(
                existe and sugestao and sugestao != trecho and tipo not in REVISAO_TIPOS_SEM_APLICAR
            )
            pendencias.append({
                'linha': linha,
                'tipo': tipo,
                'trecho': trecho,
                'sugestao': sugestao,
                'motivo': motivo,
                'aplicavel': aplicavel,
                'origem': 'ia',
            })
        return {'pendencias': pendencias}
    except APIKeyMissingError as e:
        return {'error': str(e)}
    except Exception as e:
        logger.exception('Erro ao revisar laudo')
        return {'error': str(e)}


def validate_api_keys():
    """
    Valida se as chaves de API estão configuradas
    """
    apis_status = {
        "openai": bool(_normalize_api_key(settings.OPENAI_API_KEY)),
        "openrouter": bool(_normalize_api_key(settings.OPENROUTER_API_KEY)),
        "anthropic": bool(_normalize_api_key(settings.ANTHROPIC_API_KEY)),
        "groq": bool(_normalize_api_key(settings.GROQ_API_KEY)),
    }

    return apis_status


def ia_error_http_status(error_message):
    """Mapeia mensagens de erro de IA para códigos HTTP adequados."""
    if not error_message:
        return 502
    lower = error_message.lower()
    if "não configurada" in lower or "nao configurada" in lower:
        return 503
    return 502


def get_available_services():
    """
    Retorna lista de serviços de IA disponíveis
    """
    apis_status = validate_api_keys()
    available = [service for service, available in apis_status.items() if available]

    return available if available else ["nenhum"]

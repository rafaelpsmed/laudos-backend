"""
Serviços para integração com APIs de IA
"""
import os
import json
import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status

class AIService:
    """Classe base para serviços de IA"""

    def __init__(self, api_key, base_url=None):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        })

    def make_request(self, endpoint, data, method='POST'):
        """Faz uma requisição para a API"""
        try:
            url = f"{self.base_url}/{endpoint}" if self.base_url else endpoint
            response = self.session.request(method, url, json=data)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"Erro na API: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Erro na requisição: {e}")
            return None


class OpenAIService(AIService):
    """Serviço para integração com OpenAI"""

    def __init__(self):
        super().__init__(
            api_key=settings.OPENAI_API_KEY,
            base_url="https://api.openai.com/v1"
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
            base_url="https://openrouter.ai/api/v1"
        )
    # teste de modelos
    # anthropic/claude-3.7-sonnet - melhor até agora, porem caro
    # anthropic/claude-sonnet-4 - melhor até agora, porem caro
    # deepseek/deepseek-chat-v3.1 - bom; free
    # deepseek/deepseek-chat-v3-0324 - não ficou bom
    # deepseek/deepseek-chat-v3.1 - não ficou bom
    # openai/gpt-4.1-mini - não ficou bom
    # moonshotai/kimi-k2-0905 - bom, porem precisa de ajuste no prompt pq gera o texto todo junto

    def generate_text(self, prompt, model="anthropic/claude-sonnet-4", max_tokens=20000):
        """Gera texto usando OpenRouter"""
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


class AnthropicService(AIService):
    """Serviço para integração com Anthropic/Claude"""

    def __init__(self):
        super().__init__(
            api_key=settings.ANTHROPIC_API_KEY,
            base_url="https://api.anthropic.com/v1"
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

        return "Erro: Não foi possível gerar a resposta médica."

    except Exception as e:
        print(f"Erro no serviço de IA: {e}")
        return f"Erro: {str(e)}"


def generate_radiology_report(prompt, service_name="openrouter"):
    """
    Função específica para gerar laudos radiológicos
    """
    return generate_medical_text(prompt, service_name, use_medical_context=False)


def validate_api_keys():
    """
    Valida se as chaves de API estão configuradas
    """
    apis_status = {
        "openai": bool(settings.OPENAI_API_KEY),
        "openrouter": bool(settings.OPENROUTER_API_KEY),
        "anthropic": bool(settings.ANTHROPIC_API_KEY)
    }

    return apis_status


def get_available_services():
    """
    Retorna lista de serviços de IA disponíveis
    """
    apis_status = validate_api_keys()
    available = [service for service, available in apis_status.items() if available]

    return available if available else ["nenhum"]

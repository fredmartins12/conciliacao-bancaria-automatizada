"""
Classificador de comprovantes de pagamento via Claude (visão) — protótipo.

Para os casos sem extrato bancário estruturado (ex: comprovante de PIX enviado
por foto), este módulo envia a imagem + texto para a Claude e recebe de volta
a classificação contábil já estruturada em JSON, com nível de confiança.

Status: construído e testado isoladamente. A captura automática de
comprovantes em tempo real (ex: via WhatsApp) foi iniciada mas não chegou a
produção — hoje a imagem precisa ser fornecida manualmente ao script.
"""
import base64
import json
import re

import httpx

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

CATEGORIAS_DRE = """
2.1.1 - Pagamento de motorista agregado/transportadora
2.2.3 - Combustível / abastecimento
2.2.6 - Manutenção de veículos
3.3.7 - Salário (funcionário CLT)
3.3.6 - FGTS / encargos trabalhistas
3.4.5 - Honorários advocatícios
3.8.1 - Pró-labore de sócios
4.1   - Empréstimos / financiamentos
4.2   - Taxas bancárias
1.1   - Receita de clientes
"""

PROMPT_SISTEMA = f"""Você é um assistente financeiro de uma empresa de transporte e logística.
Sua função é analisar comprovantes de pagamento (imagem) e classificar a
transação na categoria DRE correta.

Categorias disponíveis:
{CATEGORIAS_DRE}

Se não tiver certeza da categoria, responda com "--" e explique o motivo na
observação em vez de arriscar uma classificação errada.

Responda SEMPRE neste formato JSON:
{{
  "categoria_cod": "2.1.1",
  "categoria_nome": "Pagamento de motorista agregado",
  "valor": 1500.00,
  "destinatario": "Nome do destinatário",
  "data": "18/06/2026",
  "confianca": "alta",
  "observacao": ""
}}

confianca pode ser: alta, media, baixa. Se for baixa, explique por quê.
"""


async def classificar_comprovante(
    api_key: str,
    texto_contexto: str,
    imagem_base64: str | None = None,
    mime_type: str = "image/jpeg",
) -> dict:
    """Envia o comprovante (imagem opcional + texto) para a Claude e retorna a classificação."""
    content = []
    if imagem_base64:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": mime_type, "data": imagem_base64},
        })
    content.append({"type": "text", "text": f"Contexto: {texto_contexto}\n\nClassifique esta transação."})

    payload = {
        "model": "claude-opus-4-6",
        "max_tokens": 1024,
        "system": PROMPT_SISTEMA,
        "messages": [{"role": "user", "content": content}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    texto_resposta = data["content"][0]["text"]
    match = re.search(r"\{.*\}", texto_resposta, re.DOTALL)
    if match:
        return json.loads(match.group())

    return {
        "categoria_cod": "--",
        "confianca": "baixa",
        "observacao": f"Não foi possível interpretar a resposta: {texto_resposta[:200]}",
    }

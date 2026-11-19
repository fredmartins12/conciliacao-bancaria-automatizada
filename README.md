# Conciliação Bancária Automatizada

Automação de conciliação bancária para uma empresa de transporte e logística: lê extratos bancários (CSV/OFX), classifica cada lançamento na categoria contábil correta (plano de contas DRE) e concilia diretamente no Conta Azul via automação de browser — sem digitação manual.

## Contexto

Antes desta automação, a conciliação bancária era feita manualmente no Conta Azul, lançamento por lançamento. Este projeto já processou mais de 1.100 lançamentos, eliminando o trabalho repetitivo e mantendo humano no loop apenas para os casos ambíguos (sinalizados como "a revisar" em vez de classificados às cegas).

## Como funciona

1. **Parser** (`parser.py`) — lê extratos bancários em CSV ou OFX, normaliza encoding, separador decimal brasileiro e datas.
2. **Motor de classificação** (`classifier.py`) — aplica regras de pattern-matching sobre a descrição do lançamento (palavras-chave, padrões de PIX/TED/boleto) para atribuir a categoria DRE correta, com camadas de override (por data+valor, por documento) para os casos que a regra geral não cobre.
3. **Integração Conta Azul** (`contaazul_client.py`) — busca lançamentos pendentes de conciliação e cria/concilia os lançamentos diretamente via API interna do Conta Azul. O Conta Azul não expõe API pública para esse fluxo — a integração reaproveita o mesmo endpoint que o frontend usa, autenticado via sessão de browser (Playwright).
4. **Classificador por imagem — protótipo** (`claude_receipt_classifier.py`) — usa a API da Claude (visão) para ler comprovantes de pagamento e sugerir classificação com nível de confiança, para os casos sem extrato estruturado. Construído e testado isoladamente; a captura de comprovantes via WhatsApp em tempo real foi iniciada mas não chegou a produção.

## Resultado

Mais de 1.100 lançamentos conciliados automaticamente, com os casos ambíguos sinalizados para revisão humana.

## Stack

Python · pandas/openpyxl · Playwright · API da Claude (Anthropic)

---
*Nomes de clientes/motoristas, valores, tokens e identificadores de conta são fictícios neste repositório. A estrutura e a lógica refletem o sistema real em produção.*

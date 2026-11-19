"""
Motor de classificação contábil (DRE) por regras.

Estratégia em camadas, da mais genérica para a mais específica:
1. Regra por palavra-chave na descrição do lançamento (ex: "TARIFA BANCARIA" -> Taxas)
2. Override por nome de contraparte conhecida (ex: fornecedor recorrente)
3. Override por (data, contraparte, valor) — para os casos em que a mesma
   contraparte recebe por motivos diferentes em datas diferentes (ex: motorista
   que recebe diária em uma data e reembolso de avaria em outra, mesmo valor
   aproximado)

Os nomes e valores abaixo são fictícios — ilustram o mecanismo, não os dados reais.
"""
import re
import unicodedata

# ── Plano de contas (DRE) — estrutura real, exemplo de categoria de transporte ──
CATEGORIAS_DRE = {
    "1.1": "Receita de Clientes",
    "1.2": "Receita de Frota Própria",
    "2.1.1": "Pagamento de Motorista Agregado (Adiantamento)",
    "2.1.2": "Pagamento de Motorista Agregado (Saldo)",
    "2.2.1": "Diária de Motorista CLT",
    "2.2.3": "Abastecimento / Combustível",
    "2.2.6": "Manutenção de Veículos",
    "3.1.4": "Honorários Contábeis",
    "3.3.7": "Salários",
    "3.8.1": "Pró-Labore de Sócios",
    "4.2": "Taxas Bancárias",
    "5.1.6": "GNRE / Tributos Estaduais",
    "!R": "A Revisar (classificação manual)",
}

# ── Exemplo de contraparte recorrente já confirmada manualmente uma vez ────────
CONTRAPARTE_CONFIRMADA = {
    "FORNECEDOR EXEMPLO LTDA": "3.1.4",
    "SOCIO EXEMPLO UM": "3.8.1",
    "SOCIO EXEMPLO DOIS": "3.8.1",
}

# ── Exemplo de override por (data, nome truncado, valor) ──────────────────────
# Usado quando a mesma pessoa recebe por motivos diferentes em datas próximas
# e o valor é o único jeito de diferenciar (ex: diária vs. reembolso de avaria).
OVERRIDES_DATA_NOME_VALOR: dict[tuple, str] = {
    ("01/06/2026", "MOTORISTA EXEMPLO UM", 480): "2.2.1",   # diária
    ("01/06/2026", "MOTORISTA EXEMPLO UM", 90):  "!R",       # valor atípico -> revisar
    ("03/06/2026", "MOTORISTA EXEMPLO DOIS", 87): "2.1.2",   # saldo
}


def normalizar(texto: str) -> str:
    """Remove acentos e colapsa espaços, para casar descrição do banco com as regras."""
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto.upper().strip()


def classificar(descricao: str, credito: float | None, debito: float | None,
                 data: str = "", documento: str = "") -> tuple[str, str]:
    """Retorna (codigo_dre, nome_categoria) para um lançamento."""
    d = normalizar(descricao)

    # ── Entradas (créditos) ─────────────────────────────────────────────────
    if credito and not debito:
        if "TED" in d or "TRANSF" in d:
            return "1.2", CATEGORIAS_DRE["1.2"]
        return "1.1", CATEGORIAS_DRE["1.1"]

    # ── Taxas e tarifas ──────────────────────────────────────────────────────
    if any(p in d for p in ["TARIFA BANCARIA", "TAR COMANDADA", "ANUIDADE", "IOF"]):
        return "4.2", CATEGORIAS_DRE["4.2"]

    # ── Tributos ─────────────────────────────────────────────────────────────
    if "GNRE" in d or "SEFAZ" in d:
        return "5.1.6", CATEGORIAS_DRE["5.1.6"]

    # ── Combustível ──────────────────────────────────────────────────────────
    if any(p in d for p in ["POSTO", "COMBUSTIVEL", "DIESEL"]):
        return "2.2.3", CATEGORIAS_DRE["2.2.3"]

    # ── Manutenção ───────────────────────────────────────────────────────────
    if any(p in d for p in ["AUTO PECAS", "MECANICA", "OFICINA", "HIDRAULICA"]):
        return "2.2.6", CATEGORIAS_DRE["2.2.6"]

    # ── PIX enviado: tenta identificar a contraparte ────────────────────────
    if "PIX ENVIADO" in d:
        m = re.search(r"DES:\s*(.+?)(?:\s+\d{2}/\d{2}|$)", d)
        nome = m.group(1).strip() if m else ""

        if nome in CONTRAPARTE_CONFIRMADA:
            cod = CONTRAPARTE_CONFIRMADA[nome]
            return cod, CATEGORIAS_DRE[cod]

        val_int = int(round(abs(debito or 0)))
        chave = (data, nome[:22], val_int)
        if chave in OVERRIDES_DATA_NOME_VALOR:
            cod = OVERRIDES_DATA_NOME_VALOR[chave]
            return cod, CATEGORIAS_DRE[cod]

        return "!R", CATEGORIAS_DRE["!R"]

    return "!R", CATEGORIAS_DRE["!R"]

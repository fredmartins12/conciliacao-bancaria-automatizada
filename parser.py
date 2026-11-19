"""
Parser de extratos bancários (CSV e OFX).

Lida com os dois formatos mais comuns de extrato brasileiro:
- CSV exportado direto do internet banking (encoding cp1252, decimal com vírgula)
- OFX (Open Financial Exchange), usado por bancos que não oferecem CSV limpo
"""
import re
from dataclasses import dataclass


@dataclass
class Lancamento:
    data: str
    descricao: str
    documento: str
    credito: float | None
    debito: float | None
    saldo: float | None


def parse_valor_br(s: str) -> float | None:
    """Converte '1.234,56' (formato brasileiro) para float."""
    if not s or not s.strip():
        return None
    s = s.strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def ler_csv(caminho: str) -> list[Lancamento]:
    """
    Lê extrato CSV no formato: Data;Descrição;Documento;Crédito;Débito;Saldo
    Ignora cabeçalhos, linhas de saldo anterior e linhas sem movimentação.
    """
    with open(caminho, "rb") as f:
        raw = f.read()
    texto = raw.decode("cp1252", errors="replace")
    linhas = [l.strip() for l in texto.replace("\r\n", "\n").split("\n") if l.strip()]

    lancamentos = []
    for linha in linhas:
        campos = linha.split(";")
        if not campos or not re.match(r"\d{2}/\d{2}/\d{4}", campos[0].strip()):
            continue  # pula cabeçalho e metadados

        data = campos[0].strip()
        descricao = campos[1].strip() if len(campos) > 1 else ""
        documento = campos[2].strip() if len(campos) > 2 else ""
        credito = parse_valor_br(campos[3]) if len(campos) > 3 else None
        debito = parse_valor_br(campos[4]) if len(campos) > 4 else None
        saldo = parse_valor_br(campos[5]) if len(campos) > 5 else None

        if descricao == "SALDO ANTERIOR" or (credito is None and debito is None):
            continue

        lancamentos.append(Lancamento(data, descricao, documento, credito, debito, saldo))

    return lancamentos


def ler_ofx(caminho: str) -> list[Lancamento]:
    """Lê extrato OFX extraindo os blocos <STMTTRN> (transação) com regex."""
    with open(caminho, "r", encoding="utf-8", errors="replace") as f:
        texto = f.read()

    lancamentos = []
    for bloco in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", texto, re.DOTALL):
        valor = re.search(r"<TRNAMT>([-\d.]+)", bloco)
        data_raw = re.search(r"<DTPOSTED>(\d{8})", bloco)
        memo = re.search(r"<MEMO>(.*?)[\r\n<]", bloco)
        fitid = re.search(r"<FITID>(.*?)[\r\n<]", bloco)

        if not valor or not data_raw:
            continue

        v = float(valor.group(1))
        data = f"{data_raw.group(1)[6:8]}/{data_raw.group(1)[4:6]}/{data_raw.group(1)[:4]}"
        descricao = memo.group(1).strip() if memo else ""
        documento = fitid.group(1).strip() if fitid else ""

        lancamentos.append(Lancamento(
            data=data,
            descricao=descricao,
            documento=documento,
            credito=v if v > 0 else None,
            debito=abs(v) if v < 0 else None,
            saldo=None,
        ))

    return lancamentos

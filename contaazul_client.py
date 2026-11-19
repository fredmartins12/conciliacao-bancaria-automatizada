"""
Cliente para a API interna do Conta Azul.

O Conta Azul não oferece API pública para conciliação bancária em lote — o
fluxo de "baixar extrato -> conciliar lançamento a lançamento" só existe na
interface web. Esse cliente reaproveita o mesmo endpoint que o frontend do
Conta Azul consome, autenticado via sessão de browser (token obtido via
Playwright a partir do header `x-authorization` de uma requisição real).

Token e IDs de conta/categoria vêm de variáveis de ambiente — nunca hardcoded.
"""
import os
import time
import httpx

BASE_URL = "https://services.contaazul.com"


class ContaAzulClient:
    def __init__(self, token: str | None = None, financial_account_id: str | None = None):
        self.token = token or os.environ["CONTA_AZUL_TOKEN"]
        self.financial_account_id = financial_account_id or os.environ["CONTA_AZUL_ACCOUNT_ID"]
        self.headers = {
            "content-type": "application/json",
            "x-authorization": self.token,
        }

    def buscar_pendentes(self, data_inicio: str, data_fim: str) -> list[dict]:
        """Busca todos os lançamentos pendentes de conciliação no período (paginado)."""
        pendentes, offset = [], 0
        with httpx.Client(timeout=30) as client:
            while True:
                resp = client.post(
                    f"{BASE_URL}/goldengate/rest/private/reconciliations/v2/pending-reconciliations",
                    params={"limit": 100, "offset": offset, "asc": "date"},
                    headers=self.headers,
                    json={
                        "financialAccountId": self.financial_account_id,
                        "searchTerm": "",
                        "startDate": data_inicio,
                        "endDate": data_fim,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                itens = data.get("items", data if isinstance(data, list) else [])
                pendentes.extend(itens)
                if len(itens) < 100:
                    break
                offset += 100
        return pendentes

    def conciliar(self, bank_statement: dict, categoria_uuid: str, tipo: str,
                   centro_custo_uuid: str | None = None) -> int:
        """Cria um lançamento financeiro e concilia com o extrato em uma chamada.

        CRÍTICO: sempre buscar a versão fresca do bank_statement antes de
        conciliar — versões desatualizadas são rejeitadas pela API.
        """
        valor = abs(float(bank_statement["value"]))
        payload = [{
            "bankStatement": {"id": bank_statement["id"], "version": bank_statement["version"]},
            "reconciliationType": "NEW_FINANCIAL_ENTRY",
            "matchEntries": [],
            "financialEntry": {
                "type": tipo,  # "EXPENSE" ou "REVENUE"
                "description": bank_statement["description"],
                "categoryId": categoria_uuid,
                "negotiatorId": None,
                "costCenterId": centro_custo_uuid,
                "valueComposition": {
                    "grossValue": valor, "netValue": valor,
                    "discount": 0, "interest": 0, "fine": 0, "fee": 0,
                },
            },
        }]

        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{BASE_URL}/goldengate/rest/private/reconciliations/v2",
                headers=self.headers, json=payload,
            )
        time.sleep(0.15)  # rate limiting — a API rejeita rajadas sem intervalo
        return resp.status_code

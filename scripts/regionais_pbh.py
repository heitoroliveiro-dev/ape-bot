"""Gera src/apebot/dados/bairros_bh.csv a partir do PDF da PBH (research R9 da 003).

Uso: python scripts/regionais_pbh.py docs/referencias/pbh-bairros-regionais.pdf > saida.csv
Roda uma vez, fora do robô. Precisa do pdftotext (poppler-utils).
"""

import csv
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from apebot.modelos import slug

DADOS = Path(__file__).parent.parent / "src" / "apebot" / "dados"
LINHA = re.compile(
    r"^\s*(.+?)\s{2,}(BARREIRO|CENTRO-SUL|LESTE|NORDESTE|NOROESTE|NORTE|OESTE|PAMPULHA|"
    r"VENDA NOVA)\s+([A-Z]{1,2}\d+)\s*$"
)
PARTICULAS = {"da", "de", "do", "das", "dos", "e"}
ROMANOS = {"i", "ii", "iii", "iv", "v", "vi"}

# slug do catálogo → (slug do nome oficial que dá a regional, nome exibido ou None = o oficial)
APELIDOS = {
    "aparecida-7a-secao": ("aparecida-setima-secao", None),
    "nova-suica": ("nova-suissa", None),
    "incofindencia": ("inconfidencia", None),
    "bandeirantes-pampulha": ("bandeirantes", None),
    "cabana": ("cabana-do-pai-tomas", None),
    "maria-tereza": ("maria-teresa", None),
    "sao-jorge": ("sao-jorge-i", "São Jorge"),
    "tupi": ("tupi-a", "Tupi"),
    "novo-das-industrias": ("bairro-novo-das-industrias", None),
    "parque-sao-joao-batista": ("sao-joao-batista", "Parque São João Batista"),
    "miramar-barreiro": ("miramar", None),
}
PREFIXOS = {"conjunto-": "Conjunto", "chacara-": "Chácara", "jardim-": "Jardim", "vila-": "Vila"}
POR_SUFIXO = {
    "santa-cruz-barreiro": ("Barreiro", "Santa Cruz (Barreiro)"),
    "sao-pedro-venda-nova": ("Venda Nova", "São Pedro (Venda Nova)"),
}
FORA_DE_BH = {
    "chacara-belo-horizonte-taubate-sp-brasil",
    "jardim-belo-horizonte-campinas-sp-brasil",
    "jardim-belo-horizonte-indaiatuba-sp-brasil",
    "vila-belo-horizonte-sao-paulo-sp-brasil",
    "hawai-justinopolis",
    "katia-justinopolis",
}


def titulo(texto: str) -> str:
    palavras = texto.lower().split()
    saida = []
    for i, palavra in enumerate(palavras):
        if palavra in ROMANOS:
            saida.append(palavra.upper())
        elif i > 0 and palavra in PARTICULAS:
            saida.append(palavra)
        else:
            saida.append("-".join(p[:1].upper() + p[1:] for p in palavra.split("-")))
    return " ".join(saida)


def ler_pdf(caminho: str) -> dict[str, tuple[str, str]]:
    """slug oficial → (nome oficial, regional)."""
    texto = subprocess.run(
        ["pdftotext", "-layout", caminho, "-"], capture_output=True, text=True, check=True
    ).stdout
    oficiais: dict[str, tuple[str, str]] = {}
    for linha in texto.splitlines():
        m = LINHA.match(linha)
        if m:
            oficiais[slug(m.group(1))] = (titulo(m.group(1)), titulo(m.group(2)))
    return oficiais


def slugs_do_catalogo() -> list[str]:
    """Os slugs do QuintoAndar: do .txt original ou, depois da 003, da coluna slug do .csv."""
    txt = DADOS / "bairros_bh.txt"
    if txt.exists():
        return [s.strip() for s in txt.read_text(encoding="utf-8").splitlines() if s.strip()]
    with open(DADOS / "bairros_bh.csv", encoding="utf-8") as arquivo:
        return [linha["slug"] for linha in csv.DictReader(arquivo)]


def main() -> None:
    oficiais = ler_pdf(sys.argv[1])
    contagem: Counter[str] = Counter()
    linhas = []
    for item in sorted(slugs_do_catalogo()):
        if item in FORA_DE_BH:
            contagem["excluidos"] += 1
            continue
        if item in oficiais:
            nome, regional = oficiais[item]
            contagem["direto"] += 1
        elif item in APELIDOS:
            chave, nome_exibido = APELIDOS[item]
            nome, regional = oficiais[chave]
            nome = nome_exibido or nome
            contagem["apelido"] += 1
        elif any(item.startswith(p) and item[len(p) :] in oficiais for p in PREFIXOS):
            prefixo = next(p for p in PREFIXOS if item.startswith(p))
            nome, regional = oficiais[item[len(prefixo) :]]
            nome = f"{PREFIXOS[prefixo]} {nome}"  # "vila-ermelinda" não pode virar "Ermelinda"
            contagem["apelido"] += 1
        elif item in POR_SUFIXO:
            regional, nome = POR_SUFIXO[item]
            contagem["sufixo"] += 1
        else:
            nome, regional = titulo(item.replace("-", " ")), "Outros"
            contagem["outros"] += 1
        linhas.append((item, nome, regional))

    escritor = csv.writer(sys.stdout, lineterminator="\n")
    escritor.writerow(["slug", "nome", "regional"])
    escritor.writerows(linhas)
    print(dict(contagem), file=sys.stderr)


if __name__ == "__main__":
    main()

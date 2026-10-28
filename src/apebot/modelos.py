import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from zoneinfo import ZoneInfo

HORARIOS_RODADA = (6, 9, 12, 15, 18, 21, 23)
FUSO = ZoneInfo("America/Sao_Paulo")


def slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


class Tipo(Enum):
    APARTAMENTO = "apartamento"
    CASA = "casa"
    CASA_CONDOMINIO = "casa_condominio"
    KITNET = "kitnet"

    @property
    def slug_url(self) -> str:
        return _SLUG_URL[self]

    @property
    def rotulo(self) -> str:
        return _ROTULO[self]

    @classmethod
    def de_json(cls, tipo_json: str) -> "Tipo | None":
        return _DO_JSON.get(tipo_json)


_SLUG_URL = {
    Tipo.APARTAMENTO: "apartamento",
    Tipo.CASA: "casa",
    Tipo.CASA_CONDOMINIO: "casacondominio",
    Tipo.KITNET: "kitnet",
}
_ROTULO = {
    Tipo.APARTAMENTO: "Apartamento",
    Tipo.CASA: "Casa",
    Tipo.CASA_CONDOMINIO: "Casa em condomínio",
    Tipo.KITNET: "Kitnet/Studio",
}
_DO_JSON = {
    "Apartamento": Tipo.APARTAMENTO,
    "Casa": Tipo.CASA,
    "CasaCondominio": Tipo.CASA_CONDOMINIO,
    "StudioOuKitchenette": Tipo.KITNET,
}


@dataclass(frozen=True)
class Anuncio:
    fonte: str
    id_externo: str
    tipo: Tipo
    bairro: str
    bairro_slug: str
    quartos: int
    area_m2: int | None
    aluguel_centavos: int
    total_centavos: int | None
    url: str

    @property
    def chave(self) -> tuple[str, str]:
        return (self.fonte, self.id_externo)


@dataclass(frozen=True)
class Filtro:
    bairros: frozenset[str]
    aluguel_max_centavos: int
    quartos_min: int
    tipos: frozenset[Tipo]


@dataclass(frozen=True)
class Pessoa:
    chat_id: int
    nome: str
    filtro: Filtro

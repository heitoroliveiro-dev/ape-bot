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

    @property
    def zap_property_types(self) -> tuple[str, ...]:
        return _ZAP_PROPERTY_TYPES[self]

    @classmethod
    def de_json(cls, tipo_json: str) -> "Tipo | None":
        return _DO_JSON.get(tipo_json)

    @classmethod
    def de_zap(cls, unit_type: str) -> "Tipo | None":
        return _DO_ZAP.get(unit_type)


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
# research R2 (002): tipos aceitos pela GeckoAPI no Zap e devolvidos em unitTypes
_ZAP_PROPERTY_TYPES = {
    Tipo.APARTAMENTO: ("apartment", "penthouse"),
    Tipo.CASA: ("house", "two_story_house"),
    Tipo.CASA_CONDOMINIO: ("condominium",),
    Tipo.KITNET: ("kitnet", "flat"),
}
_DO_ZAP = {
    "APARTMENT": Tipo.APARTAMENTO,
    "PENTHOUSE": Tipo.APARTAMENTO,
    "HOME": Tipo.CASA,
    "TWO_STORY_HOUSE": Tipo.CASA,
    "CONDOMINIUM": Tipo.CASA_CONDOMINIO,
    "KITNET": Tipo.KITNET,
    "FLAT": Tipo.KITNET,
}

NOMES_FONTE = {"quintoandar": "QuintoAndar", "zap": "Zap", "olx": "OLX"}


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
class Contato:
    """Contato do anunciante: só em trânsito até a mensagem ser entregue; nunca vai ao banco."""

    nome: str | None
    telefone: str | None
    whatsapp_url: str | None


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

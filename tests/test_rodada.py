import pytest

from apebot.rodada import status_rodada


@pytest.mark.parametrize(
    ("ok", "erro", "formato", "esperado"),
    [
        (10, 0, False, "ok"),
        (6, 4, False, "ok"),
        (5, 5, False, "falha"),
        (0, 3, False, "falha"),
        (9, 1, True, "falha"),
        (0, 0, False, "ok"),
    ],
)
def test_status_rodada(ok, erro, formato, esperado):
    assert status_rodada(ok, erro, formato) == esperado

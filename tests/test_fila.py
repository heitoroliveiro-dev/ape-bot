import json

from apebot.fila import TIMEOUT_CONSUMO_SEGUNDOS, Fila, Mensagem


def test_socket_timeout_maior_que_espera_do_blpop():
    fila = Fila("redis://redis-inexistente:6379/0")  # não conecta até o primeiro comando
    kwargs = fila._redis.connection_pool.connection_kwargs
    assert kwargs["socket_timeout"] > TIMEOUT_CONSUMO_SEGUNDOS


def test_mensagem_ida_e_volta_em_json():
    original = Mensagem(
        chat_id=1,
        tipo="imovel",
        texto="🏠 Apartamento · Funcionários",
        anuncio_ids=[("quintoandar", "123")],
        tentativas=2,
    )
    assert Mensagem.de_json(original.para_json()) == original


def test_botoes_sobrevivem_a_fila():
    mensagem = Mensagem(
        chat_id=1,
        tipo="imovel",
        texto="x",
        anuncio_ids=[("zap", "1")],
        botoes=[
            [{"t": "Abrir anúncio", "u": "https://x"}, {"t": "WhatsApp", "u": "https://wa.me/55"}],
            [{"t": "⭐ Salvar como favorito", "c": "f:zap:1"}],
        ],
    )
    assert Mensagem.de_json(mensagem.para_json()) == mensagem


def test_mensagem_antiga_sem_botoes():
    antiga = json.dumps({"chat_id": 1, "tipo": "texto", "texto": "x", "anuncio_ids": []})
    assert Mensagem.de_json(antiga).botoes == []

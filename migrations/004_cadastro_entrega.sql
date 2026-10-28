ALTER TABLE pessoa
    ADD COLUMN filtros JSON NULL,
    ADD COLUMN cadastro_completo_em DATETIME NULL,
    ADD COLUMN filtros_atualizados_em DATETIME NULL;

CREATE TABLE conversa (
    chat_id BIGINT PRIMARY KEY,
    modo ENUM('cadastro', 'edicao') NOT NULL,
    etapa VARCHAR(20) NOT NULL,
    rascunho JSON NOT NULL,
    atualizada_em DATETIME NOT NULL,
    CONSTRAINT fk_conversa_pessoa FOREIGN KEY (chat_id) REFERENCES pessoa (chat_id)
) DEFAULT CHARSET = utf8mb4;

CREATE TABLE favorito (
    chat_id BIGINT NOT NULL,
    fonte VARCHAR(20) NOT NULL,
    id_externo VARCHAR(40) NOT NULL,
    salvo_em DATETIME NOT NULL,
    PRIMARY KEY (chat_id, fonte, id_externo),
    CONSTRAINT fk_favorito_pessoa FOREIGN KEY (chat_id) REFERENCES pessoa (chat_id),
    CONSTRAINT fk_favorito_anuncio FOREIGN KEY (fonte, id_externo)
        REFERENCES anuncio (fonte, id_externo)
) DEFAULT CHARSET = utf8mb4;

CREATE TABLE resumo_diario (
    chat_id BIGINT NOT NULL,
    dia DATE NOT NULL,
    enviado_em DATETIME NOT NULL,
    PRIMARY KEY (chat_id, dia),
    CONSTRAINT fk_resumo_pessoa FOREIGN KEY (chat_id) REFERENCES pessoa (chat_id)
) DEFAULT CHARSET = utf8mb4;

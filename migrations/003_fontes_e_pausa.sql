ALTER TABLE pessoa ADD COLUMN pausada_em DATETIME NULL;

ALTER TABLE anuncio MODIFY url VARCHAR(500) NOT NULL;

ALTER TABLE alerta ADD COLUMN fonte VARCHAR(20) NOT NULL DEFAULT 'quintoandar';

CREATE TABLE rodada_fonte (
    rodada_id BIGINT NOT NULL,
    fonte VARCHAR(20) NOT NULL,
    status ENUM('ok', 'falha', 'desligada', 'sem_credito') NOT NULL,
    consultas SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    anuncios_vistos INT UNSIGNED NOT NULL DEFAULT 0,
    descartados INT UNSIGNED NOT NULL DEFAULT 0,
    fora_da_cidade INT UNSIGNED NOT NULL DEFAULT 0,
    erro_resumo VARCHAR(500) NULL,
    PRIMARY KEY (rodada_id, fonte),
    CONSTRAINT fk_rodada_fonte_rodada FOREIGN KEY (rodada_id) REFERENCES rodada (id)
) DEFAULT CHARSET = utf8mb4;

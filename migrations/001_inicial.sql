CREATE TABLE pessoa (
    chat_id BIGINT PRIMARY KEY,
    nome VARCHAR(80) NOT NULL,
    registrada_em DATETIME NULL,
    filtros_hash CHAR(64) NULL
) DEFAULT CHARSET = utf8mb4;

CREATE TABLE anuncio (
    fonte VARCHAR(20) NOT NULL,
    id_externo VARCHAR(40) NOT NULL,
    tipo ENUM('apartamento', 'casa', 'casa_condominio', 'kitnet') NOT NULL,
    bairro VARCHAR(80) NOT NULL,
    bairro_slug VARCHAR(80) NOT NULL,
    quartos TINYINT UNSIGNED NOT NULL,
    area_m2 SMALLINT UNSIGNED NULL,
    aluguel_centavos INT UNSIGNED NOT NULL,
    total_centavos INT UNSIGNED NULL,
    url VARCHAR(255) NOT NULL,
    primeiro_visto_em DATETIME NOT NULL,
    ultimo_visto_em DATETIME NOT NULL,
    PRIMARY KEY (fonte, id_externo),
    INDEX idx_anuncio_bairro_tipo (bairro_slug, tipo)
) DEFAULT CHARSET = utf8mb4;

CREATE TABLE envio (
    chat_id BIGINT NOT NULL,
    fonte VARCHAR(20) NOT NULL,
    id_externo VARCHAR(40) NOT NULL,
    status ENUM('pendente', 'entregue', 'falhou') NOT NULL DEFAULT 'pendente',
    criado_em DATETIME NOT NULL,
    entregue_em DATETIME NULL,
    tentativas TINYINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, fonte, id_externo),
    CONSTRAINT fk_envio_pessoa FOREIGN KEY (chat_id) REFERENCES pessoa (chat_id),
    CONSTRAINT fk_envio_anuncio FOREIGN KEY (fonte, id_externo)
        REFERENCES anuncio (fonte, id_externo)
) DEFAULT CHARSET = utf8mb4;

CREATE TABLE rodada (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    iniciada_em DATETIME NOT NULL,
    terminada_em DATETIME NULL,
    status ENUM('ok', 'falha') NULL,
    paginas_ok SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    paginas_erro SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    anuncios_vistos INT UNSIGNED NOT NULL DEFAULT 0,
    anuncios_novos INT UNSIGNED NOT NULL DEFAULT 0,
    descartados INT UNSIGNED NOT NULL DEFAULT 0,
    enfileirados INT UNSIGNED NOT NULL DEFAULT 0,
    erro_resumo VARCHAR(500) NULL
) DEFAULT CHARSET = utf8mb4;

CREATE TABLE alerta (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    aberto_em DATETIME NOT NULL,
    ultimo_aviso_em DATETIME NOT NULL,
    fechado_em DATETIME NULL
) DEFAULT CHARSET = utf8mb4;

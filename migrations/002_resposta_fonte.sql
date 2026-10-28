CREATE TABLE resposta_fonte (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    fonte VARCHAR(40) NOT NULL,
    request_id CHAR(36) NOT NULL,
    url VARCHAR(500) NOT NULL,
    extraida_em DATETIME NOT NULL,
    total_resultados INT UNSIGNED NULL,
    itens SMALLINT UNSIGNED NOT NULL,
    corpo JSON NOT NULL,
    recebida_em DATETIME NOT NULL,
    UNIQUE KEY uq_resposta_request (request_id),
    INDEX idx_resposta_fonte_data (fonte, extraida_em)
) DEFAULT CHARSET = utf8mb4;

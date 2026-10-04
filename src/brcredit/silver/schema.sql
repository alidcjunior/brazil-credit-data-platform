-- Silver: séries do BCB SGS limpas e tipadas. Idempotente (pode rodar várias vezes).
CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.sgs_series (
    series_code smallint PRIMARY KEY,
    name        text NOT NULL,
    unit        text NOT NULL,
    periodicity text NOT NULL CHECK (periodicity IN ('daily', 'monthly'))
);

CREATE TABLE IF NOT EXISTS silver.sgs_observation (
    series_code         smallint      NOT NULL REFERENCES silver.sgs_series (series_code),
    ref_date            date          NOT NULL,
    value               numeric(12,4) NOT NULL,
    -- captura que estabeleceu o valor atual; recapturas com o mesmo valor não mudam a linha
    source_run_id       text          NOT NULL,
    source_extracted_at timestamptz   NOT NULL,
    loaded_at           timestamptz   NOT NULL DEFAULT now(),
    PRIMARY KEY (series_code, ref_date)
);

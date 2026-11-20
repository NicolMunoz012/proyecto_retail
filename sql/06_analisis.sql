-- Resultados del ANOVA (src/anova.py). No depende de bi ni de core: el pipeline no lo borra.
CREATE SCHEMA IF NOT EXISTS analisis;

DROP TABLE IF EXISTS analisis.resultados_anova;

CREATE TABLE analisis.resultados_anova (
    "Análisis"     varchar(30) NOT NULL,
    "Prueba"       varchar(60) NOT NULL,
    "Estadístico"  varchar(20) NOT NULL,
    "p-valor"      double precision NOT NULL CHECK ("p-valor" BETWEEN 0 AND 1),
    "Decisión"     varchar(20) NOT NULL,
    "Adoptada"     varchar(2)  NOT NULL CHECK ("Adoptada" IN ('Sí', 'No')),
    PRIMARY KEY ("Análisis", "Prueba")
);

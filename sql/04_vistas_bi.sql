CREATE VIEW bi.dim_fecha AS
SELECT
    to_char(f, 'YYYYMMDD')::int                           AS "Id Fecha",
    f::date                                               AS "Fecha",
    extract(year FROM f)::int                             AS "Año",
    'T' || extract(quarter FROM f)::int                   AS "Trimestre",
    extract(month FROM f)::int                            AS "Mes",
    (ARRAY['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto',
           'Septiembre','Octubre','Noviembre','Diciembre'])[extract(month FROM f)::int] AS "Nombre Mes",
    to_char(f, 'YYYY-MM')                                 AS "Año-Mes",
    (extract(year FROM f) * 100 + extract(month FROM f))::int AS "AñoMesNum",
    extract(day FROM f)::int                              AS "Día"
FROM generate_series(date '2003-01-01', date '2005-12-31', interval '1 day') AS f;

CREATE VIEW bi.dim_producto AS
SELECT p.id_producto AS "Id Producto", p.codigo_producto AS "Código Producto", p.nombre AS "Producto",
       l.nombre AS "Línea", p.escala AS "Escala", p.proveedor AS "Proveedor",
       p.costo_unitario AS "Costo Unitario", p.precio_lista AS "Precio Lista"
FROM core.producto p JOIN core.linea_producto l USING (id_linea);

CREATE VIEW bi.dim_cliente AS
SELECT c.id_cliente AS "Id Cliente", c.numero_cliente AS "Número Cliente", c.nombre AS "Cliente",
       c.ciudad AS "Ciudad", pa.nombre AS "País Cliente", c.limite_credito AS "Límite Crédito"
FROM core.cliente c JOIN core.pais pa USING (id_pais);

CREATE VIEW bi.dim_representante AS
SELECT e.id_empleado AS "Id Representante", e.numero_empleado AS "Número Empleado",
       e.nombre || ' ' || e.apellido AS "Representante", e.cargo AS "Cargo",
       o.ciudad AS "Oficina", pa.nombre AS "País Oficina",
       t.codigo AS "Territorio", t.nombre AS "Región"
FROM core.empleado e
JOIN core.oficina o USING (id_oficina)
JOIN core.pais pa ON pa.id_pais = o.id_pais
JOIN core.territorio t USING (id_territorio);

CREATE VIEW bi.dim_pais AS
SELECT id_pais AS "Id País", codigo_iso3 AS "ISO3", codigo_iso2 AS "ISO2", nombre AS "País",
       nombre_oficial AS "País (oficial)", region_bm AS "Región BM", nivel_ingreso AS "Nivel de Ingreso",
       capital AS "Capital", latitud AS "Latitud", longitud AS "Longitud"
FROM core.pais;

CREATE VIEW bi.fact_ventas AS
SELECT
    d.id_detalle                                            AS "Id Detalle",
    p.numero_pedido                                         AS "Pedido",
    d.numero_linea                                          AS "Línea Pedido",
    to_char(p.fecha_pedido, 'YYYYMMDD')::int                AS "Id Fecha",
    d.id_producto                                           AS "Id Producto",
    p.id_cliente                                            AS "Id Cliente",
    c.id_representante                                      AS "Id Representante",
    c.id_pais                                               AS "Id País",
    e.nombre                                                AS "Estado",
    CASE WHEN d.venta < 3000 THEN 'Pequeña'
         WHEN d.venta < 7000 THEN 'Mediana'
         ELSE 'Grande' END                                  AS "Tamaño Venta",
    d.cantidad                                              AS "Cantidad",
    d.venta                                                 AS "Venta",
    round(d.venta / d.cantidad, 4)                          AS "Precio Unitario",
    d.cantidad * pr.costo_unitario                          AS "Costo",
    d.cantidad * pr.precio_lista                            AS "Valor Lista",
    d.venta - d.cantidad * pr.costo_unitario                AS "Utilidad",
    round(greatest(0, (pr.precio_lista - d.venta / d.cantidad) / pr.precio_lista), 6) AS "Descuento %"
FROM core.detalle_pedido d
JOIN core.pedido p        USING (id_pedido)
JOIN core.estado_pedido e USING (id_estado)
JOIN core.cliente c       ON c.id_cliente = p.id_cliente
JOIN core.producto pr     ON pr.id_producto = d.id_producto
WHERE e.cuenta_como_venta;

CREATE VIEW bi.fact_pedidos AS
SELECT
    p.id_pedido                                AS "Id Pedido",
    p.numero_pedido                            AS "Pedido",
    to_char(p.fecha_pedido, 'YYYYMMDD')::int   AS "Id Fecha",
    p.id_cliente                               AS "Id Cliente",
    c.id_representante                         AS "Id Representante",
    c.id_pais                                  AS "Id País",
    e.nombre                                   AS "Estado",
    p.fecha_pedido                             AS "Fecha Pedido",
    p.fecha_requerida                          AS "Fecha Requerida",
    p.fecha_envio                              AS "Fecha Envío",
    p.fecha_envio - p.fecha_pedido             AS "Días Envío",
    CASE WHEN p.fecha_envio IS NULL THEN NULL
         ELSE p.fecha_envio <= p.fecha_requerida END AS "A Tiempo"
FROM core.pedido p
JOIN core.estado_pedido e USING (id_estado)
JOIN core.cliente c ON c.id_cliente = p.id_cliente
WHERE e.cuenta_como_venta;

CREATE VIEW bi.fact_pagos AS
SELECT id_pago AS "Id Pago", numero_cheque AS "Cheque", id_cliente AS "Id Cliente",
       to_char(fecha_pago, 'YYYYMMDD')::int AS "Id Fecha", fecha_pago AS "Fecha Pago", monto AS "Monto"
FROM core.pago;

CREATE VIEW bi.fact_indicadores AS
SELECT id_indicador AS "Id Indicador", id_pais AS "Id País", anio AS "Año",
       pib_per_capita AS "PIB per Cápita", poblacion AS "Población"
FROM core.indicador_pais;

GRANT USAGE ON SCHEMA bi TO retail_etl;
GRANT SELECT ON ALL TABLES IN SCHEMA bi TO retail_etl;

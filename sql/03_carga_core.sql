INSERT INTO core.territorio (codigo, nombre)
SELECT codigo, nombre
FROM stg.territorio
ORDER BY codigo;

INSERT INTO core.pais (codigo_iso3, codigo_iso2, nombre, nombre_oficial, region_bm, nivel_ingreso,
                       capital, latitud, longitud)
SELECT codigo_iso3, codigo_iso2, nombre, nombre_oficial, region_bm, nivel_ingreso,
       capital, latitud, longitud
FROM stg.pais
ORDER BY codigo_iso3;

INSERT INTO core.indicador_pais (id_pais, anio, pib_per_capita, poblacion)
SELECT p.id_pais, s.anio, s.pib_per_capita, s.poblacion
FROM stg.indicador_pais s
JOIN core.pais p ON p.codigo_iso3 = s.codigo_iso3
ORDER BY p.id_pais, s.anio;

INSERT INTO core.oficina (codigo_oficina, ciudad, id_pais, id_territorio)
SELECT s.codigo_oficina, s.ciudad, p.id_pais, t.id_territorio
FROM stg.oficina s
JOIN core.pais p       ON p.codigo_iso3 = s.codigo_iso3
JOIN core.territorio t ON t.codigo = s.codigo_territorio
ORDER BY s.codigo_oficina;

INSERT INTO core.empleado (numero_empleado, nombre, apellido, cargo, id_oficina)
SELECT s.numero_empleado, s.nombre, s.apellido, s.cargo, o.id_oficina
FROM stg.empleado s
JOIN core.oficina o ON o.codigo_oficina = s.codigo_oficina
ORDER BY s.numero_empleado;

UPDATE core.empleado e
SET id_jefe = j.id_empleado
FROM stg.empleado s
JOIN core.empleado j ON j.numero_empleado = s.numero_jefe
WHERE e.numero_empleado = s.numero_empleado;

INSERT INTO core.cliente (numero_cliente, nombre, ciudad, id_pais, id_representante, limite_credito)
SELECT s.numero_cliente, s.nombre, s.ciudad, p.id_pais, e.id_empleado, s.limite_credito
FROM stg.cliente s
JOIN core.pais p          ON p.codigo_iso3 = s.codigo_iso3
LEFT JOIN core.empleado e ON e.numero_empleado = s.numero_representante
ORDER BY s.numero_cliente;

INSERT INTO core.linea_producto (nombre, descripcion)
SELECT nombre, descripcion
FROM stg.linea_producto
ORDER BY nombre;

INSERT INTO core.producto (codigo_producto, nombre, id_linea, escala, proveedor, costo_unitario, precio_lista)
SELECT s.codigo_producto, s.nombre, l.id_linea, s.escala, s.proveedor, s.costo_unitario, s.precio_lista
FROM stg.producto s
JOIN core.linea_producto l ON l.nombre = s.linea
ORDER BY s.codigo_producto;

INSERT INTO core.estado_pedido (codigo, nombre, cuenta_como_venta)
SELECT codigo, nombre, cuenta_como_venta
FROM stg.estado_pedido
ORDER BY codigo;

INSERT INTO core.pedido (numero_pedido, id_cliente, id_estado, fecha_pedido, fecha_requerida, fecha_envio)
SELECT s.numero_pedido, c.id_cliente, e.id_estado, s.fecha_pedido, s.fecha_requerida, s.fecha_envio
FROM stg.pedido s
JOIN core.cliente c       ON c.numero_cliente = s.numero_cliente
JOIN core.estado_pedido e ON e.codigo = s.codigo_estado
ORDER BY s.numero_pedido;

INSERT INTO core.detalle_pedido (id_pedido, numero_linea, id_producto, cantidad, venta)
SELECT p.id_pedido, s.numero_linea, pr.id_producto, s.cantidad, s.venta
FROM stg.detalle_pedido s
JOIN core.pedido p    ON p.numero_pedido = s.numero_pedido
JOIN core.producto pr ON pr.codigo_producto = s.codigo_producto
ORDER BY s.numero_pedido, s.numero_linea;

INSERT INTO core.pago (id_cliente, numero_cheque, fecha_pago, monto)
SELECT c.id_cliente, s.numero_cheque, s.fecha_pago, s.monto
FROM stg.pago s
JOIN core.cliente c ON c.numero_cliente = s.numero_cliente
ORDER BY s.fecha_pago, s.numero_cheque;

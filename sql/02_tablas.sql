CREATE TABLE IF NOT EXISTS meta.extraccion (
    id_extraccion    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha            timestamptz NOT NULL DEFAULT now(),
    fuente           varchar(30) NOT NULL,
    url              text NOT NULL,
    archivo          text NOT NULL,
    filas            integer NOT NULL
);

CREATE TABLE stg.territorio (codigo varchar(10), nombre varchar(30));
CREATE TABLE stg.pais (codigo_iso3 char(3), codigo_iso2 char(2), nombre varchar(60), nombre_oficial varchar(80),
                       region_bm varchar(60), nivel_ingreso varchar(40), capital varchar(60),
                       latitud numeric(9,4), longitud numeric(9,4));
CREATE TABLE stg.indicador_pais (codigo_iso3 char(3), anio smallint, pib_per_capita numeric(14,2), poblacion bigint);
CREATE TABLE stg.oficina (codigo_oficina varchar(10), ciudad varchar(50), codigo_iso3 char(3), codigo_territorio varchar(10));
CREATE TABLE stg.empleado (numero_empleado integer, nombre varchar(50), apellido varchar(50), cargo varchar(50),
                           codigo_oficina varchar(10), numero_jefe integer);
CREATE TABLE stg.cliente (numero_cliente integer, nombre varchar(50), ciudad varchar(50), codigo_iso3 char(3),
                          numero_representante integer, limite_credito numeric(12,2));
CREATE TABLE stg.linea_producto (nombre varchar(50), descripcion text);
CREATE TABLE stg.producto (codigo_producto varchar(15), nombre varchar(70), linea varchar(50), escala varchar(10),
                           proveedor varchar(50), costo_unitario numeric(10,2), precio_lista numeric(10,2));
CREATE TABLE stg.estado_pedido (codigo varchar(15), nombre varchar(30), cuenta_como_venta boolean);
CREATE TABLE stg.pedido (numero_pedido integer, numero_cliente integer, codigo_estado varchar(15),
                         fecha_pedido date, fecha_requerida date, fecha_envio date);
CREATE TABLE stg.detalle_pedido (numero_pedido integer, numero_linea smallint, codigo_producto varchar(15),
                                 cantidad integer, venta numeric(14,2));
CREATE TABLE stg.pago (numero_cliente integer, numero_cheque varchar(50), fecha_pago date, monto numeric(12,2));

CREATE TABLE core.territorio (
    id_territorio    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo           varchar(10) NOT NULL UNIQUE,
    nombre           varchar(30) NOT NULL
);

CREATE TABLE core.pais (
    id_pais          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_iso3      char(3) NOT NULL UNIQUE,
    codigo_iso2      char(2) NOT NULL UNIQUE,
    nombre           varchar(60) NOT NULL UNIQUE,
    nombre_oficial   varchar(80) NOT NULL,
    region_bm        varchar(60) NOT NULL,
    nivel_ingreso    varchar(40) NOT NULL,
    capital          varchar(60),
    latitud          numeric(9,4) NOT NULL CHECK (latitud BETWEEN -90 AND 90),
    longitud         numeric(9,4) NOT NULL CHECK (longitud BETWEEN -180 AND 180)
);

CREATE TABLE core.indicador_pais (
    id_indicador     integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_pais          integer NOT NULL REFERENCES core.pais,
    anio             smallint NOT NULL CHECK (anio BETWEEN 2003 AND 2005),
    pib_per_capita   numeric(14,2),
    poblacion        bigint,
    UNIQUE (id_pais, anio)
);

CREATE TABLE core.oficina (
    id_oficina       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_oficina   varchar(10) NOT NULL UNIQUE,
    ciudad           varchar(50) NOT NULL,
    id_pais          integer NOT NULL REFERENCES core.pais,
    id_territorio    integer NOT NULL REFERENCES core.territorio
);

CREATE TABLE core.empleado (
    id_empleado      integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_empleado  integer NOT NULL UNIQUE,
    nombre           varchar(50) NOT NULL,
    apellido         varchar(50) NOT NULL,
    cargo            varchar(50) NOT NULL,
    id_oficina       integer NOT NULL REFERENCES core.oficina,
    id_jefe          integer REFERENCES core.empleado
);

CREATE TABLE core.cliente (
    id_cliente       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_cliente   integer NOT NULL UNIQUE,
    nombre           varchar(50) NOT NULL UNIQUE,
    ciudad           varchar(50) NOT NULL,
    id_pais          integer NOT NULL REFERENCES core.pais,
    id_representante integer REFERENCES core.empleado,
    limite_credito   numeric(12,2) NOT NULL CHECK (limite_credito >= 0)
);

CREATE TABLE core.linea_producto (
    id_linea         integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre           varchar(50) NOT NULL UNIQUE,
    descripcion      text
);

CREATE TABLE core.producto (
    id_producto      integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_producto  varchar(15) NOT NULL UNIQUE,
    nombre           varchar(70) NOT NULL,
    id_linea         integer NOT NULL REFERENCES core.linea_producto,
    escala           varchar(10) NOT NULL,
    proveedor        varchar(50) NOT NULL,
    costo_unitario   numeric(10,2) NOT NULL CHECK (costo_unitario > 0),
    precio_lista     numeric(10,2) NOT NULL CHECK (precio_lista > 0)
);

CREATE TABLE core.estado_pedido (
    id_estado          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo             varchar(15) NOT NULL UNIQUE,
    nombre             varchar(30) NOT NULL,
    cuenta_como_venta  boolean NOT NULL
);

CREATE TABLE core.pedido (
    id_pedido        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_pedido    integer NOT NULL UNIQUE,
    id_cliente       integer NOT NULL REFERENCES core.cliente,
    id_estado        integer NOT NULL REFERENCES core.estado_pedido,
    fecha_pedido     date NOT NULL,
    fecha_requerida  date NOT NULL,
    fecha_envio      date,
    CHECK (fecha_requerida >= fecha_pedido),
    CHECK (fecha_envio IS NULL OR fecha_envio >= fecha_pedido)
);

CREATE TABLE core.detalle_pedido (
    id_detalle       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_pedido        integer NOT NULL REFERENCES core.pedido,
    numero_linea     smallint NOT NULL CHECK (numero_linea > 0),
    id_producto      integer NOT NULL REFERENCES core.producto,
    cantidad         integer NOT NULL CHECK (cantidad > 0),
    venta            numeric(14,2) NOT NULL CHECK (venta > 0),
    UNIQUE (id_pedido, numero_linea)
);

CREATE TABLE core.pago (
    id_pago          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_cliente       integer NOT NULL REFERENCES core.cliente,
    numero_cheque    varchar(50) NOT NULL UNIQUE,
    fecha_pago       date NOT NULL,
    monto            numeric(12,2) NOT NULL CHECK (monto > 0)
);

CREATE INDEX ON core.detalle_pedido (id_producto);
CREATE INDEX ON core.pedido (id_cliente);
CREATE INDEX ON core.pago (id_cliente);

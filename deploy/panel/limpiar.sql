-- Deja la base como recién creada: el próximo ETL vuelve a crear todo.
-- Se ejecuta solo desde el botón "Limpiar base" del panel (con confirmación).
DROP SCHEMA IF EXISTS bi CASCADE;
DROP SCHEMA IF EXISTS core CASCADE;
DROP SCHEMA IF EXISTS stg CASCADE;
DROP SCHEMA IF EXISTS analisis CASCADE;
DROP SCHEMA IF EXISTS meta CASCADE;

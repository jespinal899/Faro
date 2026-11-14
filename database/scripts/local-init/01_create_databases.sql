-- Se ejecuta automáticamente la PRIMERA vez que arranca el contenedor de PostgreSQL.
-- La base "wwi_oltp" (fuente) ya la crea la variable POSTGRES_DB del docker-compose.
-- Aquí creamos la base analítica de Faro, que tendrá los esquemas de staging y del Data Warehouse.
--
-- Convención de nombres:
--   wwi_*   -> pertenece a la empresa (WideWorldImporters): su sistema operacional.
--   faro_*  -> pertenece a nuestra plataforma (Faro): staging + Data Warehouse.
--
-- En Neon replicaremos la misma separación con dos proyectos:
--   wwi-oltp        -> base wwi_oltp
--   faro-analytics  -> base faro_analytics

CREATE DATABASE faro_analytics;

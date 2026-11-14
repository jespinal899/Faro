-- Faro · Fase 1 · Restaurar WideWorldImporters en el SQL Server TEMPORAL.
--
-- Respaldo: WideWorldImporters-Standard.bak (release oficial wide-world-importers-v1.0)
--   Tamaño : 126 951 424 bytes
--   SHA-256: 066279a8cd28c8d85cbd8215ea71a5d672b420cfbc19756b635c27bd8027dada
--
-- Los nombres lógicos (WWI_Primary, WWI_UserData, WWI_Log) se obtuvieron con:
--   RESTORE FILELISTONLY FROM DISK = N'/var/opt/mssql/backup/WideWorldImporters-Standard.bak';
--
-- Ejecución (desde la raíz del repo, con SQLCMDPASSWORD definido):
--   sqlcmd -S localhost,14330 -U sa -C -b -i database/source/seed/01_restaurar_wwi.sql

RESTORE DATABASE WideWorldImporters
FROM DISK = N'/var/opt/mssql/backup/WideWorldImporters-Standard.bak'
WITH MOVE N'WWI_Primary'  TO N'/var/opt/mssql/data/WideWorldImporters.mdf',
     MOVE N'WWI_UserData' TO N'/var/opt/mssql/data/WideWorldImporters_UserData.ndf',
     MOVE N'WWI_Log'      TO N'/var/opt/mssql/data/WideWorldImporters.ldf',
     REPLACE,
     STATS = 25;
GO

-- Solo vamos a LEER de esta base: la marcamos como solo lectura para evitar cambios accidentales.
ALTER DATABASE WideWorldImporters SET READ_ONLY WITH ROLLBACK IMMEDIATE;
GO

SELECT name, state_desc, is_read_only, compatibility_level
FROM sys.databases
WHERE name = N'WideWorldImporters';
GO

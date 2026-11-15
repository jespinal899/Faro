-- =====================================================================
-- Faro · Fuente (wwi_oltp) · Persona "Simulador de ventas"
-- IDEMPOTENTE. Requiere 01_esquema_fuente.sql.
--
-- WideWorldImporters termina el 31-may-2016. Para demostrar la carga incremental y las
-- alertas, un simulador inserta ventas nuevas. TODO lo que crea lleva a esta persona en
-- last_edited_by: así cualquier dato simulado es identificable de punta a punta
-- (la guía exige identificar los eventos simulados).
-- =====================================================================

DO $$
DECLARE
    nuevo_id integer;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM application.people WHERE full_name = 'Simulador de ventas') THEN
        SELECT COALESCE(max(person_id), 0) + 1 INTO nuevo_id FROM application.people;
        INSERT INTO application.people
            (person_id, full_name, preferred_name, is_employee, is_salesperson, last_edited_by)
        VALUES (nuevo_id, 'Simulador de ventas', 'Simulador', false, false, nuevo_id);
        PERFORM setval(pg_get_serial_sequence('application.people', 'person_id'), nuevo_id);
    END IF;
END;
$$;

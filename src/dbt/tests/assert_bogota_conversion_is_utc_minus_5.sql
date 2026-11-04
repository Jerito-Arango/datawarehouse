-- Comprueba la conversión de zona horaria que usan los hechos de MongoDB.
-- 2025-01-01 03:00 UTC debe ser 2024-12-31 22:00 en Bogotá (UTC-5, sin horario de verano).
select converted
from (
    select {{ to_business_time("cast('2025-01-01 03:00:00+00' as timestamptz)") }} as converted
) as conversion
where converted <> cast('2024-12-31 22:00:00' as timestamp)

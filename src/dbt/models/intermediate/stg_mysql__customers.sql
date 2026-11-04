{# raw acumula todos los lotes cargados; aquí se deja la versión más reciente de cada llave. Las filas sin llave se conservan para que calidad las rechace. #}
with ranked as (
    select
        *,
        row_number() over (
            partition by customer_id
            order by updated_at desc nulls last, _extracted_at desc, _batch_id desc
        ) as _version_rank
    from {{ source('mysql_raw', 'mysql_customers') }}
)

select
    cast(customer_id as bigint) as customer_id,
    nullif(trim(name), '') as name,
    nullif(lower(trim(email)), '') as email,
    nullif(trim(phone), '') as phone,
    nullif(trim(city), '') as city,
    nullif(trim(department), '') as department,
    cast(registration_date as date) as registration_date,
    cast(updated_at as timestamp) as updated_at,
    _batch_id,
    _loaded_at,
    _source
from ranked
where customer_id is null or _version_rank = 1

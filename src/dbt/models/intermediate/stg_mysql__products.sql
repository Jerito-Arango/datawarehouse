{# raw acumula todos los lotes cargados; aquí se deja la versión más reciente de cada llave. Las filas sin llave se conservan para que calidad las rechace. #}
with ranked as (
    select
        *,
        row_number() over (
            partition by product_id
            order by updated_at desc nulls last, _extracted_at desc, _batch_id desc
        ) as _version_rank
    from {{ source('mysql_raw', 'mysql_products') }}
)

select
    cast(product_id as bigint) as product_id,
    nullif(trim(name), '') as name,
    nullif(trim(category), '') as category,
    cast(price as decimal(12, 2)) as price,
    nullif(trim(description), '') as description,
    cast(is_active as boolean) as is_active,
    cast(updated_at as timestamp) as updated_at,
    _batch_id,
    _loaded_at,
    _source
from ranked
where product_id is null or _version_rank = 1

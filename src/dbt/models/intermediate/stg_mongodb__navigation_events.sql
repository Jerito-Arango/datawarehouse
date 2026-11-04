{# raw acumula todos los lotes cargados; aquí se deja la versión más reciente de cada llave. Las filas sin llave se conservan para que calidad las rechace. #}
with ranked as (
    select
        *,
        row_number() over (
            partition by event_id
            order by _extracted_at desc, _batch_id desc
        ) as _version_rank
    from {{ source('mongodb_raw', 'mongo_navigation_events') }}
)

select
    cast(event_id as bigint) as event_id,
    nullif(trim(event_type), '') as event_type,
    cast(occurred_at as timestamptz) as occurred_at,
    cast(customer_id as bigint) as customer_id,
    cast(product_id as bigint) as product_id,
    nullif(trim(sales_channel), '') as sales_channel,
    document_json,
    _batch_id,
    _loaded_at,
    _source
from ranked
where event_id is null or _version_rank = 1

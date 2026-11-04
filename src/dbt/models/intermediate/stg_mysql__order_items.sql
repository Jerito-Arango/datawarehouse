{# raw acumula todos los lotes cargados; aquí se deja la versión más reciente de cada llave. Las filas sin llave se conservan para que calidad las rechace. #}
with ranked as (
    select
        *,
        row_number() over (
            partition by order_item_id
            order by _extracted_at desc, _batch_id desc
        ) as _version_rank
    from {{ source('mysql_raw', 'mysql_order_items') }}
)

select
    cast(order_item_id as bigint) as order_item_id,
    cast(order_id as bigint) as order_id,
    cast(product_id as bigint) as product_id,
    cast(quantity as integer) as quantity,
    cast(unit_price as decimal(12, 2)) as unit_price,
    cast(subtotal as decimal(14, 2)) as subtotal,
    _batch_id,
    _loaded_at,
    _source
from ranked
where order_item_id is null or _version_rank = 1

{# raw acumula todos los lotes cargados; aquí se deja la versión más reciente de cada llave. Las filas sin llave se conservan para que calidad las rechace. #}
with ranked as (
    select
        *,
        row_number() over (
            partition by order_id
            order by _extracted_at desc, _batch_id desc
        ) as _version_rank
    from {{ source('mysql_raw', 'mysql_orders') }}
)

select
    cast(order_id as bigint) as order_id,
    cast(customer_id as bigint) as customer_id,
    cast(order_date as timestamp) as order_date,
    nullif(trim(status), '') as status,
    nullif(trim(sales_channel), '') as sales_channel,
    nullif(trim(payment_method), '') as payment_method,
    cast(total as decimal(14, 2)) as total,
    _batch_id,
    _loaded_at,
    _source
from ranked
where order_id is null or _version_rank = 1

{# raw acumula todos los lotes cargados; aquí se deja la versión más reciente de cada llave. Las filas sin llave se conservan para que calidad las rechace. #}
with ranked as (
    select
        *,
        row_number() over (
            partition by review_id
            order by _extracted_at desc, _batch_id desc
        ) as _version_rank
    from {{ source('mongodb_raw', 'mongo_reviews') }}
)

select
    cast(review_id as bigint) as review_id,
    cast(customer_id as bigint) as customer_id,
    cast(product_id as bigint) as product_id,
    cast(rating as integer) as rating,
    cast(reviewed_at as timestamptz) as reviewed_at,
    case lower(json_extract_path_text(document_json, 'verification', 'purchase_confirmed'))
        when 'true' then true
        when 'false' then false
    end as is_verified_purchase,
    document_json,
    _batch_id,
    _loaded_at,
    _source
from ranked
where review_id is null or _version_rank = 1

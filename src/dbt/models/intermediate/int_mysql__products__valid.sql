select
    product_id,
    name,
    category,
    price,
    description,
    is_active,
    updated_at,
    _batch_id,
    _loaded_at,
    _source
from {{ ref('int_mysql__products__qa') }}
where rejection_reason is null

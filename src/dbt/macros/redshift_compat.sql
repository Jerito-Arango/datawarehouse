{# Piezas que cambian entre DuckDB (versión local) y Redshift. Se centralizan aquí para ajustarlas en un solo lugar. #}

{# Hora local de negocio. DuckDB: timezone(zona, ts). Redshift: convert_timezone(zona, ts), que exige TIMESTAMP (no TIMESTAMPTZ), de ahí el cast. La sesión de Redshift trabaja en UTC. #}
{% macro to_business_time(column) -%}
convert_timezone('{{ var("business_timezone") }}', cast({{ column }} as timestamp))
{%- endmacro %}

{# Día de la semana ISO (1 = lunes ... 7 = domingo). DuckDB tiene isodow; en Redshift dow va de 0 (domingo) a 6. #}
{% macro iso_dow(date_column) -%}
(case when extract(dow from {{ date_column }}) = 0 then 7 else cast(extract(dow from {{ date_column }}) as integer) end)
{%- endmacro %}

{# Equivalente portable de "a IS DISTINCT FROM b": distinto, tratando NULL como un valor. Úsese en WHERE. #}
{% macro is_distinct(left, right) -%}
({{ left }} <> {{ right }} or ({{ left }} is null) <> ({{ right }} is null))
{%- endmacro %}

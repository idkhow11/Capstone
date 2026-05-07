-- Product-level Danawa mouse corpus for structured RAG.
-- Source: mouse_data.csv

create table if not exists danawa_products (
    product_id text primary key,
    product_name text not null,
    brand text,
    price integer,
    tier text,

    weight_g numeric(5, 1),
    length_mm numeric(5, 1),
    width_mm numeric(5, 1),
    height_mm numeric(5, 1),
    feet_material text,

    sensor_model text,
    max_dpi integer,
    max_ips integer,
    max_acceleration_g integer,
    max_polling_rate integer,
    switch_type text,

    connectivity text,
    battery_max_hours integer,
    charging_port text,
    is_rechargeable boolean,

    button_count integer,
    is_gaming boolean not null default false,
    hand_orientation text,

    avg_rating numeric(4, 2),
    total_reviews integer,
    key_pros text,
    key_cons text,

    has_rgb boolean,
    color text,
    is_silent boolean,
    switch_brand text,
    has_multi_pairing boolean,
    grip_type text,
    housing_design text,

    reviews text,
    url text,
    thumbnail text,
    search_vector tsvector generated always as (
        to_tsvector(
            'simple',
            coalesce(product_name, '') || ' ' ||
            coalesce(brand, '') || ' ' ||
            coalesce(sensor_model, '') || ' ' ||
            coalesce(connectivity, '') || ' ' ||
            coalesce(hand_orientation, '') || ' ' ||
            coalesce(key_pros, '') || ' ' ||
            coalesce(key_cons, '') || ' ' ||
            coalesce(color, '') || ' ' ||
            coalesce(grip_type, '') || ' ' ||
            coalesce(housing_design, '') || ' ' ||
            coalesce(reviews, '')
        )
    ) stored,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_danawa_products_brand on danawa_products (brand);
create index if not exists idx_danawa_products_tier on danawa_products (tier);
create index if not exists idx_danawa_products_price_rating on danawa_products (price, avg_rating);
create index if not exists idx_danawa_products_gaming_hand on danawa_products (is_gaming, hand_orientation);
create index if not exists idx_danawa_products_sensor on danawa_products (sensor_model);
create index if not exists idx_danawa_products_dpi_polling on danawa_products (max_dpi, max_polling_rate);
create index if not exists idx_danawa_products_weight_battery on danawa_products (weight_g, battery_max_hours);
create index if not exists idx_danawa_products_rgb_silent on danawa_products (has_rgb, is_silent);
create index if not exists idx_danawa_products_search_vector on danawa_products using gin (search_vector);

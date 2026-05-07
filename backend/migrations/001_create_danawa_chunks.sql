-- Danawa product RAG corpus for Supabase/Postgres.
-- Run this once in the Supabase SQL editor or with psql against DATABASE_URL.

create schema if not exists extensions;
create extension if not exists vector with schema extensions;

create table if not exists danawa_chunks (
    chunk_id bigint primary key,
    chunk_type text not null check (chunk_type in ('spec', 'detail', 'review', 'finetune')),
    product_id text not null,
    product_name text,
    brand text,
    price integer,
    tier text,
    avg_rating numeric(4, 2),
    total_count integer,
    positive_count integer,
    negative_count integer,
    positive_ratio numeric(4, 3),
    connection_type text check (connection_type in ('유선', '무선', '유선+무선')),
    sensor_model text,
    dpi_max integer,
    polling_rate_hz integer,
    weight_g numeric(5, 1),
    is_gaming boolean not null default false,
    is_right_hand_only boolean,
    length_mm numeric(5, 1),
    url text,
    thumbnail text,
    chunk_text text not null,
    embedding extensions.vector(768),
    search_vector tsvector generated always as (
        to_tsvector(
            'simple',
            coalesce(product_name, '') || ' ' ||
            coalesce(brand, '') || ' ' ||
            coalesce(chunk_text, '')
        )
    ) stored,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table danawa_chunks add column if not exists positive_ratio numeric(4, 3);
alter table danawa_chunks add column if not exists connection_type text check (connection_type in ('유선', '무선', '유선+무선'));
alter table danawa_chunks add column if not exists sensor_model text;
alter table danawa_chunks add column if not exists dpi_max integer;
alter table danawa_chunks add column if not exists polling_rate_hz integer;
alter table danawa_chunks add column if not exists weight_g numeric(5, 1);
alter table danawa_chunks add column if not exists is_gaming boolean not null default false;
alter table danawa_chunks add column if not exists is_right_hand_only boolean;
alter table danawa_chunks add column if not exists length_mm numeric(5, 1);

create index if not exists idx_danawa_chunks_product_id on danawa_chunks (product_id);
create index if not exists idx_danawa_chunks_chunk_type on danawa_chunks (chunk_type);
create index if not exists idx_danawa_chunks_brand on danawa_chunks (brand);
create index if not exists idx_danawa_chunks_price on danawa_chunks (price);
create index if not exists idx_danawa_chunks_gaming_connection on danawa_chunks (is_gaming, connection_type);
create index if not exists idx_danawa_chunks_sensor on danawa_chunks (sensor_model);
create index if not exists idx_danawa_chunks_polling_weight on danawa_chunks (polling_rate_hz, weight_g);
create index if not exists idx_danawa_chunks_price_rating on danawa_chunks (price, avg_rating);
create index if not exists idx_danawa_chunks_search_vector on danawa_chunks using gin (search_vector);
create index if not exists idx_danawa_chunks_embedding
    on danawa_chunks using hnsw (embedding extensions.vector_cosine_ops)
    where embedding is not null;

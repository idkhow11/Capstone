-- Enable Row Level Security for public tables exposed by Supabase/PostgREST.
-- User-owned tables intentionally have no anon/authenticated policies; the
-- FastAPI backend accesses them server-side through DATABASE_URL.

alter table public.users enable row level security;
alter table public.conversations enable row level security;
alter table public.chat_messages enable row level security;
alter table public.search_history enable row level security;

alter table public.danawa_products enable row level security;
alter table public.danawa_chunks enable row level security;

drop policy if exists "Danawa products are publicly readable" on public.danawa_products;
create policy "Danawa products are publicly readable"
on public.danawa_products
for select
to anon, authenticated
using (true);

drop policy if exists "Danawa chunks are publicly readable" on public.danawa_chunks;
create policy "Danawa chunks are publicly readable"
on public.danawa_chunks
for select
to anon, authenticated
using (true);

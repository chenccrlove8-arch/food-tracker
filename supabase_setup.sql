-- Execute once in your Supabase project's SQL Editor.
-- No database password or service_role key is needed by this application.
begin;

create table if not exists public.food_meals (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  meal_date date not null,
  meal_type text not null check (meal_type in ('早餐','午餐','晚餐','加餐/夜宵')),
  items jsonb not null check (jsonb_typeof(items) = 'array' and jsonb_array_length(items) between 1 and 20),
  portion numeric not null check (portion > 0 and portion <= 1),
  calories numeric not null check (calories between 0 and 200000),
  protein numeric not null check (protein between 0 and 40000),
  carbs numeric not null check (carbs between 0 and 40000),
  fat numeric not null check (fat between 0 and 40000),
  reason text not null default '',
  suggestion text not null default '',
  created_at timestamptz not null default now()
);
create index if not exists food_meals_owner_date on public.food_meals(user_id, meal_date desc, id);

create table if not exists public.food_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  settings jsonb not null default '{}'::jsonb
);

alter table public.food_meals enable row level security;
alter table public.food_profiles enable row level security;
revoke all on public.food_meals, public.food_profiles from anon;
revoke all on public.food_meals, public.food_profiles from authenticated;
grant select, insert on public.food_meals to authenticated;
grant select, insert, update on public.food_profiles to authenticated;

drop policy if exists food_meals_read_own on public.food_meals;
create policy food_meals_read_own on public.food_meals
  for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists food_meals_insert_own on public.food_meals;
create policy food_meals_insert_own on public.food_meals
  for insert to authenticated with check ((select auth.uid()) = user_id);

drop policy if exists food_profiles_read_own on public.food_profiles;
create policy food_profiles_read_own on public.food_profiles
  for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists food_profiles_insert_own on public.food_profiles;
create policy food_profiles_insert_own on public.food_profiles
  for insert to authenticated with check ((select auth.uid()) = user_id);
drop policy if exists food_profiles_update_own on public.food_profiles;
create policy food_profiles_update_own on public.food_profiles
  for update to authenticated using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
commit;

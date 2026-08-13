-- Supabase > SQL Editor ichida bir marta RUN qiling.

create table if not exists public.bot_targets (
  chat_id bigint primary key,
  title text not null,
  chat_type text not null check (chat_type in ('group', 'supergroup', 'channel')),
  section text not null check (section in ('admin', 'manager', 'rahbar')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.bot_sessions (
  user_id bigint primary key,
  mode text,
  target text,
  channel_id bigint,
  channel_title text,
  ui_chat_id bigint,
  ui_message_id bigint,
  updated_at timestamptz not null default now()
);

-- Oldingi versiyada bot_sessions yaratilgan bo‘lsa, yangi UI ustunlarini qo‘shadi.
alter table public.bot_sessions add column if not exists ui_chat_id bigint;
alter table public.bot_sessions add column if not exists ui_message_id bigint;

create table if not exists public.bot_updates (
  update_id bigint primary key,
  processed_at timestamptz not null default now()
);

-- Eski channels.json ichidagi mavjud Manager guruhini saqlab qolamiz.
insert into public.bot_targets (chat_id, title, chat_type, section)
values (-1004393094242, 'manager 1', 'group', 'manager')
on conflict (chat_id) do update set
  title = excluded.title,
  chat_type = excluded.chat_type,
  section = excluded.section,
  updated_at = now();

-- Data API server-side Secret key/service_role bilan ishlaydi.
alter table public.bot_targets enable row level security;
alter table public.bot_sessions enable row level security;
alter table public.bot_updates enable row level security;

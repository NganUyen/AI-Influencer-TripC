-- Capture Automation DB migration (Supabase/Postgres)
-- Purpose: add required columns for capture pipeline state + metadata.

alter table public.campaigns
  add column if not exists capture_status text,
  add column if not exists capture_verify text,
  add column if not exists capture_error text,
  add column if not exists top_half_video_path text,
  add column if not exists top_half_storage_path text,
  add column if not exists top_half_storage_url text,
  add column if not exists subtitle_data jsonb,
  add column if not exists capture_updated_at timestamptz default now();

create index if not exists idx_campaigns_capture_status
  on public.campaigns (capture_status);

create index if not exists idx_campaigns_capture_updated_at
  on public.campaigns (capture_updated_at desc);

-- Optional integrity check for status values:
-- alter table public.campaigns
--   add constraint campaigns_capture_status_check
--   check (capture_status is null or capture_status in ('running','completed','failed'));

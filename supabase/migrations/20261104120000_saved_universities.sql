-- =====================================================================
-- Merkliste: Angemeldete Nutzer speichern Hochschulen in ihrem Konto.
-- Jeder sieht und ändert nur die eigene Liste. Wird das Konto gelöscht,
-- verschwindet die Liste mit (on delete cascade).
-- =====================================================================

create table public.saved_universities (
  user_id        uuid not null references auth.users (id) on delete cascade,
  university_id  bigint not null references public.universities (id) on delete cascade,
  created_at     timestamptz not null default now(),
  primary key (user_id, university_id)
);

comment on table public.saved_universities is
  'Merkliste: von angemeldeten Nutzern gespeicherte Hochschulen.';

create index saved_universities_university_idx on public.saved_universities (university_id);

alter table public.saved_universities enable row level security;

create policy "Eigene Merkliste lesen"
  on public.saved_universities for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "Eigene Merkliste ergänzen"
  on public.saved_universities for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy "Eigene Merkliste kürzen"
  on public.saved_universities for delete to authenticated
  using ((select auth.uid()) = user_id);

revoke all on public.saved_universities from anon, authenticated;
grant select, insert, delete on public.saved_universities to authenticated;

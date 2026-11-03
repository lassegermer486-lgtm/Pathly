-- =====================================================================
-- Konto löschen: Angemeldete Nutzer können ihr eigenes Konto entfernen
-- (DSGVO Art. 17). Die Funktion löscht ausschließlich auth.uid() –
-- fremde Konten sind nicht erreichbar.
-- =====================================================================

create or replace function public.delete_own_account()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'Nicht angemeldet';
  end if;

  delete from auth.users where id = auth.uid();
end;
$$;

comment on function public.delete_own_account() is
  'Löscht das Konto des angemeldeten Nutzers (Self-Service, DSGVO Art. 17).';

revoke all on function public.delete_own_account() from public, anon;
grant execute on function public.delete_own_account() to authenticated;

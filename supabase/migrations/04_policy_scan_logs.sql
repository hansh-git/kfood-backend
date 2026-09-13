create policy "scan_logs_select_own"
  on scan_logs for select
  using (
    profile_id in (select id from profiles where user_id = auth.uid())
  );

create policy "scan_logs_insert_own"
  on scan_logs for insert
  with check (
    profile_id in (select id from profiles where user_id = auth.uid())
  );
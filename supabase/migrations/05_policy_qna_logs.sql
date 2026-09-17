create policy "qna_logs_select_own"
  on qna_logs for select
  using (
    scan_log_id in (
      select sl.id from scan_logs sl
      join profiles p on sl.profile_id = p.id
      where p.user_id = auth.uid()
    )
  );

create policy "qna_logs_insert_own"
  on qna_logs for insert
  with check (
    scan_log_id in (
      select sl.id from scan_logs sl
      join profiles p on sl.profile_id = p.id
      where p.user_id = auth.uid()
    )
  );
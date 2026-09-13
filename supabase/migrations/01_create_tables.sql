create table profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid unique references auth.users(id) on delete cascade,
  allergies jsonb,
  religious_diet varchar(50),
  vegetarian_type varchar(50),
  preferred_language varchar(10),
  created_at timestamptz default now()
);

create table scan_logs (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references profiles(id) on delete cascade,
  scan_image_url text,
  raw_ocr_text text,
  analysis_result jsonb,
  created_at timestamptz default now()
);

create table qna_logs (
  id uuid primary key default gen_random_uuid(),
  scan_log_id uuid references scan_logs(id) on delete cascade,
  question_text text,
  answer_text text,
  input_type varchar(10),
  created_at timestamptz default now()
);
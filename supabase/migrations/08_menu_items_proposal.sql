-- [제안] 김현수 → 한석호 검토 요청
-- 현재 메뉴 기준 데이터는 app/data/menu_base.json 에 있음.
-- 팀 검수 후 DB로 옮길 때 사용할 테이블 초안. (적용 전 논의 필요)

create table if not exists menu_items (
  id uuid primary key default gen_random_uuid(),
  name text unique not null,            -- 기준 메뉴명 (예: 짬뽕)
  aliases text[] default '{}',          -- 짬봉, 자장면 등
  category varchar(30),
  required_ingredients jsonb not null,  -- [{"name":"밀가루 면","tags":["wheat"]}]
  hidden_ingredients jsonb default '[]',
  variants jsonb default '[]',          -- [{"name":"해물짬뽕","keywords":["해물"],"ingredients":[...]}]
  updated_at timestamptz default now()
);

alter table menu_items enable row level security;

-- 누구나 읽기 가능(공개 참조 데이터), 쓰기는 service role만
create policy "menu_items_read_all" on menu_items for select using (true);

-- qna_logs.input_type 은 'text' | 'voice' 사용 (varchar(10) 이내)

-- Fixed seed for the web test database (collegedata_web_test). Shared by the
-- query tests of tasks 4-8; changing it can break their expectations.
-- All ids are fixed; sequences are pushed to 1000 at the end.

-- Sources (names/urls from pipeline/config/sources.yaml) --------------------
insert into source (id, code, name, url, license) values
  (1, 'hipo', 'Hipo university-domains-list', 'https://github.com/Hipo/university-domains-list', 'MIT'),
  (2, 'uac', '大學考試入學分發委員會', 'https://www.uac.edu.tw/', '公開資料（政府資訊）'),
  (3, 'cac', '大學甄選入學委員會', 'https://www.cac.edu.tw/', '公開資料（政府資訊）'),
  (4, 'scorecard', 'College Scorecard (U.S. Department of Education)', 'https://collegescorecard.ed.gov/', 'Public domain (U.S. Government work)'),
  (5, 'openalex', 'OpenAlex', 'https://openalex.org/', 'CC0');

-- Institutions (ids 4-9 and 13-31 are the 25 test universities: 10-12 are the US schools)
-- ---------------------------------------------------------------
insert into institution (id, country_code, name_en, name_zh, domain, web_url, control, source_id, source_url, fetched_at) values
  (1, 'TW', 'National Taiwan University', '國立臺灣大學', 'ntu.edu.tw', 'https://www.ntu.edu.tw/', 'public', 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00'),
  (2, 'TW', 'Chung Yuan Christian University', '中原大學', 'cycu.edu.tw', null, 'private', 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00'),
  (3, 'TW', 'Hipo Only Taiwan College', '只有名單的台灣學校', 'hipo-only.example.edu.tw', null, null, 1, 'https://github.com/Hipo/university-domains-list', '2026-10-30 03:00:00+00');

insert into institution (id, country_code, name_en, name_zh, domain, control, source_id, source_url, fetched_at)
select case when n <= 6 then 3 + n else 6 + n end, 'TW', 'Test University ' || lpad(n::text, 2, '0'), '測試大學' || lpad(n::text, 2, '0'),
       'test' || lpad(n::text, 2, '0') || '.example.edu.tw', 'private', 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00'
from generate_series(1, 25) as n;

insert into institution (id, country_code, name_en, name_zh, domain, web_url, scorecard_id, city, region, control, source_id, source_url, fetched_at) values
  (10, 'US', 'Stanford University', null, 'stanford.edu', 'https://www.stanford.edu/', 243744, 'Stanford', 'CA', 'private', 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (11, 'US', 'Test-Optional College', null, 'test-optional.example.edu', null, 900001, 'Springfield', 'IL', 'public', 4, 'https://collegescorecard.ed.gov/school/?900001', '2026-10-30 03:00:00+00'),
  (12, 'US', 'Hipo Only American College', null, 'hipo-only.example.edu', null, null, null, null, null, 1, 'https://github.com/Hipo/university-domains-list', '2026-10-30 03:00:00+00');

-- Programs -------------------------------------------------------------------
insert into program (id, institution_id, name_zh, name_en, field_code, code, source_id, source_url, fetched_at) values
  (101, 1, '資訊工程學系', null, 'cs', null, 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00'),
  (102, 1, '醫學系', null, 'health', null, 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00'),
  (103, 1, '歷史學系', null, 'humanities', null, 3, 'https://www.cac.edu.tw/', '2026-10-30 03:00:00+00'),
  (201, 2, '建築學系', null, 'architecture', null, 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00');

insert into program (id, institution_id, name_zh, name_en, field_code, source_id, source_url, fetched_at)
select 300 + n, case when n <= 6 then 3 + n else 6 + n end, '測試學系', 'Test Department', 'business', 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00'
from generate_series(1, 25) as n;

insert into program (id, institution_id, name_zh, name_en, field_code, code, source_id, source_url, fetched_at) values
  (1001, 10, null, 'All programs', null, 'all', 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (1002, 10, null, 'Computer and Information Sciences', 'cs', '11', 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (1003, 10, null, 'Engineering', 'engineering', '14', 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (1101, 11, null, 'All programs', null, 'all', 4, 'https://collegescorecard.ed.gov/school/?900001', '2026-10-30 03:00:00+00'),
  (1102, 11, null, 'Business', 'business', '52', 4, 'https://collegescorecard.ed.gov/school/?900001', '2026-10-30 03:00:00+00');

-- TW admission_stat: UAC distribution (2023 is outside the latest three years)
insert into admission_stat (program_id, year, pathway, min_score, admitted_count, subjects, source_id, source_url, fetched_at) values
  (101, 2023, 'tw_distribution', 59.00, 44, '[{"subject":"數學甲","weight":1.5},{"subject":"物理","weight":1.0}]', 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00'),
  (101, 2024, 'tw_distribution', 60.25, 45, '[{"subject":"數學甲","weight":1.5},{"subject":"物理","weight":1.0}]', 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00'),
  (101, 2025, 'tw_distribution', 61.50, 46, '[{"subject":"數學甲","weight":1.5},{"subject":"物理","weight":1.0}]', 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00'),
  (101, 2026, 'tw_distribution', 62.75, 47, '[{"subject":"數學甲","weight":1.5},{"subject":"物理","weight":1.0}]', 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00'),
  (102, 2024, 'tw_distribution', 70.50, 20, '[{"subject":"生物","weight":2.0},{"subject":"化學","weight":1.5}]', 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00'),
  (102, 2025, 'tw_distribution', 71.25, 20, '[{"subject":"生物","weight":2.0},{"subject":"化學","weight":1.5}]', 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00'),
  (102, 2026, 'tw_distribution', 72.00, 21, '[{"subject":"生物","weight":2.0},{"subject":"化學","weight":1.5}]', 2, 'https://www.uac.edu.tw/', '2026-10-30 03:00:00+00');

-- TW admission_stat: CAC sieve (min_score/admitted_count are NULL for tw_apply)
insert into admission_stat (program_id, year, pathway, min_score, admitted_count, subjects, tiebreak, sieve, source_id, source_url, fetched_at) values
  (101, 2024, 'tw_apply', null, null, '[]', null,
    '[{"order":1,"label":"(英文+自然)24","subjects":["英文","自然"],"min_score":24},{"order":2,"label":"數學A14","subjects":["數學A"],"min_score":14}]',
    3, 'https://www.cac.edu.tw/apply113/pict/001.png', '2026-10-30 03:00:00+00'),
  (101, 2025, 'tw_apply', null, null, '[]', null,
    '[{"order":1,"label":"(英文+自然)25","subjects":["英文","自然"],"min_score":25},{"order":2,"label":"數學A15","subjects":["數學A"],"min_score":15}]',
    3, 'https://www.cac.edu.tw/apply114/pict/001.png', '2026-10-30 03:00:00+00'),
  (101, 2026, 'tw_apply', null, null, '[]', '同級分超額篩選',
    '[{"order":1,"label":"(英文+自然)26","subjects":["英文","自然"],"min_score":26},{"order":2,"label":"數學A15","subjects":["數學A"],"min_score":15}]',
    3, 'https://www.cac.edu.tw/apply115/pict/001.png', '2026-10-30 03:00:00+00');

-- TW admission_requirement (CAC individual application)
insert into admission_requirement (program_id, year, pathway, system_code, requirement, source_id, source_url, fetched_at) values
  (101, 2024, 'tw_apply', 'tw_gsat',
    '{"cac_code":"001582","group":"一般校系","gender":null,"quota":55,"thresholds":{"國文":null,"英文":"頂標","數學A":"頂標","數學B":null,"社會":null,"自然":"頂標","英聽":null},"multipliers":{"國文":null,"英文":10,"數學A":2.5,"數學B":null,"社會":null,"自然":10,"學測科目組合":null},"extra":{},"sources":{"sieve_image":"https://www.cac.edu.tw/apply113/pict/001.png","rules_page":"https://www.cac.edu.tw/apply113/html/113_001582.htm"}}',
    3, 'https://www.cac.edu.tw/apply113/html/113_001582.htm', '2026-10-30 03:00:00+00'),
  (101, 2025, 'tw_apply', 'tw_gsat',
    '{"cac_code":"001582","group":"一般校系","gender":null,"quota":56,"thresholds":{"國文":null,"英文":"頂標","數學A":"頂標","數學B":null,"社會":null,"自然":"頂標","英聽":null},"multipliers":{"國文":null,"英文":10,"數學A":2.5,"數學B":null,"社會":null,"自然":10,"學測科目組合":null},"extra":{"APCS識讀":"4"},"sources":{"sieve_image":"https://www.cac.edu.tw/apply114/pict/001.png","rules_page":"https://www.cac.edu.tw/apply114/html/114_001582.htm"}}',
    3, 'https://www.cac.edu.tw/apply114/html/114_001582.htm', '2026-10-30 03:00:00+00'),
  (101, 2026, 'tw_apply', 'tw_gsat',
    '{"cac_code":"001582","group":"一般校系","gender":null,"quota":57,"thresholds":{"國文":null,"英文":"頂標","數學A":"頂標","數學B":null,"社會":null,"自然":"頂標","英聽":null},"multipliers":{"國文":null,"英文":10,"數學A":2.5,"數學B":null,"社會":null,"自然":10,"學測科目組合":null},"extra":{"APCS識讀":"4","APCS實作":"4"},"stage2":{"gsat_weights":{"英文":1.25,"數學A":2.0,"自然":1.0},"stage1_pct":20,"items":[{"name":"審查資料","threshold":"70分","pct":50},{"name":"數學筆試","threshold":null,"pct":30}],"tiebreak_order":["審查資料","數學筆試","學科能力測驗成績","學測數學A級分"],"review_items":"修課紀錄(A)、課程學習成果(B、C、D)、多元表現(E)、學習歷程自述(F)","exam_date":"115.5.17","expected_candidates":143,"fee":1500,"website":"http://www.csie.ntu.edu.tw"},"sources":{"sieve_image":"https://www.cac.edu.tw/apply115/pict/001.png","rules_page":"https://www.cac.edu.tw/apply115/html/115_001582.htm"}}',
    3, 'https://www.cac.edu.tw/apply115/html/115_001582.htm', '2026-10-30 03:00:00+00'),
  (103, 2026, 'tw_apply', 'tw_gsat',
    '{"cac_code":"001012","group":"一般校系","gender":null,"quota":30,"thresholds":{"國文":"均標","英文":"均標","數學A":null,"數學B":null,"社會":"均標","自然":null,"英聽":null},"multipliers":{"國文":null,"英文":null,"數學A":null,"數學B":null,"社會":null,"自然":null,"學測科目組合":null},"extra":{},"sources":{"rules_page":"https://www.cac.edu.tw/apply115/html/115_001012.htm"}}',
    3, 'https://www.cac.edu.tw/apply115/html/115_001012.htm', '2026-10-30 03:00:00+00');

-- US admission_stat (school-level, on the code='all' program) -----------------
insert into admission_stat (program_id, year, pathway, admitted_count, subjects, admission_rate, source_id, source_url, fetched_at) values
  (1001, 2022, 'us_freshman', null, '[]', 0.03680, 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (1001, 2023, 'us_freshman', null, '[]', 0.03910, 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (1001, 2024, 'us_freshman', null, '[]', 0.03610, 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (1101, 2022, 'us_freshman', null, '[]', 0.58000, 4, 'https://collegescorecard.ed.gov/school/?900001', '2026-10-30 03:00:00+00'),
  (1101, 2023, 'us_freshman', null, '[]', 0.60000, 4, 'https://collegescorecard.ed.gov/school/?900001', '2026-10-30 03:00:00+00'),
  (1101, 2024, 'us_freshman', null, '[]', 0.65000, 4, 'https://collegescorecard.ed.gov/school/?900001', '2026-10-30 03:00:00+00');

insert into admission_requirement (program_id, year, pathway, system_code, requirement, source_id, source_url, fetched_at) values
  (1001, 2022, 'us_freshman', 'us_sat',
    '{"sat":{"rw":{"p25":730,"p75":770},"math":{"p25":760,"p75":800},"total":{"p25":1490,"p75":1570}},"act":{"composite":{"p25":33,"p75":35}}}',
    4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (1001, 2023, 'us_freshman', 'us_sat',
    '{"sat":{"rw":{"p25":740,"p75":770},"math":{"p25":770,"p75":800},"total":{"p25":1500,"p75":1570}},"act":{"composite":{"p25":34,"p75":35}}}',
    4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (1001, 2024, 'us_freshman', 'us_sat',
    '{"sat":{"rw":{"p25":740,"p75":780},"math":{"p25":770,"p75":800},"total":{"p25":1510,"p75":1580}},"act":{"composite":{"p25":34,"p75":35}}}',
    4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00');

-- Costs ----------------------------------------------------------------------
insert into cost (institution_id, year, residency, tuition, currency, source_id, source_url, fetched_at) values
  (10, 2022, 'local', 56169, 'USD', 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (10, 2022, 'out_of_state', 56169, 'USD', 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (10, 2023, 'local', 62484, 'USD', 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (10, 2023, 'out_of_state', 62484, 'USD', 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (10, 2024, 'local', 68544, 'USD', 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (10, 2024, 'out_of_state', 68544, 'USD', 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (11, 2024, 'local', 12000, 'USD', 4, 'https://collegescorecard.ed.gov/school/?900001', '2026-10-30 03:00:00+00'),
  (11, 2024, 'out_of_state', 30000, 'USD', 4, 'https://collegescorecard.ed.gov/school/?900001', '2026-10-30 03:00:00+00');

-- Institution stats (Test-Optional is deliberately < 5000 => "small") ---------
insert into institution_stat (institution_id, year, student_size, completion_rate, median_earnings, currency, source_id, source_url, fetched_at) values
  (10, 2024, 7554, 0.91640, 125340, 'USD', 4, 'https://collegescorecard.ed.gov/school/?243744', '2026-10-30 03:00:00+00'),
  (11, 2024, 4000, null, null, 'USD', 4, 'https://collegescorecard.ed.gov/school/?900001', '2026-10-30 03:00:00+00');

-- Strengths: NTU wins Medicine (800 vs 300), Stanford wins Computer Science (1300 vs 200)
insert into strength (institution_id, topic_id, topic_name, field_name, works_count, cited_by_count, rank, source_id, source_url, fetched_at) values
  (1, 'T1001', 'Clinical Medicine Research', 'Medicine', 500, 9000, 1, 5, 'https://openalex.org/institutions/I16733864', '2026-10-30 03:00:00+00'),
  (1, 'T1002', 'Public Health', 'Medicine', 300, 5000, 2, 5, 'https://openalex.org/institutions/I16733864', '2026-10-30 03:00:00+00'),
  (1, 'T1003', 'Machine Learning', 'Computer Science', 200, 3000, 3, 5, 'https://openalex.org/institutions/I16733864', '2026-10-30 03:00:00+00'),
  (1, 'T1004', 'Semiconductor Devices', 'Engineering', 150, 2500, 4, 5, 'https://openalex.org/institutions/I16733864', '2026-10-30 03:00:00+00'),
  (1, 'T1005', 'Materials Chemistry', 'Chemistry', 100, 1800, 5, 5, 'https://openalex.org/institutions/I16733864', '2026-10-30 03:00:00+00'),
  (10, 'T2001', 'Artificial Intelligence', 'Computer Science', 900, 20000, 1, 5, 'https://openalex.org/institutions/I97018004', '2026-10-30 03:00:00+00'),
  (10, 'T2002', 'Human-Computer Interaction', 'Computer Science', 400, 8000, 2, 5, 'https://openalex.org/institutions/I97018004', '2026-10-30 03:00:00+00'),
  (10, 'T2003', 'Robotics', 'Engineering', 350, 6000, 3, 5, 'https://openalex.org/institutions/I97018004', '2026-10-30 03:00:00+00'),
  (10, 'T2004', 'Biomedical Imaging', 'Medicine', 300, 5500, 4, 5, 'https://openalex.org/institutions/I97018004', '2026-10-30 03:00:00+00'),
  (10, 'T2005', 'Climate Science', 'Environmental Science', 120, 2000, 5, 5, 'https://openalex.org/institutions/I97018004', '2026-10-30 03:00:00+00');

-- Sequences ------------------------------------------------------------------
select setval('source_id_seq', 1000);
select setval('institution_id_seq', 1000);
select setval('program_id_seq', 1000);
select setval('admission_stat_id_seq', 1000);
select setval('admission_requirement_id_seq', 1000);
select setval('cost_id_seq', 1000);
select setval('strength_id_seq', 1000);
select setval('institution_stat_id_seq', 1000);

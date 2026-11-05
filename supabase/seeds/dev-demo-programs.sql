-- =====================================================================
-- NUR FÜR DIE DEV-DATENBANK. Niemals in der Live-Datenbank ausführen.
--
-- Alle Hochschulen und Studiengänge hier sind erfunden, damit keine falsche
-- Aussage über eine echte Hochschule entsteht. Die Demo-Hochschulen haben
-- keinen market_access und erscheinen deshalb nicht in der Hochschulsuche.
-- Das Skript lässt sich wiederholen: Es ersetzt die alten Demodaten.
-- =====================================================================

begin;

delete from public.universities where registry_id like 'PTH-DE-DE0000%';

insert into public.universities (registry_id, name, institution_type, ownership, lifecycle_status, is_listed)
values
  ('PTH-DE-DE000001', 'Universität Nordstadt (Demo)', 'university', 'public', 'active', false),
  ('PTH-DE-DE000002', 'Technische Universität Bergstadt (Demo)', 'university', 'public', 'active', false),
  ('PTH-DE-DE000003', 'Hochschule Rheintal (Demo)', 'university_of_applied_sciences', 'public', 'active', false),
  ('PTH-DE-DE000004', 'Hochschule Seeland (Demo)', 'university_of_applied_sciences', 'public', 'active', false),
  ('PTH-DE-DE000005', 'Private Hochschule Mittelfeld (Demo)', 'university_of_applied_sciences', 'private', 'active', false),
  ('PTH-DE-DE000006', 'Duale Hochschule Waldau (Demo)', 'dual_university', 'public', 'active', false);

insert into public.programs (
  university_id, name, degree, degree_title, field, study_models, languages, semesters, ects,
  start_terms, tuition_per_semester_eur, city, admission_type, min_total_ects, min_grade,
  accepted_fields, ects_requirements, tests, language_requirement, deadline_winter, deadline_summer,
  notes, is_demo
)
select
  u.id, v.name, v.degree, v.title, v.field, v.models::text[], v.languages::text[], v.semesters, v.ects,
  v.terms::text[], v.tuition, v.city, v.admission, v.min_ects, v.min_grade,
  v.accepted::text[], v.areas::jsonb, v.tests::text[], v.lang_req, v.d_winter, v.d_summer,
  v.notes, true
from (values
  ('PTH-DE-DE000001', 'Informatik', 'master', 'M.Sc.', 'informatik', '{full_time,part_time}', '{de,en}', 4, 120,
   '{winter,summer}', 0, 'Nordstadt', 'requirements', 180, 2.7,
   '{informatik,wirtschaftsinformatik}', '[{"area":"informatik","ects":60},{"area":"mathematik","ects":18}]', '{}', 'Deutsch B2 oder Englisch B2', '15.07.', '15.01.',
   'Fehlende Grundlagen bis 30 ECTS können als Auflage nachgeholt werden.'),
  ('PTH-DE-DE000001', 'Data Science', 'master', 'M.Sc.', 'informatik', '{full_time}', '{en}', 4, 120,
   '{winter}', 0, 'Nordstadt', 'selection', 180, 2.3,
   '{informatik,wirtschaftsinformatik,naturwissenschaften}', '[{"area":"mathematik","ects":30},{"area":"informatik","ects":30}]', '{Motivationsschreiben}', 'Englisch C1', '31.05.', null,
   'Auswahl nach Note, Fachbezug und Motivationsschreiben.'),
  ('PTH-DE-DE000001', 'Betriebswirtschaftslehre', 'master', 'M.Sc.', 'wirtschaft', '{full_time}', '{de}', 4, 120,
   '{winter}', 0, 'Nordstadt', 'nc', 180, 2.0,
   '{wirtschaft,wirtschaftsinformatik}', '[{"area":"wirtschaft","ects":90}]', '{}', 'Deutsch C1', '15.06.', null,
   'Die Zulassung richtet sich nach der Rangfolge der Noten im jeweiligen Jahrgang.'),
  ('PTH-DE-DE000002', 'Wirtschaftsinformatik', 'master', 'M.Sc.', 'wirtschaftsinformatik', '{full_time}', '{de,en}', 4, 120,
   '{winter,summer}', 0, 'Bergstadt', 'requirements', 180, 2.5,
   '{wirtschaftsinformatik,informatik,wirtschaft}', '[{"area":"informatik","ects":30},{"area":"wirtschaft","ects":30}]', '{}', 'Deutsch B2', '15.07.', '15.01.',
   null),
  ('PTH-DE-DE000002', 'Maschinenbau', 'master', 'M.Sc.', 'ingenieurwesen', '{full_time}', '{de}', 4, 120,
   '{winter,summer}', 0, 'Bergstadt', 'requirements', 210, 3.0,
   '{ingenieurwesen}', '[{"area":"technik","ects":90},{"area":"mathematik","ects":24}]', '{}', 'Deutsch C1', '15.07.', '15.01.',
   'Mit 180 ECTS ist eine Zulassung unter Auflagen möglich.'),
  ('PTH-DE-DE000002', 'Management and Technology', 'master', 'M.Sc.', 'wirtschaft', '{full_time}', '{en}', 4, 120,
   '{winter}', 0, 'Bergstadt', 'selection', 180, 2.3,
   '{wirtschaft,ingenieurwesen,wirtschaftsinformatik}', '[{"area":"wirtschaft","ects":30},{"area":"technik","ects":30}]', '{GMAT oder GRE,Auswahlgespräch}', 'Englisch C1', '31.05.', null,
   'Mehrstufiges Eignungsverfahren.'),
  ('PTH-DE-DE000003', 'Wirtschaftsingenieurwesen', 'master', 'M.Eng.', 'ingenieurwesen', '{full_time,part_time}', '{de}', 3, 90,
   '{winter,summer}', 0, 'Rheintal', 'requirements', 210, 2.9,
   '{ingenieurwesen,wirtschaft}', '[{"area":"technik","ects":45},{"area":"wirtschaft","ects":20}]', '{}', 'Deutsch B2', '15.07.', '15.01.',
   null),
  ('PTH-DE-DE000003', 'Angewandte Informatik', 'master', 'M.Sc.', 'informatik', '{full_time,part_time}', '{de}', 3, 90,
   '{winter,summer}', 0, 'Rheintal', 'requirements', 210, 3.0,
   '{informatik,wirtschaftsinformatik,ingenieurwesen}', '[{"area":"informatik","ects":45}]', '{}', 'Deutsch B2', '15.07.', '15.01.',
   'Mit 180 ECTS sind 30 zusätzliche ECTS im ersten Studienjahr möglich.'),
  ('PTH-DE-DE000004', 'Digital Business Management', 'master', 'M.A.', 'wirtschaftsinformatik', '{part_time,extra_occupational}', '{de}', 5, 90,
   '{winter,summer}', 650, 'Seeland', 'requirements', 180, null,
   '{}', '[{"area":"wirtschaft","ects":20}]', '{Ein Jahr Berufserfahrung}', 'Deutsch B2', '31.08.', '28.02.',
   'Berufsbegleitend mit Präsenzphasen an Wochenenden.'),
  ('PTH-DE-DE000004', 'Nachhaltige Energiesysteme', 'master', 'M.Eng.', 'ingenieurwesen', '{full_time}', '{de,en}', 3, 90,
   '{winter}', 0, 'Seeland', 'open', 210, null,
   '{ingenieurwesen,naturwissenschaften}', '[{"area":"technik","ects":30},{"area":"mathematik","ects":15}]', '{}', 'Englisch B2', '15.09.', null,
   null),
  ('PTH-DE-DE000005', 'Strategy and Consulting', 'master', 'M.Sc.', 'wirtschaft', '{full_time}', '{en}', 4, 120,
   '{winter,summer}', 5900, 'Mittelfeld', 'selection', 180, 2.5,
   '{}', '[{"area":"wirtschaft","ects":24}]', '{GMAT oder GRE,Auswahlgespräch}', 'Englisch C1', '30.06.', '30.11.',
   'Fachfremde Bewerbungen sind ausdrücklich möglich.'),
  ('PTH-DE-DE000005', 'Applied Artificial Intelligence', 'master', 'M.Sc.', 'informatik', '{full_time,extra_occupational}', '{en}', 4, 120,
   '{winter}', 4800, 'Mittelfeld', 'selection', 180, 2.7,
   '{informatik,wirtschaftsinformatik,naturwissenschaften,ingenieurwesen}', '[{"area":"informatik","ects":20},{"area":"mathematik","ects":15}]', '{Programmierprüfung}', 'Englisch B2', '31.07.', null,
   null),
  ('PTH-DE-DE000006', 'Business Engineering', 'master', 'M.Eng.', 'wirtschaftsinformatik', '{dual,extra_occupational}', '{de}', 4, 120,
   '{winter}', 0, 'Waldau', 'requirements', 210, 2.7,
   '{wirtschaftsinformatik,wirtschaft,ingenieurwesen}', '[]', '{Arbeitsvertrag mit Partnerunternehmen}', 'Deutsch B2', '31.07.', null,
   null),
  ('PTH-DE-DE000003', 'Informatik', 'bachelor', 'B.Sc.', 'informatik', '{full_time,dual}', '{de}', 7, 210,
   '{winter}', 0, 'Rheintal', 'open', null, null,
   '{}', '[]', '{}', 'Deutsch C1', '15.09.', null, null),
  ('PTH-DE-DE000001', 'Wirtschaftswissenschaften', 'bachelor', 'B.Sc.', 'wirtschaft', '{full_time}', '{de}', 6, 180,
   '{winter}', 0, 'Nordstadt', 'nc', null, null,
   '{}', '[]', '{}', 'Deutsch C1', '15.07.', null, null),
  ('PTH-DE-DE000002', 'Maschinenbau', 'bachelor', 'B.Sc.', 'ingenieurwesen', '{full_time}', '{de}', 6, 180,
   '{winter,summer}', 0, 'Bergstadt', 'requirements', null, null,
   '{}', '[]', '{Eignungstest}', 'Deutsch C1', '15.07.', '15.01.', null),
  ('PTH-DE-DE000001', 'Informatik', 'bachelor', 'B.Sc.', 'informatik', '{full_time}', '{de}', 6, 180,
   '{winter}', 0, 'Nordstadt', 'open', null, null,
   '{}', '[]', '{}', 'Deutsch C1', '15.09.', null, null),
  ('PTH-DE-DE000001', 'Physik', 'bachelor', 'B.Sc.', 'naturwissenschaften', '{full_time}', '{de}', 6, 180,
   '{winter}', 0, 'Nordstadt', 'open', null, null,
   '{}', '[]', '{}', 'Deutsch C1', '15.09.', null, null),
  ('PTH-DE-DE000002', 'Wirtschaftsinformatik', 'bachelor', 'B.Sc.', 'wirtschaftsinformatik', '{full_time}', '{de}', 6, 180,
   '{winter}', 0, 'Bergstadt', 'requirements', null, null,
   '{}', '[]', '{}', 'Deutsch C1', '15.07.', null, null),
  ('PTH-DE-DE000003', 'Wirtschaftsinformatik', 'bachelor', 'B.Sc.', 'wirtschaftsinformatik', '{full_time,dual}', '{de}', 7, 210,
   '{winter}', 0, 'Rheintal', 'open', null, null,
   '{}', '[]', '{}', 'Deutsch C1', '15.09.', null, null),
  ('PTH-DE-DE000004', 'Betriebswirtschaft', 'bachelor', 'B.A.', 'wirtschaft', '{full_time}', '{de}', 6, 180,
   '{winter,summer}', 0, 'Seeland', 'nc', null, null,
   '{}', '[]', '{}', 'Deutsch C1', '15.07.', '15.01.', null),
  ('PTH-DE-DE000006', 'Wirtschaftsingenieurwesen', 'bachelor', 'B.Eng.', 'ingenieurwesen', '{dual}', '{de}', 7, 210,
   '{winter}', 0, 'Waldau', 'requirements', null, null,
   '{}', '[]', '{Arbeitsvertrag mit Partnerunternehmen}', 'Deutsch B2', '31.07.', null, null)
) as v(reg, name, degree, title, field, models, languages, semesters, ects, terms, tuition, city, admission,
       min_ects, min_grade, accepted, areas, tests, lang_req, d_winter, d_summer, notes)
join public.universities u on u.registry_id = v.reg;

-- Studienpläne der Bachelor: ECTS pro Fachgebiet
update public.programs p
set curriculum_ects = v.plan::jsonb
from (values
  ('PTH-DE-DE000001', 'Informatik', '{"informatik":105,"mathematik":36,"wirtschaft":0,"technik":6}'),
  ('PTH-DE-DE000001', 'Physik', '{"informatik":12,"mathematik":50,"wirtschaft":0,"technik":20}'),
  ('PTH-DE-DE000001', 'Wirtschaftswissenschaften', '{"informatik":6,"mathematik":18,"wirtschaft":120,"technik":0}'),
  ('PTH-DE-DE000002', 'Maschinenbau', '{"informatik":8,"mathematik":30,"wirtschaft":6,"technik":110}'),
  ('PTH-DE-DE000002', 'Wirtschaftsinformatik', '{"informatik":60,"mathematik":18,"wirtschaft":60,"technik":0}'),
  ('PTH-DE-DE000003', 'Informatik', '{"informatik":120,"mathematik":30,"wirtschaft":6,"technik":12}'),
  ('PTH-DE-DE000003', 'Wirtschaftsinformatik', '{"informatik":70,"mathematik":15,"wirtschaft":65,"technik":6}'),
  ('PTH-DE-DE000004', 'Betriebswirtschaft', '{"informatik":6,"mathematik":12,"wirtschaft":125,"technik":0}'),
  ('PTH-DE-DE000006', 'Wirtschaftsingenieurwesen', '{"informatik":10,"mathematik":20,"wirtschaft":70,"technik":70}')
) as v(reg, name, plan)
join public.universities u on u.registry_id = v.reg
where p.university_id = u.id and p.name = v.name and p.degree = 'bachelor';

commit;

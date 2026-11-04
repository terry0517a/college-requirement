import {
  char,
  integer,
  jsonb,
  numeric,
  pgTable,
  serial,
  text,
  timestamp,
} from 'drizzle-orm/pg-core'
import type { SieveStep, TwApplyRequirement, UacSubject, UsSatRequirement } from './types'

// Read-only mirror of supabase/migrations/0001-0005. schema.test.ts checks every
// column here exists in the database.

const provenance = {
  sourceId: integer('source_id').notNull(),
  sourceUrl: text('source_url').notNull(),
  fetchedAt: timestamp('fetched_at', { withTimezone: true, mode: 'date' }).notNull(),
}

const num = (name: string) => numeric(name, { mode: 'number' })

export const source = pgTable('source', {
  id: serial('id').primaryKey(),
  code: text('code').notNull(),
  name: text('name').notNull(),
  url: text('url').notNull(),
  license: text('license'),
})

export const institution = pgTable('institution', {
  id: serial('id').primaryKey(),
  countryCode: char('country_code', { length: 2 }).notNull(),
  nameEn: text('name_en').notNull(),
  nameZh: text('name_zh'),
  domain: text('domain').notNull(),
  webUrl: text('web_url'),
  openalexId: text('openalex_id'),
  rorId: text('ror_id'),
  control: text('control', { enum: ['public', 'private'] }),
  ...provenance,
  scorecardId: integer('scorecard_id'),
  city: text('city'),
  region: text('region'),
  openalexCheckedAt: timestamp('openalex_checked_at', { withTimezone: true, mode: 'date' }),
})

export const field = pgTable('field', {
  code: text('code').primaryKey(),
  nameZh: text('name_zh').notNull(),
  nameEn: text('name_en').notNull(),
  sort: integer('sort').notNull(),
})

export const program = pgTable('program', {
  id: serial('id').primaryKey(),
  institutionId: integer('institution_id').notNull(),
  nameZh: text('name_zh'),
  nameEn: text('name_en'),
  fieldCode: text('field_code'),
  level: text('level').notNull(),
  ...provenance,
  code: text('code'),
})

export const admissionStat = pgTable('admission_stat', {
  id: serial('id').primaryKey(),
  programId: integer('program_id').notNull(),
  year: integer('year').notNull(),
  pathway: text('pathway').notNull(),
  minScore: num('min_score'),
  admittedCount: integer('admitted_count'),
  subjects: jsonb('subjects').$type<UacSubject[]>().notNull(),
  tiebreak: text('tiebreak'),
  ...provenance,
  admissionRate: num('admission_rate'),
  sieve: jsonb('sieve').$type<SieveStep[] | null>(),
})

export const admissionRequirement = pgTable('admission_requirement', {
  id: serial('id').primaryKey(),
  programId: integer('program_id').notNull(),
  year: integer('year').notNull(),
  pathway: text('pathway').notNull(),
  systemCode: text('system_code').notNull(),
  requirement: jsonb('requirement').$type<TwApplyRequirement | UsSatRequirement>().notNull(),
  ...provenance,
})

export const cost = pgTable('cost', {
  id: serial('id').primaryKey(),
  institutionId: integer('institution_id').notNull(),
  year: integer('year').notNull(),
  residency: text('residency', { enum: ['local', 'out_of_state', 'international'] }).notNull(),
  tuition: num('tuition').notNull(),
  currency: char('currency', { length: 3 }).notNull(),
  ...provenance,
})

export const strength = pgTable('strength', {
  id: serial('id').primaryKey(),
  institutionId: integer('institution_id').notNull(),
  topicId: text('topic_id').notNull(),
  topicName: text('topic_name').notNull(),
  fieldName: text('field_name').notNull(),
  worksCount: integer('works_count').notNull(),
  citedByCount: integer('cited_by_count').notNull(),
  rank: integer('rank').notNull(),
  ...provenance,
})

export const institutionStat = pgTable('institution_stat', {
  id: serial('id').primaryKey(),
  institutionId: integer('institution_id').notNull(),
  year: integer('year').notNull(),
  studentSize: integer('student_size'),
  completionRate: num('completion_rate'),
  medianEarnings: num('median_earnings'),
  currency: char('currency', { length: 3 }),
  ...provenance,
})

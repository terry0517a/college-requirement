/** JSON shapes stored in jsonb columns (see the cac-apply design doc 5.1). */

export type TwApplyStage2 = {
  gsat_weights?: Record<string, number | null>
  stage1_pct?: number | null
  items?: { name: string; threshold: string | null; pct: number | null }[]
  tiebreak_order?: string[]
  review_items?: string | null
  exam_date?: string | null
  expected_candidates?: number | null
  fee?: number | null
  website?: string | null
}

export type TwApplyRequirement = {
  cac_code: string
  group: string | null
  gender: string | null
  quota: number | null
  thresholds: Record<string, string | null>
  multipliers: Record<string, number | null>
  extra: Record<string, string>
  stage2?: TwApplyStage2
  sources?: { sieve_image?: string; rules_page?: string }
}

type Range = { p25: number; p75: number } | null

export type UsSatRequirement = {
  sat: { rw: Range; math: Range; total: Range }
  act: { composite: Range }
}

export type SieveStep = {
  order: number
  label: string
  subjects: string[]
  min_score: number
}

export type UacSubject = { subject: string; weight: number }

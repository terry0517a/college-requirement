import Link from 'next/link'
import type { Locale } from '@/i18n/config'
import type { Dictionary } from '@/i18n/dictionaries'
import type { ExploreParams } from '@/lib/explore-params'

type FieldOption = { code: string; name_zh: string; name_en: string }

const input = 'w-full rounded border border-line bg-page px-2 py-1.5'

/** Plain GET form: works without JS. Server component; values come from parsed params. */
export default function ExploreFilters({
  params,
  fields,
  locale,
  dict,
}: {
  params: ExploreParams
  fields: FieldOption[]
  locale: Locale
  dict: Dictionary
}) {
  const t = dict.explore
  return (
    <form
      action={`/${locale}/explore`}
      method="get"
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
    >
      <label className="block text-sm sm:col-span-2 lg:col-span-3">
        <span className="text-subtle">{t.keyword}</span>
        <input
          type="search"
          name="q"
          defaultValue={params.q ?? ''}
          maxLength={100}
          placeholder={t.keywordPlaceholder}
          className={input}
        />
      </label>
      <label className="block text-sm">
        <span className="text-subtle">{dict.region.label}</span>
        <select name="region" defaultValue={params.region} className={input}>
          <option value="all">{dict.region.all}</option>
          <option value="tw">{dict.region.tw}</option>
          <option value="us">{dict.region.us}</option>
        </select>
      </label>
      <label className="block text-sm">
        <span className="text-subtle">{t.field}</span>
        <select name="field" defaultValue={params.field ?? ''} className={input}>
          <option value="">{t.fieldAny}</option>
          {fields.map((f) => (
            <option key={f.code} value={f.code}>
              {locale === 'zh' ? f.name_zh : f.name_en}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        <span className="text-subtle">{t.control}</span>
        <select name="control" defaultValue={params.control ?? ''} className={input}>
          <option value="">{t.controlAny}</option>
          <option value="public">{t.public}</option>
          <option value="private">{t.private}</option>
        </select>
      </label>
      <label className="block text-sm">
        <span className="text-subtle">{t.maxTuition}</span>
        <input
          type="number"
          name="maxTuition"
          min={1}
          step={1}
          inputMode="numeric"
          defaultValue={params.maxTuition ?? ''}
          className={input}
        />
      </label>
      <label className="block text-sm">
        <span className="text-subtle">{t.size}</span>
        <select name="size" defaultValue={params.size ?? ''} className={input}>
          <option value="">{t.sizeAny}</option>
          <option value="small">{t.small}</option>
          <option value="medium">{t.medium}</option>
          <option value="large">{t.large}</option>
        </select>
      </label>
      <div className="flex items-end gap-3 sm:col-span-2 lg:col-span-1">
        <button type="submit" className="rounded bg-brand px-4 py-2 text-white">
          {t.apply}
        </button>
        <Link href={`/${locale}/explore`} prefetch={false} className="py-2 text-sm underline">
          {t.reset}
        </Link>
      </div>
    </form>
  )
}

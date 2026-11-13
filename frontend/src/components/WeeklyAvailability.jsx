import { t } from '../i18n/index.js'
import { PRESETS, trainingDays } from '../lib/availability.js'

export default function WeeklyAvailability({ value, onChange, errors }) {
  function update(index, patch) {
    onChange(value.map((d, i) => (i === index ? { ...d, ...patch } : d)))
  }

  return (
    <div className="availability">
      <div className="availability__head">
        <span className="field__label">{t('goal.weeklyAvailability')}</span>
        <span className="availability__count">
          {t('goal.trainingDays', { n: trainingDays(value) })}
        </span>
      </div>
      <p className="field__hint">{t('goal.availabilityHint')}</p>

      <div className="availability__presets">
        <button type="button" className="link-subtle" onClick={() => onChange(PRESETS.sameEveryDay())}>
          {t('goal.presetSame')}
        </button>
        <button type="button" className="link-subtle" onClick={() => onChange(PRESETS.weekdaysShort())}>
          {t('goal.presetWeekdaysShort')}
        </button>
      </div>

      <div className="availability__grid" role="group" aria-label={t('goal.weeklyAvailability')}>
        {value.map((d, i) => {
          const rest = d.slots === 0
          const dayError = errors?.days?.[d.day]
          return (
            <div className="availability__row" key={d.day}>
              <span className="availability__day">{t(`weekday.${d.day}`)}</span>
              <div className="days-picker" role="group" aria-label={t('goal.slots')}>
                {[0, 1, 2].map(n => (
                  <button
                    key={n}
                    type="button"
                    className={`days-picker__btn availability__slot${d.slots === n ? ' days-picker__btn--active' : ''}`}
                    onClick={() => update(i, { slots: n })}
                  >
                    {n}
                  </button>
                ))}
              </div>
              <input
                className={`field__input availability__km${dayError ? ' availability__km--invalid' : ''}`}
                aria-invalid={dayError ? true : undefined}
                type="number"
                min="0"
                max="60"
                step="0.5"
                inputMode="decimal"
                disabled={rest}
                placeholder={t('goal.noCap')}
                aria-label={t('goal.maxKm')}
                value={d.maxKm ?? ''}
                onChange={e => update(i, { maxKm: e.target.value === '' ? null : Number(e.target.value) })}
              />
              <label className="availability__quality">
                <input
                  type="checkbox"
                  disabled={rest}
                  checked={d.qualityAllowed}
                  onChange={e => update(i, { qualityAllowed: e.target.checked })}
                />
                {t('goal.quality')}
              </label>
              {dayError && (
                <span className="field__error availability__row-error">{t(dayError)}</span>
              )}
            </div>
          )
        })}
      </div>
      {errors?.summary && <span className="field__error">{t(errors.summary)}</span>}
    </div>
  )
}

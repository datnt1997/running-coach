import { Link } from 'react-router-dom'
import { t } from '../i18n/index.js'

// Shown above a plan when no workout has a heart-rate target: the profile still lacks
// the values the zones need. The app never fills the gap with an estimate.
export default function ZoneHint({ plan }) {
  const anyTarget = plan.weeks.some(w => w.workouts.some(x => x.targetZone))
  if (anyTarget) return null
  return (
    <p className="hint" style={{ marginBottom: '1rem' }}>
      {t('plan.zonesMissing')} <Link to="/profile">{t('plan.zonesMissingLink')}</Link>
    </p>
  )
}

import { Aviso, Button } from '@camaron/ui'
import { t } from './i18n.js'

// A view whose data did not come: what failed, the server's own message, and a way out.
export default function Failed({ title, detail, onRetry }) {
  return <Aviso tone="error" title={title} detail={detail}
    action={onRetry ? <Button size="sm" onClick={onRetry}>{t('retry')}</Button> : null} />
}

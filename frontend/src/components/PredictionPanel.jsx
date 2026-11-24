import { useTranslation } from 'react-i18next';
import { AlertTriangle } from 'lucide-react';
import { Disclaimer, ProbBar, RiskBadge } from './ui';
import { pick } from '../utils';

/** Shows an AI risk result: risk level, top diseases with confidence, top factors, disclaimer. */
export default function PredictionPanel({ p, compact }) {
  const { t } = useTranslation();
  if (!p) return <p className="text-sm text-slate-500">{t('prediction.none')}</p>;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{t('prediction.risk')}:</span><RiskBadge level={p.risk_level} />
        {p.safety_net_triggered && <span className="badge bg-red-100 text-red-800"><AlertTriangle className="h-3 w-3" />{t('prediction.safetyNet')}</span>}
      </div>
      <div>
        <div className="mb-2 text-sm font-medium">{t('prediction.top')}</div>
        {p.top_predictions.map((x) => <ProbBar key={x.disease_key} label={pick(x, 'name')} value={x.probability} />)}
      </div>
      {!compact && p.top_factors?.length > 0 && (
        <div>
          <div className="mb-1 text-sm font-medium">{t('prediction.factors')}</div>
          <ul className="list-inside list-disc text-sm text-slate-700">{p.top_factors.map((f) => <li key={f.feature}>{pick(f, 'label')}</li>)}</ul>
        </div>
      )}
      <Disclaimer />
    </div>
  );
}

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, CheckCircle2, Info, Loader2 } from 'lucide-react';
import api from '../api/client';
import { pick } from '../utils';

export const Spinner = () => (
  <div className="flex justify-center py-10 text-brand-600"><Loader2 className="h-6 w-6 animate-spin" /></div>
);

export const Empty = ({ text }) => {
  const { t } = useTranslation();
  return <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">{text || t('common.empty')}</div>;
};

export const ErrorBox = ({ error }) => {
  const { t } = useTranslation();
  return error ? <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{t('common.loadError')}</div> : null;
};

export const PageHeader = ({ title, children }) => (
  <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
    <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
    <div className="flex flex-wrap gap-2">{children}</div>
  </div>
);

const SEV = { low: 'bg-green-100 text-green-800', medium: 'bg-amber-100 text-amber-800', high: 'bg-red-100 text-red-800' };
const SEV_ICON = { low: CheckCircle2, medium: Info, high: AlertTriangle };

export function SeverityBadge({ level, kind = 'severity' }) {
  const { t } = useTranslation();
  if (!level) return <span className="text-slate-400">-</span>;
  const Icon = SEV_ICON[level];
  return <span className={`badge ${SEV[level]}`}><Icon className="h-3 w-3" />{t(`${kind}.${level}`)}</span>;
}
export const RiskBadge = ({ level }) => <SeverityBadge level={level} kind="risk" />;

const STATUS = { healthy: 'bg-green-100 text-green-800', under_observation: 'bg-amber-100 text-amber-800', sick: 'bg-red-100 text-red-800',
  recovered: 'bg-blue-100 text-blue-800', sold: 'bg-slate-100 text-slate-600', deceased: 'bg-slate-200 text-slate-600' };
export const StatusBadge = ({ status }) => {
  const { t } = useTranslation();
  return <span className={`badge ${STATUS[status] || 'bg-slate-100'}`}>{t(`status.${status}`)}</span>;
};

export const Disclaimer = () => {
  const { t } = useTranslation();
  return (
    <div className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
      <Info className="mt-0.5 h-4 w-4 shrink-0" /><span>{t('disclaimer')}</span>
    </div>
  );
};

export const ProbBar = ({ label, value }) => (
  <div className="mb-2">
    <div className="mb-1 flex justify-between text-sm"><span>{label}</span><span className="font-medium">{Math.round(value * 100)}%</span></div>
    <div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-brand-500" style={{ width: `${Math.round(value * 100)}%` }} /></div>
  </div>
);

export const Field = ({ label, children, hint }) => (
  <label className="block">
    <span className="label">{label}</span>
    {children}
    {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
  </label>
);

export function Pager({ page, pageSize, total, onChange }) {
  const { t } = useTranslation();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  return (
    <div className="mt-3 flex items-center justify-center gap-3 text-sm">
      <button className="btn-secondary btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>{t('common.prev')}</button>
      <span>{page} / {pages}</span>
      <button className="btn-secondary btn-sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>{t('common.next')}</button>
    </div>
  );
}

// ---- lookups (symptoms, diseases) cached for the session ----
let lookupPromise = null;
export function useLookups() {
  const [data, setData] = useState(null);
  useEffect(() => {
    lookupPromise = lookupPromise || api.get('/lookups').then((r) => r.data).catch(() => { lookupPromise = null; return null; });
    lookupPromise.then(setData);
  }, []);
  return data;
}

export function SymptomChips({ value, onChange }) {
  const lk = useLookups();
  if (!lk) return <Spinner />;
  const toggle = (k) => onChange(value.includes(k) ? value.filter((x) => x !== k) : [...value, k]);
  return (
    <div className="flex flex-wrap gap-2">
      {lk.symptoms.map((s) => {
        const on = value.includes(s.key);
        return (
          <button type="button" key={s.key} onClick={() => toggle(s.key)} aria-pressed={on}
            className={`min-h-[44px] rounded-full border px-4 py-2 text-sm transition ${on ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`}>
            {pick(s, 'name')}
          </button>
        );
      })}
    </div>
  );
}

export function DiseaseName({ k }) {
  const lk = useLookups();
  const d = lk?.diseases.find((x) => x.key === k);
  return <>{d ? pick(d, 'name') : k}</>;
}

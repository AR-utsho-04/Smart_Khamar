import { useState } from 'react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import { Download } from 'lucide-react';
import { download, errText, useFetch } from '../api/client';
import { Field, PageHeader } from '../components/ui';

export default function Reports() {
  const { t } = useTranslation();
  const farms = useFetch('/farms');
  const [farmId, setFarmId] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const params = (extra = {}) => ({ farm_id: farmId || undefined, from: from || undefined, to: to || undefined, ...extra });
  const get = (url, extra, name) => download(url, params(extra), name).catch((e) => toast.error(errText(e, t)));
  const Row = ({ title, desc, children }) => (
    <div className="card flex flex-wrap items-center justify-between gap-3"><div><div className="font-semibold">{title}</div><div className="text-sm text-slate-500">{desc}</div></div><div className="flex gap-2">{children}</div></div>
  );
  const Btn = ({ onClick, label }) => <button className="btn-secondary" onClick={onClick}><Download className="h-4 w-4" />{label}</button>;

  return (
    <div className="mx-auto max-w-3xl space-y-3">
      <PageHeader title={t('nav.reports')} />
      <div className="card grid gap-3 sm:grid-cols-3">
        <Field label={t('farms.farm')}><select className="input" value={farmId} onChange={(e) => setFarmId(e.target.value)}><option value="">{t('dashboard.allFarms')}</option>{farms.data?.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></Field>
        <Field label={t('reports.from')}><input className="input" type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label={t('reports.to')}><input className="input" type="date" value={to} onChange={(e) => setTo(e.target.value)} /></Field>
      </div>
      <Row title={t('reports.herd')} desc={t('reports.herdDesc')}><Btn label="PDF" onClick={() => get('/reports/herd', { format: 'pdf' }, 'herd_report.pdf')} /><Btn label="CSV" onClick={() => get('/reports/herd', { format: 'csv' }, 'herd_report.csv')} /></Row>
      <Row title={t('reports.vacc')} desc={t('reports.vaccDesc')}><Btn label="PDF" onClick={() => get('/reports/vaccinations-due', { format: 'pdf' }, 'vaccinations_due.pdf')} /><Btn label="CSV" onClick={() => get('/reports/vaccinations-due', { format: 'csv' }, 'vaccinations_due.csv')} /></Row>
      <Row title={t('reports.treatments')} desc={t('reports.treatmentsDesc')}><Btn label="CSV" onClick={() => get('/reports/treatments', {}, 'treatments.csv')} /></Row>
      <p className="text-xs text-slate-500">{t('reports.cardHint')}</p>
    </div>
  );
}

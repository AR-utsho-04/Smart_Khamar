import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useFetch } from '../api/client';
import { useAuth } from '../AuthContext';
import { Empty, ErrorBox, PageHeader, Spinner, useLookups } from '../components/ui';
import { fmtDate, pick } from '../utils';

const COLORS = ['#dc2626', '#ea580c', '#d97706', '#7c3aed', '#0891b2', '#db2777', '#4d7c0f'];

const Stat = ({ label, value, tone = 'text-slate-900', to }) => {
  const body = <div className="card"><div className="text-xs uppercase tracking-wide text-slate-500">{label}</div><div className={`mt-1 text-3xl font-bold ${tone}`}>{value}</div></div>;
  return to ? <Link to={to}>{body}</Link> : body;
};

function Bars({ data, colors, labelFn }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0) || 1;
  const keys = Object.keys(data);
  if (!keys.length) return <Empty />;
  return (
    <div className="space-y-2">
      {keys.map((k) => (
        <div key={k}>
          <div className="mb-1 flex justify-between text-sm"><span>{labelFn(k)}</span><span className="font-medium">{data[k]}</span></div>
          <div className="h-2 rounded-full bg-slate-100"><div className={`h-2 rounded-full ${colors[k] || 'bg-brand-500'}`} style={{ width: `${(data[k] / total) * 100}%` }} /></div>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const farms = useFetch('/farms');
  const [farmId, setFarmId] = useState('');
  const { data: s, loading, error } = useFetch('/dashboard/summary', farmId ? { farm_id: farmId } : {});
  const iotSum = useFetch('/iot/summary', farmId ? { farm_id: farmId } : {});
  const lk = useLookups();
  if (loading || !s) return error ? <ErrorBox error={error} /> : <Spinner />;

  const dName = (k) => { const d = lk?.diseases.find((x) => x.key === k); return d ? pick(d, 'name') : k; };
  const diseaseKeys = [...new Set(s.disease_cases_over_time.flatMap((r) => Object.keys(r).filter((k) => k !== 'date')))];
  const high = s.risk_distribution.high;

  return (
    <div>
      <PageHeader title={t('dashboard.title')}>
        {farms.data?.length > 1 && (
          <select className="input w-auto" value={farmId} onChange={(e) => setFarmId(e.target.value)}>
            <option value="">{t('dashboard.allFarms')}</option>
            {farms.data.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        )}
      </PageHeader>
      {user.role === 'farmer' && s.animals_total === 0 && (
        <div className="card mb-4 text-center"><p className="mb-3 text-sm">{t('dashboard.getStarted')}</p><Link to="/farms" className="btn-primary">{t('nav.farms')}</Link></div>
      )}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t('dashboard.animals')} value={s.animals_total} to="/animals" />
        <Stat label={t('dashboard.openAlerts')} value={Object.values(s.open_alerts_by_severity).reduce((a, b) => a + b, 0)} tone="text-amber-600" to="/alerts" />
        <Stat label={t('dashboard.highRisk')} value={high} tone="text-red-600" />
        <Stat label={t('dashboard.vaccCoverage')} value={`${s.vaccination_coverage_pct}%`} tone="text-brand-600" />
      </div>

      {iotSum.data?.devices > 0 && (
        <div className="mt-4"><div className="mb-2 flex items-center justify-between"><h2 className="font-semibold">{t('iot.dashTitle')}</h2><Link className="text-sm font-medium text-brand-700" to="/devices">{t('nav.devices')}</Link></div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={t('iot.devices')} value={iotSum.data.devices} to="/devices" />
            <Stat label={t('iot.online')} value={iotSum.data.online} tone="text-green-600" />
            <Stat label={t('iot.anomalous')} value={iotSum.data.anomalous_animals_24h} tone="text-red-600" />
            <Stat label={t('iot.openAlerts')} value={iotSum.data.open_iot_alerts} tone="text-amber-600" to="/alerts" /></div></div>)}

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="card"><h2 className="mb-3 font-semibold">{t('dashboard.byStatus')}</h2>
          <Bars data={s.animals_by_status} labelFn={(k) => t(`status.${k}`)} colors={{ healthy: 'bg-green-500', under_observation: 'bg-amber-500', sick: 'bg-red-500', recovered: 'bg-blue-500' }} /></div>
        <div className="card"><h2 className="mb-3 font-semibold">{t('dashboard.riskDist')}</h2>
          <Bars data={s.risk_distribution} labelFn={(k) => t(`risk.${k}`)} colors={{ low: 'bg-green-500', medium: 'bg-amber-500', high: 'bg-red-500' }} /></div>
        <div className="card"><h2 className="mb-3 font-semibold">{t('dashboard.bySpecies')}</h2>
          <Bars data={s.animals_by_species} labelFn={(k) => t(`species.${k}`)} colors={{}} /></div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="card"><h2 className="mb-3 font-semibold">{t('dashboard.tempTrend')}</h2>
          {s.temperature_trend.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={s.temperature_trend}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} fontSize={11} />
                <YAxis domain={['auto', 'auto']} fontSize={11} /><Tooltip /><Line type="monotone" dataKey="avg_temp" stroke="#2f9e5e" strokeWidth={2} dot={false} name="°C" /></LineChart>
            </ResponsiveContainer>) : <Empty />}
        </div>
        <div className="card"><h2 className="mb-3 font-semibold">{t('dashboard.cases')}</h2>
          {s.disease_cases_over_time.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={s.disease_cases_over_time}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} fontSize={11} />
                <YAxis allowDecimals={false} fontSize={11} /><Tooltip formatter={(v, n) => [v, dName(n)]} /><Legend formatter={dName} />
                {diseaseKeys.map((k, i) => <Bar key={k} dataKey={k} stackId="a" fill={COLORS[i % COLORS.length]} />)}</BarChart>
            </ResponsiveContainer>) : <Empty />}
        </div>
      </div>

      <div className="card mt-4"><h2 className="mb-3 font-semibold">{t('dashboard.upcoming')}</h2>
        {s.upcoming_reminders.length ? (
          <ul className="divide-y">{s.upcoming_reminders.map((r) => (
            <li key={r.id} className="flex items-center justify-between py-2 text-sm">
              <Link className="font-medium text-brand-700" to={`/animals/${r.animal_id}`}>{r.animal_tag}</Link>
              <span className="mx-2 flex-1 truncate">{r.title}</span>
              <span className={r.status === 'overdue' ? 'font-medium text-red-600' : ''}>{fmtDate(r.due_date)}</span>
            </li>))}</ul>) : <Empty />}
      </div>
    </div>
  );
}

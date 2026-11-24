import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Download, Pencil, Plus } from 'lucide-react';
import { Disclaimer } from '../components/ui';
import api, { download, errText, useFetch } from '../api/client';
import { useAuth } from '../AuthContext';
import { DiseaseName, Empty, Field, Pager, RiskBadge, Spinner, StatusBadge, useLookups } from '../components/ui';
import PredictionPanel from '../components/PredictionPanel';
import { fmtDate, fmtDateTime, pick, todayInput } from '../utils';

function Timeline({ id }) {
  const { t } = useTranslation();
  const { data, loading } = useFetch(`/animals/${id}/timeline`);
  if (loading) return <Spinner />;
  if (!data?.length) return <Empty />;
  return <ul className="space-y-2">{data.map((x, i) => (
    <li key={i} className="flex gap-3 text-sm"><span className="w-28 shrink-0 text-xs text-slate-500">{fmtDateTime(x.at)}</span>
      <span className="badge bg-slate-100 text-slate-700">{t(`timeline.${x.type}`)}</span><span className="min-w-0 flex-1">{x.summary}</span></li>))}</ul>;
}

function RecordsTab({ id }) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const chart = useFetch(`/animals/${id}/records`, { page_size: 100 });
  const list = useFetch(`/animals/${id}/records`, { page, page_size: 10 });
  const series = [...(chart.data?.items || [])].reverse().filter((r) => r.temperature_c != null).map((r) => ({ d: r.recorded_at.slice(5, 10), temp: r.temperature_c }));
  return (
    <div className="space-y-4">
      {series.length > 1 && <ResponsiveContainer width="100%" height={200}><LineChart data={series}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="d" fontSize={11} /><YAxis domain={['auto', 'auto']} fontSize={11} /><Tooltip /><Line dataKey="temp" stroke="#dc2626" strokeWidth={2} dot={false} name="°C" /></LineChart></ResponsiveContainer>}
      {list.loading ? <Spinner /> : !list.data?.items.length ? <Empty /> : (
        <div className="overflow-x-auto"><table className="w-full"><thead><tr>{['records.when', 'records.temp', 'records.weight', 'records.feed', 'records.symptoms'].map((k) => <th key={k} className="th">{t(k)}</th>)}</tr></thead>
          <tbody className="divide-y">{list.data.items.map((r) => <tr key={r.id}><td className="td">{fmtDateTime(r.recorded_at)}</td><td className="td">{r.temperature_c ?? '-'}</td><td className="td">{r.weight_kg ?? '-'}</td><td className="td">{r.feed_intake_kg ?? '-'}</td><td className="td">{r.symptoms.length ? r.symptoms.join(', ') : '-'}</td></tr>)}</tbody></table></div>)}
      {list.data && <Pager page={page} pageSize={10} total={list.data.total} onChange={setPage} />}
    </div>
  );
}

function PredictionsTab({ id, canFeedback }) {
  const { t } = useTranslation();
  const lk = useLookups();
  const { data, loading, reload } = useFetch(`/animals/${id}/predictions`, { page_size: 10 });
  const [actual, setActual] = useState({});
  if (loading) return <Spinner />;
  if (!data?.items.length) return <Empty />;
  const send = async (p, confirmed) => {
    try { await api.post(`/predictions/${p.id}/feedback`, { confirmed, actual_disease_key: confirmed ? null : actual[p.id] || null }); toast.success(t('common.saved')); reload(); }
    catch (e) { toast.error(errText(e, t)); }
  };
  return (
    <div className="space-y-3">{data.items.map((p) => (
      <div key={p.id} className="rounded-lg border p-3">
        <div className="mb-2 flex items-center justify-between text-sm"><span className="text-slate-500">{fmtDateTime(p.created_at)}</span><RiskBadge level={p.risk_level} /></div>
        <PredictionPanel p={p} compact />
        {p.feedback && <p className="mt-2 text-sm">{t('prediction.vetSaid')}: <b>{p.feedback.confirmed ? t('prediction.confirmed') : t('prediction.rejected')}</b></p>}
        {canFeedback && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button className="btn-secondary btn-sm" onClick={() => send(p, true)}>{t('prediction.confirm')}</button>
            <select className="input !min-h-[36px] w-auto !py-1 text-xs" value={actual[p.id] || ''} onChange={(e) => setActual({ ...actual, [p.id]: e.target.value })}>
              <option value="">{t('prediction.actualDisease')}</option>{lk?.diseases.map((d) => <option key={d.key} value={d.key}>{pick(d, 'name')}</option>)}</select>
            <button className="btn-secondary btn-sm" onClick={() => send(p, false)}>{t('prediction.reject')}</button>
          </div>)}
      </div>))}</div>
  );
}

function RemindersTab({ id, canEdit }) {
  const { t } = useTranslation();
  const { data, loading, reload } = useFetch('/reminders', { animal_id: id, status: 'pending,overdue,done', page_size: 50 });
  const [f, setF] = useState({ type: 'checkup', title: '', due_date: todayInput() });
  const act = async (fn) => { try { await fn(); reload(); } catch (e) { toast.error(errText(e, t)); } };
  if (loading) return <Spinner />;
  return (
    <div className="space-y-3">
      {!data.items.length ? <Empty /> : <ul className="divide-y">{data.items.map((r) => (
        <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
          <span className="font-medium">{r.title}</span><span className={r.status === 'overdue' ? 'text-red-600' : 'text-slate-500'}>{fmtDate(r.due_date)} - {t(`reminderStatus.${r.status}`)}</span>
          {canEdit && r.status !== 'done' && <button className="btn-secondary btn-sm" onClick={() => act(() => api.patch(`/reminders/${r.id}`, { status: 'done' }))}>{t('reminders.markDone')}</button>}
        </li>))}</ul>}
      {canEdit && (
        <form className="grid gap-2 rounded-lg bg-slate-50 p-3 sm:grid-cols-4" onSubmit={(e) => { e.preventDefault(); act(() => api.post(`/animals/${id}/reminders`, f)).then(() => setF({ ...f, title: '' })); }}>
          <select className="input" value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>{['vaccination', 'deworming', 'checkup', 'follow_up'].map((x) => <option key={x} value={x}>{t(`reminderType.${x}`)}</option>)}</select>
          <input className="input" required placeholder={t('reminders.titlePh')} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
          <input className="input" type="date" required value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} />
          <button className="btn-primary">{t('reminders.add')}</button>
        </form>)}
    </div>
  );
}

function ConsultTab({ id, isVet, latestPredictionId }) {
  const { t } = useTranslation();
  const { data, loading, reload } = useFetch('/consultations', { animal_id: id });
  const [f, setF] = useState({ diagnosis: '', treatment: '', medicine: '', dosage: '', follow_up_date: '' });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/animals/${id}/consultations`, { ...f, treatment: f.treatment || null, medicine: f.medicine || null, dosage: f.dosage || null,
        follow_up_date: f.follow_up_date || null, prediction_id: latestPredictionId || null });
      toast.success(t('common.saved')); setF({ diagnosis: '', treatment: '', medicine: '', dosage: '', follow_up_date: '' }); reload();
    } catch (err) { toast.error(errText(err, t)); }
  };
  return (
    <div className="space-y-4">
      {isVet && (
        <form onSubmit={submit} className="grid gap-3 rounded-lg bg-slate-50 p-3 sm:grid-cols-2">
          <div className="sm:col-span-2"><Field label={t('vet.diagnosis')}><textarea className="input min-h-[70px]" required value={f.diagnosis} onChange={set('diagnosis')} /></Field></div>
          <div className="sm:col-span-2"><Field label={t('vet.treatment')}><textarea className="input min-h-[70px]" value={f.treatment} onChange={set('treatment')} /></Field></div>
          <Field label={t('vet.medicine')}><input className="input" value={f.medicine} onChange={set('medicine')} /></Field>
          <Field label={t('vet.dosage')}><input className="input" value={f.dosage} onChange={set('dosage')} /></Field>
          <Field label={t('vet.followUp')}><input className="input" type="date" value={f.follow_up_date} onChange={set('follow_up_date')} /></Field>
          <div className="flex items-end"><button className="btn-primary">{t('vet.saveConsultation')}</button></div>
        </form>)}
      {loading ? <Spinner /> : !data.items.length ? <Empty /> : (
        <ul className="space-y-2">{data.items.map((c) => (
          <li key={c.id}><Link to={`/consultations/${c.id}`} className="card block hover:bg-slate-50">
            <div className="flex justify-between text-sm"><b>{c.diagnosis}</b><span className="text-slate-500">{fmtDate(c.created_at)}</span></div>
            <div className="text-sm text-slate-600">{c.vet_name}{c.medicine ? ` - ${c.medicine}` : ''}</div></Link></li>))}</ul>)}
    </div>
  );
}


function SignalChart({ data, k, label, color }) {
  const fmt = (v) => new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return (
    <div>
      <div className="mb-1 text-sm font-medium">{label}</div>
      <ResponsiveContainer width="100%" height={150}>
        <LineChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="t" tickFormatter={fmt} fontSize={10} minTickGap={40} /><YAxis domain={['auto', 'auto']} fontSize={10} width={36} />
          <Tooltip labelFormatter={fmt} />
          <Line type="monotone" dataKey={k} stroke={color} strokeWidth={2} isAnimationActive={false} connectNulls
            dot={(p) => (p.payload.anomaly && p.cx != null && p.cy != null ? <circle key={`d${p.index}`} cx={p.cx} cy={p.cy} r={4} fill="#dc2626" /> : <g key={`d${p.index}`} />)} /></LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function IotTab({ id }) {
  const { t } = useTranslation();
  const [hours, setHours] = useState(24);
  const { data, reload } = useFetch(`/iot/animals/${id}/readings`, { hours });
  useEffect(() => { const i = setInterval(reload, 10000); return () => clearInterval(i); }, [reload]);
  if (!data) return <Spinner />;
  if (!data.devices.length && !data.total_readings) return <Empty text={t('iot.noDevice')} />;
  const L = data.latest;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">{data.devices.map((d) => (
          <span key={d.id} className={`badge ${d.status === 'online' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>{d.name}: {t(`deviceStatus.${d.status}`)}</span>))}
          <span className="text-xs text-slate-500">{t('iot.live')}</span></div>
        <select className="input !min-h-[36px] w-auto !py-1 text-sm" value={hours} onChange={(e) => setHours(Number(e.target.value))}>{[6, 24, 72].map((h) => <option key={h} value={h}>{t('iot.hours', { h })}</option>)}</select>
      </div>
      {!data.points.length ? <Empty text={t('iot.noData')} /> : (<>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {[[t('iot.latest') + ' °C', L?.temperature_c ?? '-'], [t('iot.hr'), L?.heart_rate_bpm ?? '-'], [t('iot.activity'), L?.activity_index ?? '-'], [t('iot.readings'), data.total_readings], [t('iot.flagged'), data.anomalies]].map(([k, v]) => (
            <div key={k} className="rounded-lg bg-slate-50 p-2 text-center"><div className="text-xs text-slate-500">{k}</div><div className={`text-lg font-bold ${k === t('iot.flagged') && data.anomalies ? 'text-red-600' : ''}`}>{v}</div></div>))}
        </div>
        <SignalChart data={data.points} k="temperature_c" label={t('iot.temp')} color="#dc2626" />
        <SignalChart data={data.points} k="heart_rate_bpm" label={t('iot.hr')} color="#7c3aed" />
        <SignalChart data={data.points} k="activity_index" label={t('iot.activity')} color="#2f9e5e" />
        <p className="text-xs text-slate-500">{t('iot.redDots')}</p>
      </>)}
      <Disclaimer />
    </div>
  );
}

export default function AnimalDetail() {
  const { t } = useTranslation();
  const { id } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const { data: a, loading, error, reload } = useFetch(`/animals/${id}`);
  const [tab, setTab] = useState('timeline');
  if (loading) return <Spinner />;
  if (error || !a) return <Empty text={t('common.notFound')} />;
  const farmer = user.role === 'farmer';
  const isVet = user.role === 'vet';
  const act = async (fn, msg) => { try { await fn(); if (msg) toast.success(msg); reload(); } catch (e) { toast.error(errText(e, t)); } };
  const tabs = ['timeline', 'records', 'iot', 'predictions', 'reminders', 'consultations'];

  return (
    <div className="space-y-4">
      <div className="card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold">{a.tag_no}{a.name && <span className="text-slate-500"> ({a.name})</span>}</h1>
            <p className="text-sm text-slate-600">{t(`species.${a.species}`)} - {t(`animals.${a.sex}`)}{a.age_months != null && ` - ${a.age_months} ${t('animals.months')}`}{a.weight_kg != null && ` - ${a.weight_kg} kg`}{a.breed && ` - ${a.breed}`}</p>
            <div className="mt-2 flex items-center gap-2"><StatusBadge status={a.status} />{a.latest_prediction && <RiskBadge level={a.latest_prediction.risk_level} />}</div>
          </div>
          <div className="flex flex-wrap gap-2">
            {(farmer || isVet) && <Link className="btn-primary" to={`/animals/${id}/records/new`}><Plus className="h-4 w-4" />{t('records.add')}</Link>}
            {farmer && <Link className="btn-secondary" to={`/animals/${id}/edit`}><Pencil className="h-4 w-4" />{t('common.edit')}</Link>}
            <button className="btn-secondary" onClick={() => download(`/reports/animal/${id}`, {}, `animal_${a.tag_no}.pdf`).catch((e) => toast.error(errText(e, t)))}><Download className="h-4 w-4" />{t('animals.healthCard')}</button>
          </div>
        </div>
        {(farmer || isVet) && (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3">
            <span className="text-sm text-slate-600">{t('animals.setStatus')}:</span>
            <select className="input !min-h-[36px] w-auto !py-1 text-sm" value={a.status} onChange={(e) => act(() => api.patch(`/animals/${id}/status`, { status: e.target.value }), t('common.saved'))}>
              {['healthy', 'under_observation', 'sick', 'recovered', 'sold', 'deceased'].map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}</select>
            {farmer && <>
              <button className="btn-secondary btn-sm" onClick={() => act(async () => { const r = await api.post(`/animals/${id}/reminders/generate`); toast.success(t('reminders.generated', { n: r.data.created })); })}>{t('reminders.generate')}</button>
              <button className="btn-secondary btn-sm text-red-700" onClick={() => window.confirm(t('animals.confirmArchive')) && act(async () => { await api.delete(`/animals/${id}`); nav('/animals'); })}>{t('animals.archive')}</button></>}
          </div>)}
      </div>

      {a.latest_prediction && <div className="card"><h2 className="mb-2 font-semibold">{t('prediction.latest')}</h2><PredictionPanel p={a.latest_prediction} /></div>}

      <div className="card">
        <div className="mb-3 flex gap-1 overflow-x-auto border-b">{tabs.map((k) => (
          <button key={k} onClick={() => setTab(k)} className={`whitespace-nowrap px-3 py-2 text-sm ${tab === k ? 'border-b-2 border-brand-600 font-semibold text-brand-700' : 'text-slate-500'}`}>{t(`tabs.${k}`)}</button>))}</div>
        {tab === 'timeline' && <Timeline id={id} />}
        {tab === 'records' && <RecordsTab id={id} />}
        {tab === 'iot' && <IotTab id={id} />}
        {tab === 'predictions' && <PredictionsTab id={id} canFeedback={isVet} />}
        {tab === 'reminders' && <RemindersTab id={id} canEdit={farmer || isVet} />}
        {tab === 'consultations' && <ConsultTab id={id} isVet={isVet} latestPredictionId={a.latest_prediction?.id} />}
      </div>
    </div>
  );
}

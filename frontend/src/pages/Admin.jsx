import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import api, { errText, useFetch } from '../api/client';
import { Empty, Field, PageHeader, Pager, Spinner } from '../components/ui';
import { fmtDateTime } from '../utils';

const TABS = ['users', 'thresholds', 'schedules', 'lookups', 'audit', 'model', 'jobs'];

function Users() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [role, setRole] = useState('');
  const { data, loading, reload } = useFetch('/admin/users', { page, page_size: 20, role: role || undefined });
  const act = async (fn) => { try { await fn(); reload(); } catch (e) { toast.error(errText(e, t)); } };
  return (
    <div>
      <select className="input mb-3 w-auto" value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }}><option value="">{t('admin.allRoles')}</option>{['farmer', 'vet', 'admin'].map((r) => <option key={r} value={r}>{t(`role.${r}`)}</option>)}</select>
      {loading ? <Spinner /> : (
        <div className="overflow-x-auto rounded-xl border bg-white"><table className="w-full"><thead className="bg-slate-50"><tr>{['auth.name', 'auth.email', 'auth.role', 'admin.approved', 'admin.active', ''].map((k, i) => <th key={i} className="th">{k && t(k)}</th>)}</tr></thead>
          <tbody className="divide-y">{data.items.map((u) => (
            <tr key={u.id}><td className="td">{u.name}</td><td className="td">{u.email}</td><td className="td">{t(`role.${u.role}`)}</td><td className="td">{u.is_approved ? '✓' : '—'}</td><td className="td">{u.is_active ? '✓' : '—'}</td>
              <td className="td"><div className="flex gap-2">
                {u.role === 'vet' && !u.is_approved && <button className="btn-primary btn-sm" onClick={() => act(() => api.patch(`/admin/vets/${u.id}/approve`))}>{t('admin.approve')}</button>}
                <button className="btn-secondary btn-sm" onClick={() => act(() => api.patch(`/admin/users/${u.id}`, { is_active: !u.is_active }))}>{u.is_active ? t('admin.suspend') : t('admin.activate')}</button></div></td></tr>))}</tbody></table></div>)}
      {data && <Pager page={page} pageSize={20} total={data.total} onChange={setPage} />}
    </div>
  );
}

function Thresholds() {
  const { t } = useTranslation();
  const { data, loading } = useFetch('/admin/thresholds');
  const [rows, setRows] = useState([]);
  useEffect(() => { if (data) setRows(data); }, [data]);
  if (loading) return <Spinner />;
  const set = (i, k, v) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v === '' ? null : Number(v) } : r)));
  const save = async () => { try { await api.put('/admin/thresholds', rows.map(({ species, parameter, min_value, max_value }) => ({ species, parameter, min_value, max_value }))); toast.success(t('common.saved')); } catch (e) { toast.error(errText(e, t)); } };
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">{t('admin.thresholdHelp')}</p>
      <div className="overflow-x-auto rounded-xl border bg-white"><table className="w-full"><thead className="bg-slate-50"><tr>{['Parameter', t('animals.species'), 'Min', 'Max'].map((k) => <th key={k} className="th">{k}</th>)}</tr></thead>
        <tbody className="divide-y">{rows.map((r, i) => (
          <tr key={r.id}><td className="td font-mono text-xs">{r.parameter}</td><td className="td">{r.species}</td>
            <td className="td"><input className="input !min-h-[36px] w-24" type="number" step="0.01" value={r.min_value ?? ''} onChange={(e) => set(i, 'min_value', e.target.value)} /></td>
            <td className="td"><input className="input !min-h-[36px] w-24" type="number" step="0.01" value={r.max_value ?? ''} onChange={(e) => set(i, 'max_value', e.target.value)} /></td></tr>))}</tbody></table></div>
      <button className="btn-primary" onClick={save}>{t('common.save')}</button>
    </div>
  );
}

function Schedules() {
  const { t } = useTranslation();
  const { data, loading, reload } = useFetch('/admin/schedules');
  const [f, setF] = useState({ species: 'all', name: '', kind: 'vaccination', interval_days: 180 });
  const add = async (e) => { e.preventDefault(); try { await api.post('/admin/schedules', { ...f, interval_days: Number(f.interval_days) }); setF({ ...f, name: '' }); reload(); } catch (err) { toast.error(errText(err, t)); } };
  const off = async (id) => { try { await api.delete(`/admin/schedules/${id}`); reload(); } catch (err) { toast.error(errText(err, t)); } };
  if (loading) return <Spinner />;
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">{t('admin.scheduleHelp')}</p>
      <ul className="divide-y rounded-xl border bg-white">{data.map((s) => (
        <li key={s.id} className={`flex flex-wrap items-center justify-between gap-2 p-3 text-sm ${s.is_active ? '' : 'opacity-50'}`}>
          <span><b>{s.name}</b> <span className="text-slate-500">({s.species}, {t(`reminderType.${s.kind}`)})</span></span><span>{t('admin.everyDays', { n: s.interval_days })}</span>
          {s.is_active && <button className="btn-secondary btn-sm" onClick={() => off(s.id)}>{t('admin.deactivate')}</button>}</li>))}</ul>
      <form onSubmit={add} className="card grid gap-2 sm:grid-cols-5">
        <select className="input" value={f.species} onChange={(e) => setF({ ...f, species: e.target.value })}>{['all', 'cattle', 'goat', 'sheep'].map((s) => <option key={s}>{s}</option>)}</select>
        <input className="input sm:col-span-2" required placeholder={t('admin.name')} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <select className="input" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{['vaccination', 'deworming', 'checkup'].map((k) => <option key={k} value={k}>{t(`reminderType.${k}`)}</option>)}</select>
        <input className="input" type="number" min="1" required value={f.interval_days} onChange={(e) => setF({ ...f, interval_days: e.target.value })} />
        <button className="btn-primary sm:col-span-5">{t('admin.addSchedule')}</button>
      </form>
    </div>
  );
}

function Lookups() {
  const { t } = useTranslation();
  const { data, loading, reload } = useFetch('/lookups');
  const [edit, setEdit] = useState({});
  if (loading) return <Spinner />;
  const val = (kind, item, k) => edit[`${kind}${item.id}`]?.[k] ?? item[k];
  const change = (kind, item, k, v) => setEdit({ ...edit, [`${kind}${item.id}`]: { ...(edit[`${kind}${item.id}`] || {}), [k]: v } });
  const save = async (kind, item) => {
    try { await api.put(`/admin/${kind}/${item.id}`, { key: item.key, name_en: val(kind, item, 'name_en'), name_bn: val(kind, item, 'name_bn') }); toast.success(t('common.saved')); reload(); } catch (e) { toast.error(errText(e, t)); }
  };
  const List = ({ kind, items }) => (
    <div><h3 className="mb-2 font-semibold">{t(`admin.${kind}`)}</h3>
      <ul className="space-y-2">{items.map((it) => (
        <li key={it.id} className="grid items-center gap-2 sm:grid-cols-[100px_1fr_1fr_auto]"><span className="font-mono text-xs text-slate-500">{it.key}</span>
          <input className="input !min-h-[36px]" value={val(kind, it, 'name_en')} onChange={(e) => change(kind, it, 'name_en', e.target.value)} />
          <input className="input !min-h-[36px]" value={val(kind, it, 'name_bn')} onChange={(e) => change(kind, it, 'name_bn', e.target.value)} />
          <button className="btn-secondary btn-sm" onClick={() => save(kind, it)}>{t('common.save')}</button></li>))}</ul></div>
  );
  return <div className="space-y-6"><p className="text-sm text-slate-600">{t('admin.lookupHelp')}</p><List kind="symptoms" items={data.symptoms} /><List kind="diseases" items={data.diseases} /></div>;
}

function Audit() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const { data, loading } = useFetch('/admin/audit-log', { page, page_size: 25 });
  if (loading) return <Spinner />;
  if (!data.items.length) return <Empty />;
  return (
    <div><div className="overflow-x-auto rounded-xl border bg-white"><table className="w-full"><thead className="bg-slate-50"><tr>{['admin.when', 'admin.user', 'admin.action', 'admin.entity'].map((k) => <th key={k} className="th">{t(k)}</th>)}</tr></thead>
      <tbody className="divide-y">{data.items.map((a) => <tr key={a.id}><td className="td">{fmtDateTime(a.created_at)}</td><td className="td">{a.user || '-'}</td><td className="td">{a.action}</td><td className="td">{a.entity} {a.entity_id ?? ''}</td></tr>)}</tbody></table></div>
      <Pager page={page} pageSize={25} total={data.total} onChange={setPage} /></div>
  );
}

function Model() {
  const { t } = useTranslation();
  const { data, loading } = useFetch('/admin/model');
  if (loading) return <Spinner />;
  const m = data?.metrics;
  if (!data?.available || !m) return <div className="card text-sm">{t('admin.noModel')}</div>;
  const cm = m.final.confusion_matrix;
  return (
    <div className="space-y-4">
      {m.synthetic_data && <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{t('admin.syntheticNotice')}</div>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[['Version', m.model_version], [t('admin.chosen'), m.chosen_model], [t('admin.accuracy'), m.final.accuracy], ['Macro F1', m.final.macro_f1]].map(([k, v]) => (
          <div key={k} className="card"><div className="text-xs uppercase text-slate-500">{k}</div><div className="mt-1 text-lg font-bold">{v}</div></div>))}
      </div>
      <div className="card overflow-x-auto"><h3 className="mb-2 font-semibold">{t('admin.compare')}</h3><table className="w-full"><thead><tr><th className="th">Model</th><th className="th">CV macro F1</th><th className="th">Test macro F1</th><th className="th">Test accuracy</th></tr></thead>
        <tbody>{Object.entries(m.models).map(([k, v]) => <tr key={k}><td className="td">{k}</td><td className="td">{v.cv_macro_f1}</td><td className="td">{v.test_macro_f1}</td><td className="td">{v.test_accuracy}</td></tr>)}</tbody></table></div>
      {data.anomaly_metrics ? (
        <div className="card"><h3 className="mb-2 font-semibold">{t('admin.anomalyTitle')}</h3><p className="mb-3 text-xs text-slate-500">{data.anomaly_metrics.algorithm}</p>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[[t('admin.detection'), `${Math.round(data.anomaly_metrics.episode_detection_rate * 100)}% (${data.anomaly_metrics.episodes_detected}/${data.anomaly_metrics.episodes})`],
            [t('admin.falseAlerts'), data.anomaly_metrics.false_alerts_per_animal_week], [t('admin.readingF1'), data.anomaly_metrics.reading_f1], ['Version', data.anomaly_metrics.version]].map(([k, v]) => (
            <div key={k} className="rounded-lg bg-slate-50 p-3"><div className="text-xs uppercase text-slate-500">{k}</div><div className="mt-1 text-lg font-bold">{v}</div></div>))}</div>
          <p className="mt-3 text-xs text-slate-500">{data.anomaly_metrics.limitations}</p><p className="mt-1 text-xs text-slate-500">{t('iot.synthetic')}</p></div>
      ) : <div className="card text-sm">{t('admin.noAnomalyModel')}</div>}
      <div className="card overflow-x-auto"><h3 className="mb-2 font-semibold">{t('admin.confusion')}</h3><table className="text-xs"><thead><tr><th className="th" />{cm.labels.map((l) => <th key={l} className="th">{l}</th>)}</tr></thead>
        <tbody>{cm.matrix.map((row, i) => <tr key={i}><td className="td font-semibold">{cm.labels[i]}</td>{row.map((v, j) => <td key={j} className={`td text-center ${i === j ? 'bg-green-50 font-semibold' : ''}`}>{v}</td>)}</tr>)}</tbody></table></div>
    </div>
  );
}

function Jobs() {
  const { t } = useTranslation();
  const run = async (name) => { try { const r = await api.post('/admin/jobs/run', null, { params: { name } }); toast.success(`${name}: ${r.data.result}`); } catch (e) { toast.error(errText(e, t)); } };
  return (
    <div className="space-y-3"><p className="text-sm text-slate-600">{t('admin.jobsHelp')}</p>
      <div className="flex flex-wrap gap-2">{['reminders_daily', 'missed_entry_daily', 'escalation_check', 'snooze_reactivate', 'iot_offline_check', 'iot_cleanup_daily'].map((j) => <button key={j} className="btn-secondary" onClick={() => run(j)}>{j}</button>)}</div></div>
  );
}

export default function Admin() {
  const { t } = useTranslation();
  const [tab, setTab] = useState('users');
  const Body = { users: Users, thresholds: Thresholds, schedules: Schedules, lookups: Lookups, audit: Audit, model: Model, jobs: Jobs }[tab];
  return (
    <div>
      <PageHeader title={t('nav.admin')} />
      <div className="mb-4 flex gap-1 overflow-x-auto border-b">{TABS.map((k) => (
        <button key={k} onClick={() => setTab(k)} className={`whitespace-nowrap px-3 py-2 text-sm ${tab === k ? 'border-b-2 border-brand-600 font-semibold text-brand-700' : 'text-slate-500'}`}>{t(`admin.tab_${k}`)}</button>))}</div>
      <Body />
    </div>
  );
}

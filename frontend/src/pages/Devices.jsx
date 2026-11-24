import { useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import { Battery, Copy, Cpu } from 'lucide-react';
import api, { errText, useFetch } from '../api/client';
import { useAuth } from '../AuthContext';
import { Empty, Field, PageHeader, Spinner } from '../components/ui';
import { fmtDateTime } from '../utils';

const TONE = { online: 'bg-green-100 text-green-800', offline: 'bg-red-100 text-red-800', never_seen: 'bg-slate-100 text-slate-600', unassigned: 'bg-amber-100 text-amber-800' };

function KeyPanel({ device, onClose }) {
  const { t } = useTranslation();
  const url = `${location.origin}/api/v1/iot/telemetry`;
  const curl = `curl -X POST ${url} -H "Content-Type: application/json" -H "X-Device-Key: ${device.api_key}" -d "{\\"temperature_c\\": 38.7}"`;
  const sim = `python scripts/iot_simulator.py --device-key ${device.api_key} --species cattle`;
  const copy = (txt) => navigator.clipboard?.writeText(txt).then(() => toast.success(t('devices.copied')));
  const Box = ({ label, text }) => (
    <div><div className="mb-1 text-xs font-semibold uppercase text-slate-500">{label}</div>
      <div className="flex items-start gap-2"><code className="block flex-1 overflow-x-auto whitespace-pre-wrap break-all rounded bg-slate-900 p-2 text-xs text-green-300">{text}</code>
        <button className="btn-secondary btn-sm" onClick={() => copy(text)}><Copy className="h-3 w-3" />{t('devices.copy')}</button></div></div>
  );
  return (
    <div className="card space-y-3 border-amber-300 bg-amber-50">
      <h2 className="font-semibold">{device.name}: {t('devices.keyTitle')}</h2>
      <p className="text-sm text-amber-900">{t('devices.keyHelp')}</p>
      <Box label="X-Device-Key" text={device.api_key} />
      <Box label={t('devices.endpoint')} text={url} />
      <Box label={t('devices.example')} text={curl} />
      <Box label={t('devices.simulator')} text={sim} />
      <button className="btn-secondary btn-sm" onClick={onClose}>OK</button>
    </div>
  );
}

export default function Devices() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const farmer = user.role === 'farmer';
  const devices = useFetch('/iot/devices');
  const farms = useFetch(farmer ? '/farms' : null);
  const animals = useFetch(farmer ? '/animals' : null, { page_size: 100 });
  const [f, setF] = useState({ name: '', farm_id: '', animal_id: '' });
  const [shown, setShown] = useState(null);
  const run = async (fn, msg) => { try { const r = await fn(); if (msg) toast.success(msg); devices.reload(); return r; } catch (e) { toast.error(errText(e, t)); } };
  if (devices.loading && !devices.data) return <Spinner />;
  const farmId = Number(f.farm_id || farms.data?.[0]?.id || 0);
  const myAnimals = (animals.data?.items || []).filter((a) => a.farm_id === farmId);

  const create = async (e) => {
    e.preventDefault();
    const r = await run(() => api.post('/iot/devices', { farm_id: farmId, name: f.name, animal_id: f.animal_id ? Number(f.animal_id) : null }), t('devices.created'));
    if (r) { setShown(r.data); setF({ ...f, name: '', animal_id: '' }); }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <PageHeader title={t('devices.title')} />
      <p className="text-sm text-slate-600">{t('devices.intro')}</p>
      {shown && <KeyPanel device={shown} onClose={() => setShown(null)} />}
      {!devices.data?.length ? <Empty text={t('devices.none')} /> : (
        <div className="grid gap-3 md:grid-cols-2">{devices.data.map((d) => (
          <div key={d.id} className={`card ${d.is_active ? '' : 'opacity-60'}`}>
            <div className="flex items-start justify-between gap-2">
              <div><div className="flex items-center gap-2 font-semibold"><Cpu className="h-4 w-4 text-brand-600" />{d.name}</div><div className="font-mono text-xs text-slate-500">{d.device_uid}</div></div>
              <span className={`badge ${TONE[d.status]}`}>{d.is_active ? t(`deviceStatus.${d.status}`) : t('devices.inactive')}</span>
            </div>
            <div className="mt-2 space-y-1 text-sm text-slate-600">
              <div>{t('devices.animal')}: {d.animal_id ? <Link className="font-medium text-brand-700" to={`/animals/${d.animal_id}`}>{d.animal_tag}</Link> : t('devices.noneAssigned')}</div>
              <div>{t('devices.lastSeen')}: {d.last_seen_at ? fmtDateTime(d.last_seen_at) : t('devices.never')}</div>
              <div className="flex items-center gap-1"><Battery className="h-4 w-4" />{d.battery_pct != null ? `${Math.round(d.battery_pct)}%` : '-'}</div>
            </div>
            {farmer && (
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3">
                <select className="input !min-h-[36px] w-auto !py-1 text-sm" value={d.animal_id || ''}
                  onChange={(e) => run(() => api.patch(`/iot/devices/${d.id}`, { animal_id: e.target.value ? Number(e.target.value) : null }), t('common.saved'))}>
                  <option value="">{t('devices.noneAssigned')}</option>
                  {(animals.data?.items || []).filter((a) => a.farm_id === d.farm_id).map((a) => <option key={a.id} value={a.id}>{a.tag_no}</option>)}</select>
                <button className="btn-secondary btn-sm" onClick={() => window.confirm(t('devices.rotateConfirm')) && run(() => api.post(`/iot/devices/${d.id}/rotate-key`)).then((r) => r && setShown(r.data))}>{t('devices.rotate')}</button>
                <button className="btn-secondary btn-sm" onClick={() => run(() => api.patch(`/iot/devices/${d.id}`, { is_active: !d.is_active }))}>{d.is_active ? t('devices.deactivate') : t('devices.activate')}</button>
              </div>)}
          </div>))}</div>)}
      {farmer && farms.data?.length > 0 && (
        <form onSubmit={create} className="card grid gap-3 sm:grid-cols-3">
          <h2 className="font-semibold sm:col-span-3">{t('devices.add')}</h2>
          <Field label={t('devices.name')}><input className="input" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder={t('devices.namePh')} /></Field>
          {farms.data.length > 1 && <Field label={t('farms.farm')}><select className="input" value={f.farm_id || farms.data[0].id} onChange={(e) => setF({ ...f, farm_id: e.target.value, animal_id: '' })}>{farms.data.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>}
          <Field label={t('devices.animal')}><select className="input" value={f.animal_id} onChange={(e) => setF({ ...f, animal_id: e.target.value })}><option value="">{t('devices.noneAssigned')}</option>{myAnimals.map((a) => <option key={a.id} value={a.id}>{a.tag_no}</option>)}</select></Field>
          <div className="sm:col-span-3"><button className="btn-primary">{t('devices.add')}</button></div>
        </form>)}
    </div>
  );
}

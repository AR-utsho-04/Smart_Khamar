import { useState } from 'react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import api, { errText, useFetch } from '../api/client';
import { Empty, Field, PageHeader, Spinner } from '../components/ui';

function VetAccess({ farm }) {
  const { t } = useTranslation();
  const { data, reload } = useFetch(`/farms/${farm.id}/vets`);
  const [email, setEmail] = useState('');
  const invite = async (e) => {
    e.preventDefault();
    try { await api.post(`/farms/${farm.id}/vets`, { vet_email: email }); toast.success(t('farms.invited')); setEmail(''); reload(); } catch (err) { toast.error(errText(err, t)); }
  };
  const revoke = async (vetId) => { try { await api.patch(`/farms/${farm.id}/vets/${vetId}`, { status: 'revoked' }); reload(); } catch (err) { toast.error(errText(err, t)); } };
  return (
    <div className="mt-3 border-t pt-3">
      <h3 className="mb-2 text-sm font-semibold">{t('farms.vetAccess')}</h3>
      {data?.length ? <ul className="mb-2 divide-y text-sm">{data.map((v) => (
        <li key={v.id} className="flex items-center justify-between py-2"><span>{v.vet_name} <span className="text-slate-500">({v.vet_email})</span></span>
          <span className="flex items-center gap-2"><span className="badge bg-slate-100">{t(`vetStatus.${v.status}`)}</span>{v.status !== 'revoked' && <button className="btn-secondary btn-sm" onClick={() => revoke(v.vet_id)}>{t('farms.revoke')}</button>}</span></li>))}</ul>
        : <p className="mb-2 text-sm text-slate-500">{t('farms.noVets')}</p>}
      <form onSubmit={invite} className="flex gap-2"><input className="input" type="email" required placeholder={t('farms.vetEmail')} value={email} onChange={(e) => setEmail(e.target.value)} /><button className="btn-primary">{t('farms.invite')}</button></form>
    </div>
  );
}

export default function Farms() {
  const { t } = useTranslation();
  const { data, loading, reload } = useFetch('/farms');
  const [f, setF] = useState({ name: '', district: '', address: '' });
  const create = async (e) => {
    e.preventDefault();
    try { await api.post('/farms', { name: f.name, district: f.district || null, address: f.address || null }); toast.success(t('common.saved')); setF({ name: '', district: '', address: '' }); reload(); } catch (err) { toast.error(errText(err, t)); }
  };
  if (loading) return <Spinner />;
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHeader title={t('nav.farms')} />
      {!data.length && <Empty text={t('farms.none')} />}
      {data.map((farm) => (
        <div key={farm.id} className="card"><div className="font-semibold">{farm.name}</div><div className="text-sm text-slate-500">{[farm.district, farm.address].filter(Boolean).join(', ')}</div><VetAccess farm={farm} /></div>))}
      <form onSubmit={create} className="card grid gap-3 sm:grid-cols-3">
        <h2 className="font-semibold sm:col-span-3">{t('farms.add')}</h2>
        <Field label={t('farms.name')}><input className="input" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label={t('farms.district')}><input className="input" value={f.district} onChange={(e) => setF({ ...f, district: e.target.value })} /></Field>
        <Field label={t('farms.address')}><input className="input" value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></Field>
        <div className="sm:col-span-3"><button className="btn-primary">{t('common.save')}</button></div>
      </form>
    </div>
  );
}

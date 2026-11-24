import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import api, { errText, useFetch } from '../api/client';
import { Field, PageHeader, Spinner } from '../components/ui';

export default function AnimalForm() {
  const { t } = useTranslation();
  const { id } = useParams();
  const nav = useNavigate();
  const farms = useFetch('/farms');
  const existing = useFetch(id ? `/animals/${id}` : null);
  const [f, setF] = useState({ farm_id: '', tag_no: '', name: '', species: 'cattle', breed: '', sex: 'female', dob: '', age_months: '', weight_kg: '' });
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (farms.data?.length && !f.farm_id && !id) setF((x) => ({ ...x, farm_id: farms.data[0].id })); }, [farms.data, id, f.farm_id]);
  useEffect(() => {
    const a = existing.data;
    if (a) setF({ farm_id: a.farm_id, tag_no: a.tag_no, name: a.name || '', species: a.species, breed: a.breed || '', sex: a.sex, dob: a.dob || '', age_months: a.age_months ?? '', weight_kg: a.weight_kg ?? '' });
  }, [existing.data]);

  if (farms.loading || (id && existing.loading)) return <Spinner />;
  if (!farms.data?.length) return <div className="card text-center text-sm">{t('animals.needFarm')}</div>;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const body = { tag_no: f.tag_no, name: f.name || null, breed: f.breed || null, sex: f.sex, dob: f.dob || null,
      age_months: f.dob || f.age_months === '' ? null : Number(f.age_months), weight_kg: f.weight_kg === '' ? null : Number(f.weight_kg) };
    try {
      const r = id ? await api.put(`/animals/${id}`, body) : await api.post('/animals', { ...body, farm_id: Number(f.farm_id), species: f.species });
      toast.success(t('common.saved'));
      nav(`/animals/${r.data.id}`);
    } catch (err) { toast.error(errText(err, t)); } finally { setBusy(false); }
  };

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader title={id ? t('animals.edit') : t('animals.add')} />
      <form onSubmit={submit} className="card grid gap-3 sm:grid-cols-2">
        {!id && farms.data.length > 1 && <Field label={t('farms.farm')}><select className="input" value={f.farm_id} onChange={set('farm_id')}>{farms.data.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>}
        <Field label={t('animals.tag')}><input className="input" required value={f.tag_no} onChange={set('tag_no')} placeholder="C-001" /></Field>
        <Field label={t('animals.name')}><input className="input" value={f.name} onChange={set('name')} /></Field>
        <Field label={t('animals.species')}><select className="input" value={f.species} onChange={set('species')} disabled={!!id}>{['cattle', 'goat', 'sheep'].map((s) => <option key={s} value={s}>{t(`species.${s}`)}</option>)}</select></Field>
        <Field label={t('animals.sex')}><select className="input" value={f.sex} onChange={set('sex')}><option value="female">{t('animals.female')}</option><option value="male">{t('animals.male')}</option></select></Field>
        <Field label={t('animals.breed')}><input className="input" value={f.breed} onChange={set('breed')} /></Field>
        <Field label={t('animals.weight')}><input className="input" type="number" step="0.1" min="0" value={f.weight_kg} onChange={set('weight_kg')} /></Field>
        <Field label={t('animals.dob')}><input className="input" type="date" value={f.dob} onChange={set('dob')} /></Field>
        <Field label={t('animals.ageMonths')} hint={t('animals.ageHint')}><input className="input" type="number" min="0" value={f.age_months} onChange={set('age_months')} disabled={!!f.dob} /></Field>
        <div className="flex gap-2 sm:col-span-2"><button className="btn-primary" disabled={busy}>{t('common.save')}</button><button type="button" className="btn-secondary" onClick={() => nav(-1)}>{t('common.cancel')}</button></div>
      </form>
    </div>
  );
}

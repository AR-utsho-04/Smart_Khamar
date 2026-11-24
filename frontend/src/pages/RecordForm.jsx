import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import api, { errText, useFetch } from '../api/client';
import { Empty, Field, PageHeader, SeverityBadge, Spinner, SymptomChips } from '../components/ui';
import PredictionPanel from '../components/PredictionPanel';
import { nowLocalInput } from '../utils';

export default function RecordForm() {
  const { t } = useTranslation();
  const { id } = useParams();
  const nav = useNavigate();
  const animal = useFetch(`/animals/${id}`);
  const [f, setF] = useState({ recorded_at: nowLocalInput(), temperature_c: '', weight_kg: '', feed_intake_kg: '', milk_yield_l: '', notes: '' });
  const [symptoms, setSymptoms] = useState([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  if (animal.loading) return <Spinner />;
  const a = animal.data;
  if (!a) return <Empty text={t('common.notFound')} />;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const num = (v) => (v === '' ? null : Number(v));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.post(`/animals/${id}/records`, {
        recorded_at: new Date(f.recorded_at).toISOString(), temperature_c: num(f.temperature_c), weight_kg: num(f.weight_kg),
        feed_intake_kg: num(f.feed_intake_kg), milk_yield_l: num(f.milk_yield_l), symptoms, notes: f.notes || null });
      setResult(r.data);
      toast.success(t('common.saved'));
    } catch (err) { toast.error(errText(err, t), { duration: 6000 }); } finally { setBusy(false); }
  };

  if (result) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <PageHeader title={`${t('records.result')} - ${a.tag_no}`} />
        <div className="card"><PredictionPanel p={result.prediction} />{!result.prediction && <p className="text-xs text-slate-500">{t('prediction.noModel')}</p>}</div>
        {result.alerts.length > 0 && (
          <div className="card"><h2 className="mb-2 font-semibold">{t('records.alertsCreated')}</h2>
            <ul className="space-y-1 text-sm">{result.alerts.map((x) => <li key={x.id} className="flex items-center gap-2"><SeverityBadge level={x.severity} />{t(`alertType.${x.type}`)}</li>)}</ul></div>
        )}
        <div className="flex gap-2"><Link className="btn-primary" to={`/animals/${id}`}>{t('records.backToAnimal')}</Link>
          <button className="btn-secondary" onClick={() => { setResult(null); setSymptoms([]); setF({ ...f, temperature_c: '', notes: '' }); }}>{t('records.addAnother')}</button></div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title={`${t('records.add')} - ${a.tag_no}`} />
      <form onSubmit={submit} className="card space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t('records.when')}><input className="input" type="datetime-local" required value={f.recorded_at} onChange={set('recorded_at')} /></Field>
          <Field label={t('records.temp')}><input className="input" type="number" step="0.1" min="35" max="43" value={f.temperature_c} onChange={set('temperature_c')} /></Field>
          <Field label={t('records.weight')}><input className="input" type="number" step="0.1" min="0" value={f.weight_kg} onChange={set('weight_kg')} /></Field>
          <Field label={t('records.feed')}><input className="input" type="number" step="0.01" min="0" value={f.feed_intake_kg} onChange={set('feed_intake_kg')} /></Field>
          {a.species === 'cattle' && a.sex === 'female' && <Field label={t('records.milk')}><input className="input" type="number" step="0.1" min="0" value={f.milk_yield_l} onChange={set('milk_yield_l')} /></Field>}
        </div>
        <div><div className="label">{t('records.symptoms')}</div><SymptomChips value={symptoms} onChange={setSymptoms} /></div>
        <Field label={t('records.notes')}><textarea className="input min-h-[80px]" value={f.notes} onChange={set('notes')} /></Field>
        <div className="flex gap-2"><button className="btn-primary" disabled={busy}>{t('records.submit')}</button><button type="button" className="btn-secondary" onClick={() => nav(-1)}>{t('common.cancel')}</button></div>
      </form>
    </div>
  );
}

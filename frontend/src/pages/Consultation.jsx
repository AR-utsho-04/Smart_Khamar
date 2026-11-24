import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import api, { errText, useFetch } from '../api/client';
import { Empty, PageHeader, Spinner } from '../components/ui';
import { fmtDate, fmtDateTime } from '../utils';

export default function Consultation() {
  const { t } = useTranslation();
  const { id } = useParams();
  const { data: c, loading, reload } = useFetch(`/consultations/${id}`);
  const [body, setBody] = useState('');
  if (loading) return <Spinner />;
  if (!c) return <Empty text={t('common.notFound')} />;
  const send = async (e) => {
    e.preventDefault();
    try { await api.post(`/consultations/${id}/comments`, { body }); setBody(''); reload(); } catch (err) { toast.error(errText(err, t)); }
  };
  const Row = ({ label, value }) => value ? <div><div className="text-xs uppercase text-slate-500">{label}</div><div className="text-sm">{value}</div></div> : null;
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageHeader title={t('vet.consultation')}><Link className="btn-secondary" to={`/animals/${c.animal_id}`}>{c.animal_tag}</Link></PageHeader>
      <div className="card space-y-3">
        <Row label={t('vet.diagnosis')} value={c.diagnosis} /><Row label={t('vet.treatment')} value={c.treatment} /><Row label={t('vet.medicine')} value={c.medicine} />
        <Row label={t('vet.dosage')} value={c.dosage} /><Row label={t('vet.followUp')} value={c.follow_up_date && fmtDate(c.follow_up_date)} />
        <div className="text-xs text-slate-500">{c.vet_name} - {fmtDateTime(c.created_at)}</div>
      </div>
      <div className="card">
        <h2 className="mb-2 font-semibold">{t('vet.comments')}</h2>
        {c.comments.length ? <ul className="mb-3 space-y-2">{c.comments.map((m) => (
          <li key={m.id} className="rounded-lg bg-slate-50 p-2 text-sm"><div className="text-xs text-slate-500">{m.user_name} ({t(`role.${m.role}`)}) - {fmtDateTime(m.created_at)}</div>{m.body}</li>))}</ul> : <p className="mb-3 text-sm text-slate-500">{t('vet.noComments')}</p>}
        <form onSubmit={send} className="flex gap-2"><input className="input" required value={body} onChange={(e) => setBody(e.target.value)} placeholder={t('vet.writeComment')} /><button className="btn-primary">{t('vet.send')}</button></form>
      </div>
    </div>
  );
}

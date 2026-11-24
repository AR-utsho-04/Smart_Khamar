import { useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import api, { errText, useFetch } from '../api/client';
import { useAuth } from '../AuthContext';
import { Empty, PageHeader, Pager, Spinner } from '../components/ui';
import { fmtDate } from '../utils';

export default function Reminders() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [tab, setTab] = useState('pending,overdue');
  const [page, setPage] = useState(1);
  const { data, loading, reload } = useFetch('/reminders', { status: tab, page, page_size: 20 });
  const done = async (id) => { try { await api.patch(`/reminders/${id}`, { status: 'done' }); toast.success(t('common.saved')); reload(); } catch (e) { toast.error(errText(e, t)); } };
  return (
    <div>
      <PageHeader title={t('nav.reminders')} />
      <div className="mb-3 flex gap-1 border-b">{[['pending,overdue', 'reminders.upcoming'], ['done', 'reminders.done']].map(([k, label]) => (
        <button key={k} onClick={() => { setTab(k); setPage(1); }} className={`px-3 py-2 text-sm ${tab === k ? 'border-b-2 border-brand-600 font-semibold text-brand-700' : 'text-slate-500'}`}>{t(label)}</button>))}</div>
      {loading ? <Spinner /> : !data.items.length ? <Empty /> : (
        <ul className="divide-y rounded-xl border bg-white">{data.items.map((r) => (
          <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
            <div><Link className="font-semibold text-brand-700" to={`/animals/${r.animal_id}`}>{r.animal_tag}</Link><span className="ml-2">{r.title}</span></div>
            <div className="flex items-center gap-3"><span className={r.status === 'overdue' ? 'font-medium text-red-600' : 'text-slate-500'}>{fmtDate(r.due_date)} - {t(`reminderStatus.${r.status}`)}</span>
              {r.status !== 'done' && ['farmer', 'vet'].includes(user.role) && <button className="btn-secondary btn-sm" onClick={() => done(r.id)}>{t('reminders.markDone')}</button>}</div>
          </li>))}</ul>)}
      {data && <Pager page={page} pageSize={20} total={data.total} onChange={setPage} />}
    </div>
  );
}

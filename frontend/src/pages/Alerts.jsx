import { useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import api, { errText, useFetch } from '../api/client';
import { Empty, ErrorBox, PageHeader, Pager, SeverityBadge, Spinner } from '../components/ui';
import { fmtDateTime, pick } from '../utils';

export default function Alerts() {
  const { t } = useTranslation();
  const [status, setStatus] = useState('open');
  const [severity, setSeverity] = useState('');
  const [page, setPage] = useState(1);
  const { data, loading, error, reload } = useFetch('/alerts', { status, severity: severity || undefined, page, page_size: 15 });
  const act = async (id, action, body) => { try { await api.patch(`/alerts/${id}/${action}`, body); reload(); } catch (e) { toast.error(errText(e, t)); } };

  return (
    <div>
      <PageHeader title={t('nav.alerts')}>
        <select className="input w-auto" value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }}>
          <option value="">{t('alerts.allSeverities')}</option>{['high', 'medium', 'low'].map((s) => <option key={s} value={s}>{t(`severity.${s}`)}</option>)}</select>
      </PageHeader>
      <div className="mb-3 flex gap-1 overflow-x-auto border-b">{['open', 'acknowledged', 'snoozed', 'resolved', 'all'].map((s) => (
        <button key={s} onClick={() => { setStatus(s); setPage(1); }} className={`whitespace-nowrap px-3 py-2 text-sm ${status === s ? 'border-b-2 border-brand-600 font-semibold text-brand-700' : 'text-slate-500'}`}>{t(`alertStatus.${s}`)}</button>))}</div>
      {loading ? <Spinner /> : error ? <ErrorBox error={error} /> : !data.items.length ? <Empty /> : (
        <div className="space-y-2">{data.items.map((a) => (
          <div key={a.id} className={`card border-l-4 ${a.severity === 'high' ? 'border-l-red-500' : a.severity === 'medium' ? 'border-l-amber-500' : 'border-l-green-500'}`}>
            <div className="mb-1 flex flex-wrap items-center gap-2"><SeverityBadge level={a.severity} /><span className="text-xs text-slate-500">{t(`alertType.${a.type}`)} - {fmtDateTime(a.created_at)}</span>
              {a.escalated && <span className="badge bg-red-100 text-red-800">{t('alerts.escalated')}</span>}</div>
            <p className="text-sm">{pick(a, 'message')}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {a.animal_id && <Link className="btn-secondary btn-sm" to={`/animals/${a.animal_id}`}>{a.animal_tag}</Link>}
              {(a.status === 'open' || a.status === 'snoozed') && <button className="btn-primary btn-sm" onClick={() => act(a.id, 'acknowledge')}>{t('alerts.acknowledge')}</button>}
              {a.status === 'open' && [1, 6, 24].map((h) => <button key={h} className="btn-secondary btn-sm" onClick={() => act(a.id, 'snooze', { hours: h })}>{t('alerts.snooze', { h })}</button>)}
              {a.status !== 'resolved' && <button className="btn-secondary btn-sm" onClick={() => act(a.id, 'resolve')}>{t('alerts.resolve')}</button>}
            </div>
          </div>))}</div>)}
      {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
    </div>
  );
}

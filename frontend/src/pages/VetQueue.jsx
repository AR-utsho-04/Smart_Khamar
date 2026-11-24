import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useFetch } from '../api/client';
import { Empty, ErrorBox, PageHeader, RiskBadge, Spinner, StatusBadge } from '../components/ui';
import { fmtDate } from '../utils';

export default function VetQueue() {
  const { t } = useTranslation();
  const { data, loading, error } = useFetch('/consultations/queue');
  return (
    <div>
      <PageHeader title={t('vet.queue')} />
      {loading ? <Spinner /> : error ? <ErrorBox error={error} /> : !data.length ? <Empty text={t('vet.queueEmpty')} /> : (
        <div className="overflow-x-auto rounded-xl border bg-white"><table className="w-full"><thead className="bg-slate-50"><tr>
          {['animals.tag', 'farms.farm', 'animals.species', 'animals.status', 'animals.risk', 'vet.highAlerts', 'animals.lastRecord'].map((k) => <th key={k} className="th">{t(k)}</th>)}</tr></thead>
          <tbody className="divide-y">{data.map((a) => (
            <tr key={a.id} className="hover:bg-slate-50">
              <td className="td"><Link className="font-medium text-brand-700" to={`/animals/${a.id}`}>{a.tag_no}</Link></td><td className="td">{a.farm_name}</td><td className="td">{t(`species.${a.species}`)}</td>
              <td className="td"><StatusBadge status={a.status} /></td><td className="td"><RiskBadge level={a.latest_risk} /></td><td className="td">{a.open_high_alerts}</td><td className="td">{fmtDate(a.last_record_at)}</td></tr>))}</tbody></table></div>)}
    </div>
  );
}

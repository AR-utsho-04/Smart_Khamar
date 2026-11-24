import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Plus, Search } from 'lucide-react';
import { useFetch } from '../api/client';
import { useAuth } from '../AuthContext';
import { Empty, ErrorBox, PageHeader, Pager, RiskBadge, Spinner, StatusBadge } from '../components/ui';
import { fmtDate } from '../utils';

export default function Animals() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [q, setQ] = useState('');
  const [species, setSpecies] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const { data, loading, error } = useFetch('/animals', { q: q || undefined, species: species || undefined, status: status || undefined, page, page_size: 15 });

  return (
    <div>
      <PageHeader title={t('nav.animals')}>
        {user.role === 'farmer' && <Link to="/animals/new" className="btn-primary"><Plus className="h-4 w-4" />{t('animals.add')}</Link>}
      </PageHeader>
      <div className="mb-3 grid gap-2 sm:grid-cols-3">
        <div className="relative"><Search className="absolute left-3 top-3.5 h-4 w-4 text-slate-400" />
          <input className="input pl-9" placeholder={t('animals.search')} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></div>
        <select className="input" value={species} onChange={(e) => { setSpecies(e.target.value); setPage(1); }}>
          <option value="">{t('animals.allSpecies')}</option>{['cattle', 'goat', 'sheep'].map((s) => <option key={s} value={s}>{t(`species.${s}`)}</option>)}</select>
        <select className="input" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">{t('animals.allStatus')}</option>{['healthy', 'under_observation', 'sick', 'recovered', 'sold', 'deceased'].map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}</select>
      </div>
      {loading ? <Spinner /> : error ? <ErrorBox error={error} /> : !data.items.length ? <Empty /> : (
        <>
          <div className="hidden overflow-x-auto rounded-xl border bg-white md:block">
            <table className="w-full"><thead className="bg-slate-50"><tr>
              {['animals.tag', 'animals.species', 'animals.status', 'animals.risk', 'animals.lastRecord'].map((k) => <th key={k} className="th">{t(k)}</th>)}</tr></thead>
              <tbody className="divide-y">{data.items.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50">
                  <td className="td"><Link className="font-medium text-brand-700" to={`/animals/${a.id}`}>{a.tag_no}</Link>{a.name && <span className="ml-1 text-slate-500">({a.name})</span>}</td>
                  <td className="td">{t(`species.${a.species}`)}</td><td className="td"><StatusBadge status={a.status} /></td>
                  <td className="td"><RiskBadge level={a.latest_risk} /></td><td className="td">{fmtDate(a.last_record_at)}</td></tr>))}</tbody></table>
          </div>
          <div className="space-y-2 md:hidden">{data.items.map((a) => (
            <Link key={a.id} to={`/animals/${a.id}`} className="card block">
              <div className="flex items-center justify-between"><span className="font-semibold">{a.tag_no}</span><StatusBadge status={a.status} /></div>
              <div className="mt-1 flex items-center justify-between text-sm text-slate-500"><span>{t(`species.${a.species}`)}</span><RiskBadge level={a.latest_risk} /></div>
            </Link>))}</div>
          <Pager page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />
        </>
      )}
    </div>
  );
}

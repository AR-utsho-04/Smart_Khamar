import { useState } from 'react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import { Download, Upload } from 'lucide-react';
import api, { errText, useFetch } from '../api/client';
import { Field, PageHeader, Spinner } from '../components/ui';

export default function Import() {
  const { t } = useTranslation();
  const farms = useFetch('/farms');
  const [farmId, setFarmId] = useState('');
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState(null);
  if (farms.loading) return <Spinner />;
  const fid = farmId || farms.data?.[0]?.id;

  const upload = async (e) => {
    e.preventDefault();
    if (!file || !fid) return;
    const fd = new FormData();
    fd.append('file', file);
    fd.append('farm_id', fid);
    setBusy(true);
    try { const r = await api.post('/records/import', fd); setReport(r.data); toast.success(t('import.done')); } catch (err) { toast.error(errText(err, t)); } finally { setBusy(false); }
  };

  const downloadErrors = () => {
    const rows = ['row,field,message', ...report.errors.map((x) => `${x.row},${x.field},"${x.message.replace(/"/g, '""')}"`)];
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([rows.join('\n')], { type: 'text/csv' }));
    a.download = 'import_errors.csv';
    a.click();
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHeader title={t('import.title')}><a className="btn-secondary" href="/sample_health_data.csv" download><Download className="h-4 w-4" />{t('import.sample')}</a></PageHeader>
      <form onSubmit={upload} className="card space-y-3">
        <p className="text-sm text-slate-600">{t('import.help')}</p>
        <code className="block overflow-x-auto rounded bg-slate-100 p-2 text-xs">tag_no,recorded_at,temperature_c,weight_kg,feed_intake_kg,milk_yield_l,symptoms,notes</code>
        {farms.data?.length > 1 && <Field label={t('farms.farm')}><select className="input" value={fid} onChange={(e) => setFarmId(e.target.value)}>{farms.data.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></Field>}
        <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files[0])} className="block w-full text-sm" />
        <button className="btn-primary" disabled={!file || busy}><Upload className="h-4 w-4" />{t('import.upload')}</button>
      </form>
      {report && (
        <div className="card space-y-3">
          <div className="grid grid-cols-3 gap-2 text-center"><div><div className="text-2xl font-bold">{report.total_rows}</div><div className="text-xs text-slate-500">{t('import.total')}</div></div>
            <div><div className="text-2xl font-bold text-green-600">{report.imported}</div><div className="text-xs text-slate-500">{t('import.imported')}</div></div>
            <div><div className="text-2xl font-bold text-red-600">{report.failed}</div><div className="text-xs text-slate-500">{t('import.failed')}</div></div></div>
          {report.errors.length > 0 && (<>
            <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">{t('import.row')}</th><th className="th">{t('import.field')}</th><th className="th">{t('import.message')}</th></tr></thead>
              <tbody className="divide-y">{report.errors.map((x, i) => <tr key={i}><td className="td">{x.row}</td><td className="td">{x.field}</td><td className="td">{x.message}</td></tr>)}</tbody></table></div>
            <button className="btn-secondary btn-sm" onClick={downloadErrors}>{t('import.downloadErrors')}</button></>)}
        </div>)}
    </div>
  );
}

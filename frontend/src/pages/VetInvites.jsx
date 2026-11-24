import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import api, { errText, useFetch } from '../api/client';
import { Empty, PageHeader, Spinner } from '../components/ui';

export default function VetInvites() {
  const { t } = useTranslation();
  const { data, loading, reload } = useFetch('/vet/invitations');
  const respond = async (id, status) => { try { await api.patch(`/vet/invitations/${id}`, { status }); reload(); } catch (e) { toast.error(errText(e, t)); } };
  if (loading) return <Spinner />;
  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title={t('nav.invitations')} />
      {!data.length ? <Empty /> : <div className="space-y-2">{data.map((i) => (
        <div key={i.id} className="card flex flex-wrap items-center justify-between gap-2">
          <div><div className="font-semibold">{i.farm_name}</div><div className="text-sm text-slate-500">{i.owner_name}{i.district ? ` - ${i.district}` : ''}</div></div>
          {i.status === 'pending' ? <div className="flex gap-2"><button className="btn-primary btn-sm" onClick={() => respond(i.id, 'approved')}>{t('vet.accept')}</button><button className="btn-secondary btn-sm" onClick={() => respond(i.id, 'revoked')}>{t('vet.decline')}</button></div>
            : <div className="flex items-center gap-2"><span className="badge bg-green-100 text-green-800">{t('vetStatus.approved')}</span><button className="btn-secondary btn-sm" onClick={() => respond(i.id, 'revoked')}>{t('vet.leave')}</button></div>}
        </div>))}</div>}
    </div>
  );
}

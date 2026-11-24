import { useState } from 'react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import api, { errText } from '../api/client';
import { useAuth } from '../AuthContext';
import { Field, PageHeader } from '../components/ui';

export default function Profile() {
  const { t, i18n } = useTranslation();
  const { user, refresh, setLang } = useAuth();
  const [f, setF] = useState({ name: user.name, phone: user.phone || '' });
  const [pw, setPw] = useState({ old_password: '', new_password: '' });
  const save = async (e) => {
    e.preventDefault();
    try { await api.patch('/auth/me', { name: f.name, phone: f.phone || null }); await refresh(); toast.success(t('common.saved')); } catch (err) { toast.error(errText(err, t)); }
  };
  const changePw = async (e) => {
    e.preventDefault();
    try { await api.post('/auth/change-password', pw); setPw({ old_password: '', new_password: '' }); toast.success(t('profile.pwChanged')); } catch (err) { toast.error(errText(err, t)); }
  };
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <PageHeader title={t('nav.profile')} />
      <form onSubmit={save} className="card space-y-3">
        <p className="text-sm text-slate-500">{user.email} - {t(`role.${user.role}`)}</p>
        <Field label={t('auth.name')}><input className="input" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label={t('auth.phone')}><input className="input" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
        <Field label={t('profile.language')}><select className="input" value={i18n.language} onChange={(e) => setLang(e.target.value)}><option value="en">English</option><option value="bn">বাংলা</option></select></Field>
        <button className="btn-primary">{t('common.save')}</button>
      </form>
      <form onSubmit={changePw} className="card space-y-3">
        <h2 className="font-semibold">{t('profile.changePw')}</h2>
        <Field label={t('profile.oldPw')}><input className="input" type="password" required value={pw.old_password} onChange={(e) => setPw({ ...pw, old_password: e.target.value })} /></Field>
        <Field label={t('profile.newPw')} hint={t('auth.passwordHint')}><input className="input" type="password" required minLength={8} maxLength={64} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
        <button className="btn-primary">{t('profile.changePw')}</button>
      </form>
    </div>
  );
}

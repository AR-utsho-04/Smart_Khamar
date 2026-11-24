import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import api, { errText } from '../api/client';
import { useAuth } from '../AuthContext';
import { Field } from '../components/ui';

export default function Register() {
  const { t, i18n } = useTranslation();
  const { login } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ name: '', email: '', phone: '', password: '', role: 'farmer', license_no: '' });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post('/auth/register', { ...f, phone: f.phone || null, license_no: f.role === 'vet' ? f.license_no || null : null, language: i18n.language });
      await login(f.email, f.password);
      toast.success(t('auth.registered'));
      nav('/dashboard');
    } catch (err) { toast.error(errText(err, t)); } finally { setBusy(false); }
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center p-4">
      <form onSubmit={submit} className="card space-y-3">
        <h1 className="text-center text-xl font-bold text-brand-700">{t('auth.createAccount')}</h1>
        <Field label={t('auth.name')}><input className="input" required value={f.name} onChange={set('name')} /></Field>
        <Field label={t('auth.email')}><input className="input" type="email" required value={f.email} onChange={set('email')} /></Field>
        <Field label={t('auth.phone')}><input className="input" value={f.phone} onChange={set('phone')} /></Field>
        <Field label={t('auth.password')} hint={t('auth.passwordHint')}><input className="input" type="password" required minLength={8} maxLength={64} value={f.password} onChange={set('password')} /></Field>
        <Field label={t('auth.role')}>
          <select className="input" value={f.role} onChange={set('role')}>
            <option value="farmer">{t('role.farmer')}</option><option value="vet">{t('role.vet')}</option>
          </select>
        </Field>
        {f.role === 'vet' && <Field label={t('auth.license')} hint={t('auth.vetApproval')}><input className="input" value={f.license_no} onChange={set('license_no')} /></Field>}
        <button className="btn-primary w-full" disabled={busy}>{t('auth.register')}</button>
        <p className="text-center text-sm"><Link className="font-medium text-brand-700" to="/login">{t('auth.backToLogin')}</Link></p>
      </form>
    </div>
  );
}

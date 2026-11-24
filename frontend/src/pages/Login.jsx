import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../AuthContext';
import { errText } from '../api/client';
import { Field } from '../components/ui';

export default function Login() {
  const { t, i18n } = useTranslation();
  const { login, setLang } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { await login(email, password); nav('/dashboard'); } catch (err) { toast.error(errText(err, t)); } finally { setBusy(false); }
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center p-4">
      <div className="mb-3 flex justify-end">
        <div className="flex overflow-hidden rounded-lg border border-slate-300 text-sm">
          <button onClick={() => setLang('en')} className={`px-3 py-2 ${i18n.language === 'en' ? 'bg-brand-600 text-white' : ''}`}>EN</button>
          <button onClick={() => setLang('bn')} className={`px-3 py-2 ${i18n.language === 'bn' ? 'bg-brand-600 text-white' : ''}`}>বাংলা</button>
        </div>
      </div>
      <form onSubmit={submit} className="card space-y-4">
        <div className="text-center"><div className="text-4xl">🐄</div><h1 className="text-xl font-bold text-brand-700">{t('app.name')}</h1><p className="text-sm text-slate-500">{t('auth.subtitle')}</p></div>
        <Field label={t('auth.email')}><input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" /></Field>
        <Field label={t('auth.password')}><input className="input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></Field>
        <button className="btn-primary w-full" disabled={busy}>{t('auth.login')}</button>
        <p className="text-center text-sm">{t('auth.noAccount')} <Link className="font-medium text-brand-700" to="/register">{t('auth.register')}</Link></p>
        <p className="rounded-lg bg-slate-50 p-2 text-xs text-slate-500">{t('auth.demoHint')}</p>
      </form>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Bell, CalendarClock, Cpu, FileText, Home, LayoutDashboard, LogOut, Mail, Menu, PawPrint, Settings, Stethoscope, Upload, User, Users, X } from 'lucide-react';
import { useAuth } from '../AuthContext';
import api from '../api/client';

const NAV = {
  farmer: [['/dashboard', 'nav.dashboard', LayoutDashboard], ['/animals', 'nav.animals', PawPrint], ['/devices', 'nav.devices', Cpu], ['/alerts', 'nav.alerts', Bell],
    ['/reminders', 'nav.reminders', CalendarClock], ['/import', 'nav.import', Upload], ['/reports', 'nav.reports', FileText], ['/farms', 'nav.farms', Home], ['/profile', 'nav.profile', User]],
  vet: [['/dashboard', 'nav.dashboard', LayoutDashboard], ['/vet/queue', 'nav.queue', Stethoscope], ['/animals', 'nav.animals', PawPrint], ['/devices', 'nav.devices', Cpu], ['/alerts', 'nav.alerts', Bell],
    ['/reminders', 'nav.reminders', CalendarClock], ['/reports', 'nav.reports', FileText], ['/vet/invitations', 'nav.invitations', Mail], ['/profile', 'nav.profile', User]],
  admin: [['/dashboard', 'nav.dashboard', LayoutDashboard], ['/animals', 'nav.animals', PawPrint], ['/devices', 'nav.devices', Cpu], ['/alerts', 'nav.alerts', Bell],
    ['/reports', 'nav.reports', FileText], ['/admin', 'nav.admin', Settings], ['/profile', 'nav.profile', User]],
};

export default function Layout() {
  const { user, logout, setLang } = useAuth();
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (user?.role === 'vet' && !user.is_approved) return undefined;
    const load = () => api.get('/alerts/summary').then((r) => setCount(r.data.total)).catch(() => {});
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, [user]);

  const items = NAV[user.role] || [];
  const link = (to, key, Icon) => (
    <NavLink key={to} to={to} onClick={() => setOpen(false)}
      className={({ isActive }) => `flex min-h-[44px] items-center gap-3 rounded-lg px-3 py-2 text-sm ${isActive ? 'bg-brand-50 font-semibold text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`}>
      <Icon className="h-4 w-4" />{t(key)}
    </NavLink>
  );

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2">
        <div className="flex items-center gap-2">
          <button className="rounded p-2 md:hidden" onClick={() => setOpen(!open)} aria-label="menu">{open ? <X /> : <Menu />}</button>
          <span className="text-lg font-bold text-brand-700">🐄 {t('app.name')}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex overflow-hidden rounded-lg border border-slate-300 text-sm">
            <button onClick={() => setLang('en')} className={`px-3 py-2 ${i18n.language === 'en' ? 'bg-brand-600 text-white' : ''}`}>EN</button>
            <button onClick={() => setLang('bn')} className={`px-3 py-2 ${i18n.language === 'bn' ? 'bg-brand-600 text-white' : ''}`}>বাংলা</button>
          </div>
          <button className="relative rounded-lg p-2 hover:bg-slate-100" onClick={() => nav('/alerts')} aria-label={t('nav.alerts')}>
            <Bell className="h-5 w-5" />
            {count > 0 && <span className="absolute -right-0.5 -top-0.5 rounded-full bg-red-600 px-1.5 text-[10px] font-bold text-white">{count}</span>}
          </button>
          <button className="btn-secondary btn-sm" onClick={() => { logout(); nav('/login'); }}><LogOut className="h-4 w-4" /><span className="hidden sm:inline">{t('nav.logout')}</span></button>
        </div>
      </header>
      <div className="mx-auto flex max-w-7xl">
        <aside className={`${open ? 'block' : 'hidden'} fixed inset-x-0 top-[57px] z-20 max-h-[80vh] overflow-auto border-b bg-white p-3 shadow md:static md:block md:w-56 md:shrink-0 md:border-0 md:bg-transparent md:p-4 md:shadow-none`}>
          <div className="mb-3 hidden px-3 md:block"><div className="text-sm font-semibold">{user.name}</div><div className="text-xs text-slate-500">{t(`role.${user.role}`)}</div></div>
          <nav className="space-y-1">{items.map(([to, key, Icon]) => link(to, key, Icon))}</nav>
        </aside>
        <main className="min-w-0 flex-1 p-4"><Outlet /></main>
      </div>
    </div>
  );
}

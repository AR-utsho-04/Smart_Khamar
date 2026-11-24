import { Navigate, Route, Routes } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from './AuthContext';
import Layout from './components/Layout';
import { Spinner } from './components/ui';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Animals from './pages/Animals';
import AnimalForm from './pages/AnimalForm';
import AnimalDetail from './pages/AnimalDetail';
import RecordForm from './pages/RecordForm';
import Import from './pages/Import';
import Devices from './pages/Devices';
import Alerts from './pages/Alerts';
import Reminders from './pages/Reminders';
import Reports from './pages/Reports';
import Farms from './pages/Farms';
import VetQueue from './pages/VetQueue';
import VetInvites from './pages/VetInvites';
import Consultation from './pages/Consultation';
import Admin from './pages/Admin';
import Profile from './pages/Profile';

function Pending() {
  const { t } = useTranslation();
  const { refresh } = useAuth();
  return (
    <div className="card mx-auto mt-10 max-w-md text-center">
      <h1 className="mb-2 text-lg font-semibold">{t('pending.title')}</h1>
      <p className="mb-4 text-sm text-slate-600">{t('pending.text')}</p>
      <button className="btn-secondary" onClick={refresh}>{t('pending.check')}</button>
    </div>
  );
}

function Protected({ roles }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/dashboard" replace />;
  return <Layout />;
}

function Gate({ children }) {
  const { user } = useAuth();
  return user.role === 'vet' && !user.is_approved ? <Pending /> : children;
}

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <Login />} />
      <Route path="/register" element={user ? <Navigate to="/dashboard" replace /> : <Register />} />
      <Route element={<Protected />}>
        <Route path="/dashboard" element={<Gate><Dashboard /></Gate>} />
        <Route path="/animals" element={<Gate><Animals /></Gate>} />
        <Route path="/animals/new" element={<Gate><AnimalForm /></Gate>} />
        <Route path="/animals/:id" element={<Gate><AnimalDetail /></Gate>} />
        <Route path="/animals/:id/edit" element={<Gate><AnimalForm /></Gate>} />
        <Route path="/animals/:id/records/new" element={<Gate><RecordForm /></Gate>} />
        <Route path="/devices" element={<Gate><Devices /></Gate>} />
        <Route path="/import" element={<Gate><Import /></Gate>} />
        <Route path="/alerts" element={<Gate><Alerts /></Gate>} />
        <Route path="/reminders" element={<Gate><Reminders /></Gate>} />
        <Route path="/reports" element={<Gate><Reports /></Gate>} />
        <Route path="/farms" element={<Gate><Farms /></Gate>} />
        <Route path="/vet/queue" element={<Gate><VetQueue /></Gate>} />
        <Route path="/vet/invitations" element={<Gate><VetInvites /></Gate>} />
        <Route path="/consultations/:id" element={<Gate><Consultation /></Gate>} />
        <Route path="/admin" element={<Gate><Admin /></Gate>} />
        <Route path="/profile" element={<Profile />} />
      </Route>
      <Route path="*" element={<Navigate to={user ? '/dashboard' : '/login'} replace />} />
    </Routes>
  );
}

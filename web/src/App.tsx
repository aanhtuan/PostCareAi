import { Center, Loader } from '@mantine/core';
import { Navigate, Route, Routes } from 'react-router';

import { useAuth } from './auth/useAuth';
import { AppLayout } from './components/AppLayout';
import { AlertsPage } from './pages/Alerts/AlertsPage';
import { HandoverPage } from './pages/Handover/HandoverPage';
import { LiveViewPage } from './pages/LiveView/LiveViewPage';
import { LoginPage } from './pages/Login/LoginPage';
import { ManagementPage } from './pages/Management/ManagementPage';
import { OverviewPage } from './pages/Overview/OverviewPage';
import { TimelinePage } from './pages/Timeline/TimelinePage';
import { RealtimeProvider } from './realtime/RealtimeProvider';

function Protected() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <Center mih="100vh">
        <Loader />
      </Center>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return (
    <RealtimeProvider>
      <AppLayout />
    </RealtimeProvider>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Protected />}>
        <Route index element={<OverviewPage />} />
        <Route path="live" element={<LiveViewPage />} />
        <Route path="beds/:bedId/live" element={<LiveViewPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="timeline" element={<TimelinePage />} />
        <Route path="handover" element={<HandoverPage />} />
        <Route path="management" element={<ManagementPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

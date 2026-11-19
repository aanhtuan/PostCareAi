import { Center, Loader } from '@mantine/core';
import { Navigate, Route, Routes } from 'react-router';

import { RequireRole } from './auth/RequireRole';
import { useAuth } from './auth/useAuth';
import { AppLayout } from './components/AppLayout';
import { AlertsPage } from './pages/Alerts/AlertsPage';
import { DemoPage } from './pages/Demo/DemoPage';
import { CameraConfigPage } from './pages/CameraConfig/CameraConfigPage';
import { HandoverPage } from './pages/Handover/HandoverPage';
import { LiveViewPage } from './pages/LiveView/LiveViewPage';
import { FamilyPlaceholder } from './pages/Family/FamilyPlaceholder';
import { LoginPage } from './pages/Login/LoginPage';
import { ManagementPage } from './pages/Management/ManagementPage';
import { UsersPage } from './pages/Management/Users/UsersPage';
import { OverviewPage } from './pages/Overview/OverviewPage';
import { TimelinePage } from './pages/Timeline/TimelinePage';
import { RealtimeProvider } from './realtime/RealtimeProvider';

function Loading() {
  return (
    <Center mih="100vh">
      <Loader />
    </Center>
  );
}

function Protected() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  // Người nhà không vào giao diện nhân viên, không mở WebSocket nhân viên (F35 R2).
  if (user.role === 'FAMILY') return <Navigate to="/family" replace />;
  return (
    <RealtimeProvider>
      <AppLayout />
    </RealtimeProvider>
  );
}

function FamilyArea() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== 'FAMILY') return <Navigate to="/" replace />;
  return <FamilyPlaceholder />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/family" element={<FamilyArea />} />
      <Route element={<Protected />}>
        <Route index element={<OverviewPage />} />
        <Route path="live" element={<LiveViewPage />} />
        <Route path="demo" element={<DemoPage />} />
        <Route path="beds/:bedId/live" element={<LiveViewPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="timeline" element={<TimelinePage />} />
        <Route path="handover" element={<HandoverPage />} />
        <Route path="management" element={<ManagementPage />} />
        <Route
          path="management/users"
          element={
            <RequireRole roles={['ADMIN']}>
              <UsersPage />
            </RequireRole>
          }
        />
        <Route
          path="cameras/:cameraId/config"
          element={
            <RequireRole roles={['ADMIN']}>
              <CameraConfigPage />
            </RequireRole>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

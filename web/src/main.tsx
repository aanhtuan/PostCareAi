import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';
import './styles.css';

import { MantineProvider, createTheme } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';

import { App } from './App';
import { AuthProvider } from './auth/AuthContext';

const theme = createTheme({
  primaryColor: 'teal',
  fontFamily: 'system-ui, Segoe UI, Roboto, sans-serif',
});

const queryClient = new QueryClient({
  defaultOptions: {
    // Không polling: dữ liệu được làm mới qua WebSocket (F21 R8). API lỗi tạm thời giữ dữ liệu cũ.
    queries: { retry: 1, refetchOnWindowFocus: true, staleTime: 5_000 },
  },
});

const root = document.getElementById('root');
if (!root) throw new Error('Thiếu #root');

createRoot(root).render(
  <StrictMode>
    <MantineProvider theme={theme}>
      <Notifications position="top-right" />
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);

import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi as vitest } from 'vitest';

import type { DemoStatusOut, UserOut } from '../../api/types';
import { vi } from '../../i18n/vi';
import { mockFetch, renderWithProviders } from '../../test/render';
import { DemoPage } from './DemoPage';

const admin: UserOut = {
  id: 1,
  username: 'admin',
  full_name: 'Demo Admin',
  role: 'ADMIN',
  is_active: true,
  created_at: '2026-11-19T00:00:00Z',
};
const status: DemoStatusOut = {
  enabled: true,
  available: true,
  clip_id: 'pexels-8090735',
  setup: null,
  run: null,
};

function routes(data: DemoStatusOut) {
  return {
    '/api/v1/demo': data,
    '/api/v1/overview': { beds: [] },
    '/api/v1/events': { items: [], total: 0 },
    '/api/v1/alerts': { items: [], total: 0 },
    '/api/v1/sessions': { items: [], total: 0 },
  };
}

afterEach(() => vitest.restoreAllMocks());

describe('video demo', () => {
  it('labels recorded media and submits only the allowlisted clip', async () => {
    const fetch = mockFetch({ ...routes(status), '/api/v1/demo/start': {} });
    renderWithProviders(<DemoPage />, admin);
    expect(await screen.findByText(vi.demo.recorded)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: vi.demo.start }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/api/v1/demo/start',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ clip_id: 'pexels-8090735' }),
        }),
      ),
    );
  });

  it('does not expose process controls to nurses', async () => {
    mockFetch(routes(status));
    renderWithProviders(<DemoPage />, { ...admin, role: 'NURSE' });
    expect(await screen.findByText(vi.demo.adminOnly)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: vi.demo.start })).not.toBeInTheDocument();
  });

  it('disables launch when source is missing', async () => {
    mockFetch(routes({ ...status, available: false }));
    renderWithProviders(<DemoPage />, admin);
    expect(await screen.findByText(vi.demo.missing)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: vi.demo.start })).toBeDisabled();
  });

  it('shows completed-run history, correct timeline link and replay action', async () => {
    const setup = { camera_id: 8, bed_id: 8, patient_id: 8 };
    mockFetch(
      routes({
        ...status,
        setup,
        run: {
          ...setup,
          clip_id: 'pexels-8090735',
          session_id: 17,
          status: 'COMPLETED',
          started_at: '2026-11-19T00:00:00Z',
        },
      }),
    );
    renderWithProviders(<DemoPage />, admin);
    expect(await screen.findByRole('button', { name: vi.demo.replay })).toBeEnabled();
    expect(screen.getByRole('link', { name: vi.alerts.openTimeline })).toHaveAttribute(
      'href',
      '/timeline?bed=8&session=17',
    );
    expect(screen.getByText(vi.demo.openAlertsHint)).toBeInTheDocument();
    expect(screen.getAllByText(vi.demo.statuses.COMPLETED).length).toBeGreaterThan(0);
  });
});

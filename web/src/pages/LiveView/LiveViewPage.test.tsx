import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi as vitest } from 'vitest';

import type { BedStateOut, EventOut, OverviewOut, UserOut } from '../../api/types';
import { vi } from '../../i18n/vi';
import { applyMessage, flushInvalidations } from '../../realtime/invalidation';
import { mockFetch, renderWithProviders, testQueryClient } from '../../test/render';
import { LiveViewPage } from './LiveViewPage';

const nurse: UserOut = {
  id: 1,
  username: 'nurse',
  full_name: 'Nguyễn Thị Hoa',
  role: 'NURSE',
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
};
const T = '2026-10-12T07:38:34Z'; // 14:38:34 giờ VN

type Bed = OverviewOut['beds'][number];

function bed(extra: Partial<Bed> = {}): Bed {
  return {
    bed_id: 1,
    code: 'A01',
    area: 'Khu hậu phẫu',
    session: { id: 5, patient_code: 'BN-001', started_at: T, paused_at: null },
    camera: { id: 1, name: 'Camera A01', status: 'ONLINE' },
    pending_alert_count: 0,
    acknowledged_alert_count: 0,
    max_open_priority: null,
    state: null,
    ...extra,
  };
}

function camera(status: 'ONLINE' | 'OFFLINE' | 'UNKNOWN', roi: number[][] | null) {
  return {
    id: 1,
    name: 'Camera A01',
    bed_id: 1,
    bed_code: 'A01',
    source_type: 'FILE',
    source: 'clip.mp4',
    display_mode: 'RAW',
    observation_profile: 'BED_MONITORING',
    status,
    last_seen_at: T,
    config_version: 1,
    is_active: true,
    runtime: null,
    roi_polygon: roi,
  };
}

const ROI = [
  [0.2, 0.25],
  [0.8, 0.25],
  [0.8, 0.85],
  [0.2, 0.85],
];

function setup(b: Bed, cam = camera(b.camera?.status ?? 'UNKNOWN', ROI), user = nurse) {
  mockFetch({
    '/api/v1/overview': { current_shift: null, beds: [b] },
    '/api/v1/cameras/1': cam,
    '/api/v1/events': { items: [], total: 0 },
  });
  return renderWithProviders(
    <Routes>
      <Route path="/beds/:bedId/live" element={<LiveViewPage />} />
    </Routes>,
    user,
    '/beds/1/live',
  );
}

const streamImg = () => screen.queryByRole('img', { name: 'Giường A01' });

describe('LiveViewPage', () => {
  const admin: UserOut = { ...nurse, role: 'ADMIN' };

  it('only lets an admin connect a camera outside an active session', async () => {
    const { unmount } = setup(bed({ session: null }));
    await screen.findByText(vi.live.noSession);
    expect(screen.queryByRole('button', { name: vi.live.connectCamera })).toBeNull();
    unmount();
    setup(bed(), undefined, admin);
    expect(await screen.findByRole('button', { name: vi.live.connectCamera })).toBeDisabled();
  });

  it('creates a camera assigned to the selected bed', async () => {
    setup(bed({ camera: null, session: null }), undefined, admin);
    const fetchGet = globalThis.fetch;
    const post = vitest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method !== 'POST') return fetchGet(input, init);
      expect(input).toBe('/api/v1/cameras');
      expect(JSON.parse(String(init.body))).toEqual({
        name: 'Camera A01',
        source_type: 'WEBCAM',
        source: '2',
        bed_id: 1,
        observation_profile: 'BED_MONITORING',
      });
      return Response.json({ id: 3, config_version: 1 }, { status: 201 });
    });
    globalThis.fetch = post as typeof fetch;
    fireEvent.click(await screen.findByRole('button', { name: vi.live.connectCamera }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByRole('textbox', { name: vi.camera.name })).toHaveValue('Camera A01');
    expect(within(dialog).queryByLabelText(vi.common.bed)).toBeNull();
    fireEvent.change(within(dialog).getByRole('textbox', { name: vi.camera.source }), {
      target: { value: '2' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: vi.live.saveAndConnect }));
    expect(await screen.findByText(/make worker CAMERA=3/)).toBeInTheDocument();
  });

  it('waits for the new source instead of showing the old online stream', async () => {
    const previous = { ...camera('ONLINE', ROI), source: '0', source_type: 'WEBCAM' };
    const changed = { ...previous, source: '2', config_version: 2 };
    const routes = {
      '/api/v1/overview': { current_shift: null, beds: [bed({ session: null })] },
      '/api/v1/cameras/1': { ...previous, has_current_frames: true, worker_active: true },
      '/api/v1/events': { items: [], total: 0 },
    };
    const fetchGet = mockFetch(routes);
    const requests = vitest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method !== 'PATCH') return fetchGet(input);
      expect(input).toBe('/api/v1/cameras/1');
      expect(JSON.parse(String(init.body))).toMatchObject({ source: '2', bed_id: 1 });
      routes['/api/v1/cameras/1'] = { ...changed, has_current_frames: false, worker_active: false };
      return Response.json(changed);
    });
    globalThis.fetch = requests as typeof fetch;
    renderWithProviders(
      <Routes>
        <Route path="/beds/:bedId/live" element={<LiveViewPage />} />
      </Routes>,
      admin,
      '/beds/1/live',
      {},
      { ws: 'open' },
    );
    await screen.findByRole('img', { name: 'Giường A01' });
    const connect = screen.getByRole('button', { name: vi.live.connectCamera });
    await waitFor(() => expect(connect).toBeEnabled());
    fireEvent.click(connect);
    fireEvent.change(screen.getByRole('textbox', { name: vi.camera.source }), {
      target: { value: '2' },
    });
    fireEvent.click(screen.getByRole('button', { name: vi.live.saveAndConnect }));
    expect(await screen.findByText(/make worker CAMERA=1/)).toBeInTheDocument();
    expect(streamImg()).toBeNull();

    routes['/api/v1/cameras/1'] = { ...changed, has_current_frames: true, worker_active: true };
    expect(
      await screen.findByRole('img', { name: 'Giường A01' }, { timeout: 3000 }),
    ).toBeInTheDocument();
  });

  it('LiveViewPage shows bed, session and camera status', async () => {
    setup(bed());
    expect(await screen.findByText(vi.cameraStatus.ONLINE)).toBeInTheDocument();
    expect(screen.getAllByText('Giường A01').length).toBeGreaterThan(0);
    expect(screen.getByText(/Đang theo dõi/)).toBeInTheDocument();
    expect(screen.getByText(/BN-001/)).toBeInTheDocument();
    expect(screen.getByText(/14:38:34/)).toBeInTheDocument();
    const img = await screen.findByRole('img', { name: 'Giường A01' });
    expect(img.getAttribute('src')).toContain('/api/v1/cameras/1/stream.mjpeg?token=test-token');
    // Không còn hình người que mô phỏng.
    expect(screen.queryByText(/mô phỏng/)).toBeNull();
    expect(screen.queryByText(vi.live.roiNotConfigured)).toBeNull();
  });

  it('shows a single camera stream in the configured privacy mode', async () => {
    setup(bed(), { ...camera('ONLINE', ROI), display_mode: 'BLUR' });
    const display = await screen.findByRole('img', { name: 'Giường A01' });
    expect(display.getAttribute('src')).not.toContain('view=skeleton');
    expect(screen.queryByRole('img', { name: vi.live.skeletonTitle })).toBeNull();
    expect(await screen.findByText(vi.displayMode.BLUR)).toBeInTheDocument();
    expect(screen.getByText(vi.live.displayTitle)).toBeInTheDocument();
  });

  it('shows the skeleton in the same camera area when skeleton mode is configured', async () => {
    setup(bed(), { ...camera('ONLINE', ROI), display_mode: 'SKELETON' });
    const skeleton = await screen.findByRole('img', { name: vi.live.skeletonTitle });
    expect(skeleton.getAttribute('src')).toContain('view=skeleton');
    expect(streamImg()).toBeNull();
  });

  it('LiveViewPage links to the bed timeline (F22 R7)', async () => {
    setup(bed());
    const link = await screen.findByRole('link', { name: vi.timeline.title });
    expect(link.getAttribute('href')).toMatch(/^\/timeline\?bed=1&session=\d+$/);
  });

  it('LiveViewPage shows no-session label', async () => {
    setup(bed({ session: null }));
    expect(await screen.findByText(vi.live.noSession)).toBeInTheDocument();
    expect(screen.queryByText(/BN-001/)).toBeNull();
  });

  it('LiveViewPage shows "Chưa gắn camera" and no image without a camera', async () => {
    setup(bed({ camera: null }));
    expect((await screen.findAllByText(vi.camera.notAssigned)).length).toBeGreaterThan(0);
    expect(streamImg()).toBeNull();
  });

  it('LiveViewPage hides stream when camera offline', async () => {
    setup(bed({ camera: { id: 1, name: 'Camera A01', status: 'OFFLINE' } }));
    expect((await screen.findAllByText(vi.cameraStatus.OFFLINE)).length).toBeGreaterThan(0);
    expect(streamImg()).toBeNull();
  });

  it('LiveViewPage hides stream on image error', async () => {
    setup(bed());
    const img = await screen.findByRole('img', { name: 'Giường A01' });
    fireEvent.error(img);
    expect(streamImg()).toBeNull();
    expect(screen.getAllByText(vi.cameraStatus.OFFLINE).length).toBeGreaterThan(0);
  });

  it('LiveViewPage notes when the bed region is not configured', async () => {
    setup(bed(), camera('ONLINE', null));
    expect(await screen.findByText(vi.live.roiNotConfigured)).toBeInTheDocument();
    expect(screen.getByText(vi.live.askAdminForRoi)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: vi.live.drawRoi })).toBeNull();
  });

  it('allows a no-ROI observation profile to stream without a bed region', async () => {
    setup(bed(), { ...camera('ONLINE', null), observation_profile: 'ABNORMAL_MOVEMENT' });
    expect(await screen.findByRole('img', { name: 'Giường A01' })).toBeInTheDocument();
    expect(screen.queryByText(vi.live.roiNotConfigured)).toBeNull();
  });

  it.each([{ roi: null }, { roi: ROI }])(
    'links an admin to the assigned camera region ($roi)',
    async ({ roi }) => {
      setup(bed(), camera('ONLINE', roi), admin);
      const link = await screen.findByRole('link', {
        name: roi ? vi.live.editRoi : vi.live.drawRoi,
      });
      expect(link).toHaveAttribute('href', '/cameras/1/config?from=live');
    },
  );

  it('LiveViewPage shows no internal codes', async () => {
    const { container } = setup(bed());
    await screen.findByRole('img', { name: 'Giường A01' });
    const text = container.textContent ?? '';
    for (const code of ['ONLINE', 'OFFLINE', 'UNKNOWN', 'NO_OBSERVATION', 'RAW', 'FILE']) {
      expect(text).not.toContain(code);
    }
  });

  describe('realtime (F21 AC5)', () => {
    afterEach(() => {
      vitest.useRealTimers();
    });

    const state = (extra: Partial<BedStateOut> = {}): BedStateOut => ({
      bed_id: 1,
      body_state: 'LYING',
      observation_quality: 'GOOD',
      activity_level: 'LOW',
      rest_status: 'UNKNOWN',
      face_status: 'NOT_VISIBLE',
      face_signals: {
        eyes_closed: false,
        eyes_closed_prolonged: false,
        brow_down: false,
        eye_squint: false,
        nose_sneer: false,
        mouth_change: false,
      },
      updated_at: T,
      ...extra,
    });
    const ev = (extra: Partial<EventOut> = {}): EventOut => ({
      id: 30,
      event_uid: 'u30',
      session_id: 5,
      bed_id: 1,
      bed_code: 'A01',
      camera_id: 1,
      code: 'SIT_UP',
      priority: 'INFO',
      occurred_at: T,
      detected_at: T,
      created_at: T,
      confidence: 0.9,
      observation_quality: 'GOOD',
      explanation: {},
      alert_id: null,
      alert_status: null,
      ...extra,
    });

    function live(b: Bed, events: EventOut[] = []) {
      const routes: Record<string, unknown> = {
        '/api/v1/overview': { current_shift: null, beds: [b] },
        '/api/v1/cameras/1': camera(b.camera?.status ?? 'UNKNOWN', ROI),
        '/api/v1/events': { items: events, total: events.length },
      };
      const fetchFn = mockFetch(routes);
      const qc = testQueryClient();
      renderWithProviders(
        <Routes>
          <Route path="/beds/:bedId/live" element={<LiveViewPage />} />
        </Routes>,
        nurse,
        '/beds/1/live',
        {},
        { ws: 'open', qc },
      );
      const push = (type: string, payload: unknown) =>
        act(() => {
          applyMessage(qc, { type, payload, sent_at: T });
          flushInvalidations(qc);
        });
      return { qc, routes, fetchFn, push };
    }

    it('shows body state from bed.state', async () => {
      const { push } = live(bed({ state: state() }));
      expect(await screen.findByText('Nằm')).toBeInTheDocument();
      push('bed.state', state({ body_state: 'AT_EDGE' }));
      expect(await screen.findByText('Ở mép giường')).toBeInTheDocument();
      expect(screen.queryByText('Nằm')).toBeNull();
    });

    it('shows observation quality label', async () => {
      const { push } = live(bed({ state: state() }));
      expect(await screen.findByText('Quan sát tốt')).toBeInTheDocument();
      push('bed.state', state({ observation_quality: 'MULTIPLE_PEOPLE' }));
      expect(await screen.findByText('Có nhiều người trong vùng giường')).toBeInTheDocument();
      expect(document.body.textContent).not.toContain('MULTIPLE_PEOPLE');
    });

    it('shows latest event text from vi.ts', async () => {
      const { routes, push } = live(bed({ state: state() }));
      expect(await screen.findByText(vi.live.noEvent)).toBeInTheDocument();
      const e = ev({ code: 'BED_EDGE', priority: 'MEDIUM' });
      mockFetch({ ...routes, '/api/v1/events': { items: [e], total: 1 } });
      push('event.created', e);
      expect(await screen.findByText(/Bệnh nhân đang ở mép giường/)).toBeInTheDocument();
      expect(document.body.textContent).not.toContain('BED_EDGE');
    });

    it('no bed.state shows Không đủ dữ liệu quan sát', async () => {
      live(bed({ state: null }));
      expect(await screen.findByText(vi.bodyState.NO_OBSERVATION)).toBeInTheDocument();
      expect(screen.getByText(vi.live.noState)).toBeInTheDocument();
      expect(screen.queryByText('Nằm')).toBeNull();
    });

    it('keeps one observation reason and shows the labeled details without expanding anything', async () => {
      live(
        bed({
          state: state({
            body_state: 'NO_OBSERVATION',
            observation_quality: 'NO_PERSON',
            activity_level: 'UNKNOWN',
          }),
        }),
      );
      expect(await screen.findByText(vi.quality.NO_PERSON)).toBeInTheDocument();
      expect(screen.getAllByText(vi.quality.NO_PERSON)).toHaveLength(1);
      expect(screen.getByRole('rowheader', { name: vi.live.activity })).toBeVisible();
      expect(screen.getByText(vi.activity.UNKNOWN)).toBeVisible();
      expect(screen.getByRole('rowheader', { name: vi.live.rest })).toBeVisible();
      expect(screen.getByRole('rowheader', { name: vi.live.faceSignals })).toBeVisible();
    });

    it('does not show the previous body state during a camera disconnection', async () => {
      live(bed({ state: state(), camera: { id: 1, name: 'Camera A01', status: 'OFFLINE' } }));
      expect(await screen.findByText(vi.bodyState.NO_OBSERVATION)).toBeInTheDocument();
      expect(screen.queryByText('Nằm')).toBeNull();
      expect(screen.queryByText(vi.quality.GOOD)).toBeNull();
    });

    it('opens an event summary and fetches alert details by alert id', async () => {
      const cameraEvent = ev({ code: 'CAMERA_ONLINE', priority: 'LOG' });
      const edge = ev({
        id: 31,
        code: 'BED_EDGE',
        priority: 'MEDIUM',
        alert_id: 82,
        alert_status: 'PENDING',
      });
      const { routes } = live(bed({ state: state() }), [cameraEvent, edge]);
      const fetchFn = mockFetch({
        ...routes,
        '/api/v1/alerts/82': {
          id: 82,
          status: 'PENDING',
          event: edge,
          bed: { id: 1, code: 'A01' },
        },
      });
      const eventButton = await screen.findByRole('button', { name: /Camera hoạt động lại/ });
      fireEvent.click(eventButton);
      expect(eventButton).toHaveAttribute('aria-expanded', 'true');
      fireEvent.click(screen.getByRole('button', { name: /Bệnh nhân đang ở mép giường/ }));
      expect(
        await screen.findByRole('dialog', { name: vi.alerts.detailTitle }),
      ).toBeInTheDocument();
      await waitFor(() =>
        expect(fetchFn).toHaveBeenCalledWith('/api/v1/alerts/82', expect.anything()),
      );
    });

    it('no polling while WebSocket open', async () => {
      vitest.useFakeTimers({ shouldAdvanceTime: true });
      const { fetchFn } = live(bed({ state: state() }));
      expect(await screen.findByText('Nằm')).toBeInTheDocument();
      const before = fetchFn.mock.calls.length;
      await act(async () => {
        await vitest.advanceTimersByTimeAsync(30000);
      });
      expect(fetchFn.mock.calls.length).toBe(before);
    });
  });
});

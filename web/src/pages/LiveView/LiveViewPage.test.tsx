import { act, fireEvent, screen } from '@testing-library/react';
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

function setup(b: Bed, cam = camera(b.camera?.status ?? 'UNKNOWN', ROI)) {
  mockFetch({
    '/api/v1/overview': { current_shift: null, beds: [b] },
    '/api/v1/cameras/1': cam,
    '/api/v1/events': { items: [], total: 0 },
  });
  return renderWithProviders(
    <Routes>
      <Route path="/beds/:bedId/live" element={<LiveViewPage />} />
    </Routes>,
    nurse,
    '/beds/1/live',
  );
}

const streamImg = () => screen.queryByRole('img', { name: 'Giường A01' });

describe('LiveViewPage', () => {
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
  });

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
        '/api/v1/cameras/1': camera('ONLINE', ROI),
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

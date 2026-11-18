import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { BedStateOut } from '../../api/types';
import { vi } from '../../i18n/vi';
import { FaceSignalsPanel } from './FaceSignalsPanel';

type FaceSignals = BedStateOut['face_signals'];
type FaceStatus = BedStateOut['face_status'];

const NONE: FaceSignals = {
  eyes_closed: false,
  eyes_closed_prolonged: false,
  brow_down: false,
  eye_squint: false,
  nose_sneer: false,
  mouth_change: false,
};

function show(face_status: FaceStatus, signals: Partial<FaceSignals> = {}) {
  return render(
    <MantineProvider>
      <FaceSignalsPanel state={{ face_status, face_signals: { ...NONE, ...signals } }} />
    </MantineProvider>,
  );
}

describe('FaceSignalsPanel', () => {
  it('lists active face signals in Vietnamese from a bed.state payload', () => {
    show('OK', { brow_down: true, eye_squint: true, mouth_change: true });
    expect(screen.getByText(vi.faceSignal.brow_down)).toBeInTheDocument();
    expect(screen.getByText(vi.faceSignal.eye_squint)).toBeInTheDocument();
    expect(screen.getByText(vi.faceSignal.mouth_change)).toBeInTheDocument();
    expect(screen.queryByText(vi.faceSignal.eyes_closed)).not.toBeInTheDocument();
    expect(screen.queryByText(vi.live.faceNoSignal)).not.toBeInTheDocument();
  });

  it('shows prolonged eye closure instead of plain eyes closed', () => {
    show('OK', { eyes_closed: true, eyes_closed_prolonged: true });
    expect(screen.getByText(vi.faceSignal.eyes_closed_prolonged)).toBeInTheDocument();
    expect(screen.queryByText(vi.faceSignal.eyes_closed)).not.toBeInTheDocument();
  });

  it('lists no signal when face_signals is empty', () => {
    show('OK');
    expect(screen.getByText(vi.live.faceNoSignal)).toBeInTheDocument();
    for (const text of Object.values(vi.faceSignal)) {
      expect(screen.queryByText(text)).not.toBeInTheDocument();
    }
  });

  it.each<FaceStatus>(['NOT_VISIBLE', 'TOO_SMALL', 'LOW_CONFIDENCE'])(
    'face %s shows not enough face data and no signal',
    (status) => {
      // Tín hiệu cũ (nếu có) cũng không hiện khi mặt không quan sát được.
      show(status, { brow_down: true });
      expect(screen.getByText(vi.live.faceNoData)).toBeInTheDocument();
      expect(screen.getByText(vi.faceStatus[status])).toBeInTheDocument();
      expect(screen.queryByText(vi.faceSignal.brow_down)).not.toBeInTheDocument();
      expect(screen.queryByText(vi.live.faceNoSignal)).not.toBeInTheDocument();
      expect(screen.queryByText(vi.faceStatus.OK)).not.toBeInTheDocument();
    },
  );
});

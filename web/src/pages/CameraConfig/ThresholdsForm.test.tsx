import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi as vitest } from 'vitest';

import { fmt, vi } from '../../i18n/vi';
import { ThresholdsForm, type ThresholdsData } from './ThresholdsForm';
import { THRESHOLD_KEYS } from './thresholdKeys';

const DEFAULTS = {
  version: 1,
  pose: { num_poses: 2, min_keypoint_visibility: 0.5 },
  quality: { low_quality_to_no_observation_s: 2.0 },
  posture: { lying_enter_deg: 25, lying_exit_deg: 35, sitting_enter_deg: 55, sitting_exit_deg: 45 },
  location: { edge_distance_torso: 0.3, out_of_roi_margin_torso: 0.2 },
  min_duration_s: {
    RAISING: 0.5,
    SITTING: 2.0,
    AT_EDGE: 1.5,
    STANDING: 1.0,
    OUT_OF_BED: 1.0,
    LYING: 2.0,
    RETURN_TO_BED: 3.0,
  },
  activity: { low_threshold: 0.02, high_threshold: 0.15, window_s: 5 },
};

function merged(over: Record<string, Record<string, number>>) {
  const out = structuredClone(DEFAULTS) as Record<string, Record<string, number>>;
  for (const [k, v] of Object.entries(over)) out[k] = { ...out[k], ...v };
  return out;
}

function data(overrides: Record<string, Record<string, number>>): ThresholdsData {
  return { defaults: DEFAULTS, overrides, effective: merged(overrides), config_version: 3 };
}

const label = (path: string) => vi.cameraConfig.thresholds.labels[path];

function renderForm(d: ThresholdsData) {
  const onSave = vitest.fn();
  const onReset = vitest.fn();
  const utils = render(
    <MantineProvider>
      <ThresholdsForm data={d} onSave={onSave} onReset={onReset} />
    </MantineProvider>,
  );
  return { ...utils, onSave, onReset };
}

describe('ThresholdsForm', () => {
  it('lists every main threshold with a Vietnamese label', () => {
    renderForm(data({}));
    for (const path of THRESHOLD_KEYS) {
      expect(label(path)).toBeTruthy();
      expect(screen.getByLabelText(label(path))).toBeInTheDocument();
    }
  });

  it('shows effective value and the default beside it', () => {
    renderForm(data({ posture: { lying_enter_deg: 20 } }));
    expect(screen.getByLabelText(label('posture.lying_enter_deg'))).toHaveValue('20');
    expect(screen.getAllByText(fmt(vi.cameraConfig.thresholds.default, { value: 25 })).length).toBe(
      1,
    );
  });

  it('saves only values different from defaults, keeping other overrides', () => {
    const { onSave } = renderForm(
      data({ posture: { lying_enter_deg: 20 }, smoothing: { ema_alpha: 0.5 } }),
    );
    // Đưa lying_enter_deg về mặc định, đổi SITTING.
    fireEvent.change(screen.getByLabelText(label('posture.lying_enter_deg')), {
      target: { value: '25' },
    });
    fireEvent.change(screen.getByLabelText(label('min_duration_s.SITTING')), {
      target: { value: '3' },
    });
    fireEvent.click(screen.getByRole('button', { name: vi.cameraConfig.thresholds.save }));
    expect(onSave).toHaveBeenCalledWith({
      smoothing: { ema_alpha: 0.5 },
      min_duration_s: { SITTING: 3 },
    });
  });

  it('blocks save when a field is empty', () => {
    const { onSave } = renderForm(data({}));
    fireEvent.change(screen.getByLabelText(label('activity.low_threshold')), {
      target: { value: '' },
    });
    expect(screen.getByRole('button', { name: vi.cameraConfig.thresholds.save })).toBeDisabled();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('ThresholdsForm resets to defaults', async () => {
    const { onReset, rerender } = renderForm(data({ posture: { lying_enter_deg: 20 } }));
    fireEvent.click(screen.getByRole('button', { name: vi.cameraConfig.thresholds.reset }));
    // Hộp thoại xác nhận.
    expect(await screen.findByText(vi.cameraConfig.thresholds.resetConfirm)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: vi.common.confirm }));
    expect(onReset).toHaveBeenCalledTimes(1);
    // Server trả override rỗng → form hiện lại giá trị mặc định.
    rerender(
      <MantineProvider>
        <ThresholdsForm data={data({})} onSave={vitest.fn()} onReset={onReset} />
      </MantineProvider>,
    );
    await waitFor(() =>
      expect(screen.getByLabelText(label('posture.lying_enter_deg'))).toHaveValue('25'),
    );
  });
});

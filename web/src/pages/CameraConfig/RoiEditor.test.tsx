import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { describe, expect, it, vi as vitest } from 'vitest';

import { fmt, vi } from '../../i18n/vi';
import { RoiEditor } from './RoiEditor';

const W = 400;
const H = 200;

function setup(props: Partial<Parameters<typeof RoiEditor>[0]> = {}) {
  const onSave = vitest.fn();
  const ui: ReactElement = (
    <MantineProvider>
      <RoiEditor cameraId={1} token="t" online initial={null} onSave={onSave} {...props} />
    </MantineProvider>
  );
  render(ui);
  const canvas = screen.getByTestId('roi-canvas');
  // jsdom không có layout: khung đang hiển thị 400×200 px, góc trên trái (10, 20).
  canvas.getBoundingClientRect = () =>
    ({
      left: 10,
      top: 20,
      width: W,
      height: H,
      right: 10 + W,
      bottom: 20 + H,
      x: 10,
      y: 20,
    }) as DOMRect;
  return { canvas, onSave };
}

function clickAt(canvas: HTMLElement, px: number, py: number) {
  fireEvent.click(canvas, { clientX: 10 + px, clientY: 20 + py });
}

const saveButton = () => screen.getByRole('button', { name: vi.cameraConfig.roi.save });
const handle = (n: number) =>
  screen.getByRole('button', { name: fmt(vi.cameraConfig.roi.point, { n }) });

describe('RoiEditor', () => {
  it('shows the live MJPEG frame as background', () => {
    setup();
    const img = screen.getByRole('img', { name: vi.cameraConfig.roi.title });
    expect(img.getAttribute('src')).toMatch(/^\/api\/v1\/cameras\/1\/stream\.mjpeg\?/);
  });

  it('RoiEditor adds point on click with normalized coords', () => {
    const { canvas, onSave } = setup();
    clickAt(canvas, 100, 50); // (0.25, 0.25)
    clickAt(canvas, 300, 50); // (0.75, 0.25)
    clickAt(canvas, 300, 150); // (0.75, 0.75)
    expect(screen.getByText(fmt(vi.cameraConfig.roi.points, { n: 3 }))).toBeInTheDocument();
    expect(saveButton()).toBeEnabled();
    fireEvent.click(saveButton());
    expect(onSave).toHaveBeenCalledWith([
      [0.25, 0.25],
      [0.75, 0.25],
      [0.75, 0.75],
    ]);
  });

  it('RoiEditor disables save with fewer than 3 points', () => {
    const { canvas } = setup();
    expect(saveButton()).toBeDisabled();
    clickAt(canvas, 100, 50);
    clickAt(canvas, 300, 50);
    expect(saveButton()).toBeDisabled();
    expect(screen.getByText(vi.cameraConfig.roi.reasons.TOO_FEW_POINTS)).toBeInTheDocument();
  });

  it('RoiEditor disables save for a self-intersecting polygon', () => {
    const { canvas } = setup();
    clickAt(canvas, 40, 20);
    clickAt(canvas, 360, 180);
    clickAt(canvas, 360, 20);
    clickAt(canvas, 40, 180);
    expect(saveButton()).toBeDisabled();
    expect(screen.getByText(vi.cameraConfig.roi.reasons.SELF_INTERSECTION)).toBeInTheDocument();
  });

  it('RoiEditor drags and deletes points', () => {
    const { canvas, onSave } = setup({
      initial: [
        [0.1, 0.1],
        [0.9, 0.1],
        [0.9, 0.9],
        [0.1, 0.9],
      ],
    });
    // Kéo điểm 3 từ (0.9, 0.9) tới (0.5, 0.75).
    fireEvent.mouseDown(handle(3), { clientX: 10 + 360, clientY: 20 + 180 });
    fireEvent.mouseMove(canvas, { clientX: 10 + 200, clientY: 20 + 150 });
    fireEvent.mouseUp(canvas, { clientX: 10 + 200, clientY: 20 + 150 });
    // Click sau khi kéo không thêm điểm.
    clickAt(canvas, 200, 150);
    expect(screen.getByText(fmt(vi.cameraConfig.roi.points, { n: 4 }))).toBeInTheDocument();

    // Chọn điểm 1 rồi xóa.
    fireEvent.click(handle(1));
    fireEvent.click(screen.getByRole('button', { name: vi.cameraConfig.roi.deletePoint }));
    expect(screen.getByText(fmt(vi.cameraConfig.roi.points, { n: 3 }))).toBeInTheDocument();
    fireEvent.click(saveButton());
    expect(onSave).toHaveBeenCalledWith([
      [0.9, 0.1],
      [0.5, 0.75],
      [0.1, 0.9],
    ]);
  });

  it('clear removes all points', () => {
    setup({
      initial: [
        [0.1, 0.1],
        [0.9, 0.1],
        [0.5, 0.9],
      ],
    });
    fireEvent.click(screen.getByRole('button', { name: vi.cameraConfig.roi.clear }));
    expect(screen.getByText(fmt(vi.cameraConfig.roi.points, { n: 0 }))).toBeInTheDocument();
    expect(saveButton()).toBeDisabled();
  });

  it('offline camera: blank background, still editable', () => {
    const { canvas } = setup({
      online: false,
      initial: [
        [0.1, 0.1],
        [0.9, 0.1],
        [0.5, 0.9],
      ],
    });
    expect(screen.queryByRole('img', { name: vi.cameraConfig.roi.title })).toBeNull();
    expect(screen.getByText(vi.cameraStatus.OFFLINE)).toBeInTheDocument();
    clickAt(canvas, 200, 100);
    expect(screen.getByText(fmt(vi.cameraConfig.roi.points, { n: 4 }))).toBeInTheDocument();
  });
});

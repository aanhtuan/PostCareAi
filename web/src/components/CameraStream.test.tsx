import { MantineProvider } from '@mantine/core';
import { act, fireEvent, render, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { afterEach, describe, expect, it, vi as vitest } from 'vitest';

import { vi } from '../i18n/vi';
import { CameraStream } from './CameraStream';

function wrap(ui: ReactElement) {
  return <MantineProvider>{ui}</MantineProvider>;
}

afterEach(() => {
  vitest.useRealTimers();
});

describe('CameraStream', () => {
  it('shows the MJPEG stream with token in query', () => {
    render(wrap(<CameraStream cameraId={3} token="abc" online roi={null} alt="Giường A01" />));
    const img = screen.getByRole('img', { name: 'Giường A01' });
    const src = img.getAttribute('src') ?? '';
    expect(src.startsWith('/api/v1/cameras/3/stream.mjpeg?')).toBe(true);
    expect(new URL(src, 'http://x').searchParams.get('token')).toBe('abc');
  });

  it('hides the image and shows the offline block when not online', () => {
    render(
      wrap(<CameraStream cameraId={3} token="abc" online={false} roi={null} alt="Giường A01" />),
    );
    expect(screen.queryByRole('img', { name: 'Giường A01' })).toBeNull();
    expect(screen.getByText(vi.cameraStatus.OFFLINE)).toBeInTheDocument();
  });

  it('reopens the stream when the camera comes back online', () => {
    const { rerender } = render(
      wrap(<CameraStream cameraId={3} token="abc" online={false} roi={null} alt="Giường A01" />),
    );
    rerender(wrap(<CameraStream cameraId={3} token="abc" online roi={null} alt="Giường A01" />));
    expect(screen.getByRole('img', { name: 'Giường A01' })).toBeInTheDocument();
    expect(screen.queryByText(vi.cameraStatus.OFFLINE)).toBeNull();
  });

  it('image error → offline block, then retries with a new URL', () => {
    vitest.useFakeTimers();
    render(
      wrap(
        <CameraStream cameraId={3} token="abc" online roi={null} alt="Giường A01" retryMs={1000} />,
      ),
    );
    const first = screen.getByRole('img', { name: 'Giường A01' }).getAttribute('src');
    fireEvent.error(screen.getByRole('img', { name: 'Giường A01' }));
    expect(screen.queryByRole('img', { name: 'Giường A01' })).toBeNull();
    expect(screen.getByText(vi.cameraStatus.OFFLINE)).toBeInTheDocument();
    act(() => {
      vitest.advanceTimersByTime(1000);
    });
    const again = screen.getByRole('img', { name: 'Giường A01' }).getAttribute('src');
    expect(again).not.toBe(first);
  });
});

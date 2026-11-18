import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { vi } from '../../i18n/vi';
import { ImageQualityIndicator } from './ImageQualityIndicator';

describe('ImageQualityIndicator', () => {
  it('ImageQualityIndicator shows brightness and fps', () => {
    render(
      <MantineProvider>
        <ImageQualityIndicator
          runtime={{
            fps: 14.76,
            brightness: 118.4,
            dropped_frames: 0,
            source_status: 'ONLINE',
            updated_at: '2026-11-18T03:00:00Z',
          }}
        />
      </MantineProvider>,
    );
    expect(screen.getByText(vi.cameraConfig.imageQuality.brightness)).toBeInTheDocument();
    expect(screen.getByText(vi.cameraConfig.imageQuality.fps)).toBeInTheDocument();
    expect(screen.getByTestId('quality-brightness')).toHaveTextContent('118');
    expect(screen.getByTestId('quality-fps')).toHaveTextContent('14,8');
    expect(screen.queryByText(vi.cameraConfig.imageQuality.noData)).toBeNull();
  });

  it('ImageQualityIndicator shows no data', () => {
    render(
      <MantineProvider>
        <ImageQualityIndicator runtime={null} />
      </MantineProvider>,
    );
    expect(screen.getByText(vi.cameraConfig.imageQuality.noData)).toBeInTheDocument();
    expect(screen.queryByTestId('quality-fps')).toBeNull();
  });
});

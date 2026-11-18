import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { RoiOverlay } from './RoiOverlay';

describe('RoiOverlay', () => {
  it('RoiOverlay scales normalized points to image size', () => {
    const { container } = render(
      <RoiOverlay
        polygon={[
          [0.2, 0.25],
          [0.8, 0.25],
          [0.8, 0.85],
          [0.2, 0.85],
        ]}
        width={640}
        height={360}
      />,
    );
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute('viewBox')).toBe('0 0 640 360');
    const polygon = container.querySelector('polygon');
    expect(polygon?.getAttribute('points')).toBe('128,90 512,90 512,306 128,306');
  });

  it('RoiOverlay follows a new display size', () => {
    const roi: number[][] = [
      [0.5, 0.5],
      [1, 0.5],
      [1, 1],
    ];
    const { container, rerender } = render(<RoiOverlay polygon={roi} width={100} height={100} />);
    expect(container.querySelector('polygon')?.getAttribute('points')).toBe('50,50 100,50 100,100');
    rerender(<RoiOverlay polygon={roi} width={200} height={50} />);
    expect(container.querySelector('polygon')?.getAttribute('points')).toBe('100,25 200,25 200,50');
  });

  it('RoiOverlay renders nothing without polygon', () => {
    const { container } = render(<RoiOverlay polygon={null} width={640} height={360} />);
    expect(container.querySelector('svg')).toBeNull();
  });

  it('RoiOverlay renders nothing before the image has a size', () => {
    const { container } = render(
      <RoiOverlay
        polygon={[
          [0, 0],
          [1, 0],
          [1, 1],
        ]}
        width={0}
        height={0}
      />,
    );
    expect(container.querySelector('svg')).toBeNull();
  });
});

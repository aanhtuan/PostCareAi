import type { AlertCreatedOut } from '../api/types';

export function createAlertNotifier(_deps: {
  show: (n: unknown) => void;
  play: () => void;
}): (data: AlertCreatedOut) => void {
  void _deps;
  throw new Error('not implemented');
}

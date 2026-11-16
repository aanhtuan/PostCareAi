import { Badge } from '@mantine/core';

import type { AlertOutcome, AlertStatus, Priority } from '../api/types';
import { vi } from '../i18n/vi';

const PRIORITY_COLOR: Record<Priority, string> = {
  LOG: 'gray',
  INFO: 'blue',
  MEDIUM: 'orange',
  HIGH: 'red',
};

const STATUS_COLOR: Record<AlertStatus, string> = {
  PENDING: 'red',
  ACKNOWLEDGED: 'yellow',
  RESOLVED: 'green',
};

export function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <Badge color={PRIORITY_COLOR[priority]} variant={priority === 'HIGH' ? 'filled' : 'light'}>
      {vi.priority[priority]}
    </Badge>
  );
}

export function AlertStatusBadge({ status }: { status: AlertStatus }) {
  return (
    <Badge color={STATUS_COLOR[status]} variant="light">
      {vi.alertStatus[status]}
    </Badge>
  );
}

export function OutcomeText({ outcome }: { outcome: AlertOutcome | null | undefined }) {
  return <>{outcome ? vi.outcome[outcome] : vi.alerts.noOutcome}</>;
}

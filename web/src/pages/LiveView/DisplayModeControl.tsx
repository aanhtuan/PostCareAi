// Chế độ hiển thị của camera trên "Theo dõi trực tiếp" (F28 R10; PDF §9.1, §11).
// Mọi vai trò nhân viên thấy tên chế độ hiện tại; chỉ ADMIN và CHARGE_NURSE đổi được
// (api-conventions.md ma trận quyền). Khung hình được render trong worker, web chỉ hiển thị.
import { CheckIcon, Group, SegmentedControl, Stack, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';

import { useSaveDisplayMode } from '../../api/hooks';
import type { DisplayMode, UserRole } from '../../api/types';
import { useAuth } from '../../auth/useAuth';
import { vi } from '../../i18n/vi';
import { apiErrorMessage } from '../Management/errorMessage';

const EDITOR_ROLES: readonly UserRole[] = ['ADMIN', 'CHARGE_NURSE'];
const MODES: readonly DisplayMode[] = ['RAW', 'BLUR', 'SKELETON'];

export function DisplayModeControl({ cameraId, mode }: { cameraId: number; mode: DisplayMode }) {
  const { user } = useAuth();
  const save = useSaveDisplayMode(cameraId);
  const canEdit = user !== null && EDITOR_ROLES.includes(user.role);

  const change = (value: string) => {
    const next = value as DisplayMode;
    if (next === mode) return;
    save.mutate(next, {
      onSuccess: () => notifications.show({ color: 'green', message: vi.live.displayModeSaved }),
      onError: (err) =>
        notifications.show({
          color: 'red',
          message: apiErrorMessage(err) ?? vi.common.genericError,
        }),
    });
  };

  return (
    <Stack gap={4}>
      <Group gap="xs">
        <Text size="sm" c="dimmed">
          {vi.live.displayMode}:
        </Text>
        {!canEdit && (
          <Group gap={4}>
            <CheckIcon size={14} aria-hidden="true" />
            <Text size="sm" fw={600}>
              {vi.displayMode[mode]}
            </Text>
          </Group>
        )}
      </Group>
      {canEdit && (
        <SegmentedControl
          fullWidth
          aria-label={vi.live.changeDisplayMode}
          value={mode}
          onChange={change}
          disabled={save.isPending}
          data={MODES.map((m) => ({
            value: m,
            label: (
              <Group
                component="span"
                gap={4}
                justify="center"
                wrap="nowrap"
                style={{ whiteSpace: 'normal' }}
              >
                {m === mode && <CheckIcon size={14} style={{ flexShrink: 0 }} aria-hidden="true" />}
                <span>{vi.displayMode[m]}</span>
              </Group>
            ),
          }))}
        />
      )}
      {mode === 'RAW' && (
        <Text size="xs" c="orange">
          {vi.live.rawHint}
        </Text>
      )}
    </Stack>
  );
}

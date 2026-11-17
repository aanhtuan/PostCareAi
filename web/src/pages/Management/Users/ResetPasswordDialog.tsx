import { Button, Group, Modal, PasswordInput, Stack, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import type { UserOut } from '../../../api/types';
import { useResetPassword } from '../../../api/users';
import { vi } from '../../../i18n/vi';
import { showUserError } from './errors';
import { MIN_PASSWORD } from './UserForm';

function Body({ user, onClose }: { user: UserOut; onClose: () => void }) {
  const reset = useResetPassword();
  const [password, setPassword] = useState('');
  return (
    <Stack>
      <Text size="sm">
        {user.full_name} ({user.username})
      </Text>
      <Text size="sm" c="dimmed">
        {vi.users.resetPasswordHint}
      </Text>
      <PasswordInput
        label={vi.users.newPassword}
        description={vi.users.passwordHint}
        value={password}
        onChange={(e) => setPassword(e.currentTarget.value)}
        required
      />
      <Group justify="flex-end">
        <Button variant="default" onClick={onClose}>
          {vi.common.cancel}
        </Button>
        <Button
          disabled={password.length < MIN_PASSWORD}
          loading={reset.isPending}
          onClick={() =>
            reset.mutate(
              { id: user.id, new_password: password },
              {
                onSuccess: () => {
                  notifications.show({ color: 'teal', message: vi.users.passwordReset });
                  onClose();
                },
                onError: showUserError,
              },
            )
          }
        >
          {vi.users.save}
        </Button>
      </Group>
    </Stack>
  );
}

export function ResetPasswordDialog({
  user,
  onClose,
}: {
  user: UserOut | null;
  onClose: () => void;
}) {
  return (
    <Modal opened={user !== null} onClose={onClose} title={vi.users.resetPassword}>
      {user && <Body key={user.id} user={user} onClose={onClose} />}
    </Modal>
  );
}

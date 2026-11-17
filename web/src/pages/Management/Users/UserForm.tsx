import { Button, Group, Modal, PasswordInput, Select, Stack, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { USER_ROLES, type UserOut, type UserRole } from '../../../api/types';
import { useCreateUser, useUpdateUser } from '../../../api/users';
import { vi } from '../../../i18n/vi';
import { showUserError } from './errors';

const USERNAME_RE = /^[a-z0-9._-]{3,64}$/;
export const MIN_PASSWORD = 8;

const roleOptions = USER_ROLES.map((r) => ({ value: r, label: vi.role[r] }));

type Props = {
  opened: boolean;
  /** `null`: tạo mới; có giá trị: sửa họ tên và vai trò (không sửa tên đăng nhập). */
  user: UserOut | null;
  onClose: () => void;
};

function FormBody({ user, onClose }: Omit<Props, 'opened'>) {
  const create = useCreateUser();
  const update = useUpdateUser();
  const [username, setUsername] = useState(user?.username ?? '');
  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [role, setRole] = useState<UserRole | null>(user?.role ?? null);
  const [password, setPassword] = useState('');

  const normalized = username.trim().toLowerCase();
  const valid =
    fullName.trim() !== '' &&
    role !== null &&
    (user !== null || (USERNAME_RE.test(normalized) && password.length >= MIN_PASSWORD));

  const done = (message: string) => {
    notifications.show({ color: 'teal', message });
    onClose();
  };

  const submit = () => {
    if (!valid || role === null) return;
    if (user) {
      update.mutate(
        { id: user.id, body: { full_name: fullName.trim(), role } },
        { onSuccess: () => done(vi.users.updated), onError: showUserError },
      );
    } else {
      create.mutate(
        { username: normalized, full_name: fullName.trim(), role, password },
        { onSuccess: () => done(vi.users.created), onError: showUserError },
      );
    }
  };

  return (
    <Stack>
      <TextInput
        label={vi.users.username}
        description={user ? undefined : vi.users.usernameHint}
        value={username}
        disabled={user !== null}
        onChange={(e) => setUsername(e.currentTarget.value)}
        required
      />
      <TextInput
        label={vi.users.fullName}
        value={fullName}
        onChange={(e) => setFullName(e.currentTarget.value)}
        required
      />
      <Select
        label={vi.users.role}
        data={roleOptions}
        value={role}
        onChange={(v) => setRole(v as UserRole | null)}
        allowDeselect={false}
        required
      />
      {user === null && (
        <PasswordInput
          label={vi.users.password}
          description={vi.users.passwordHint}
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
          required
        />
      )}
      <Group justify="flex-end">
        <Button variant="default" onClick={onClose}>
          {vi.common.cancel}
        </Button>
        <Button disabled={!valid} loading={create.isPending || update.isPending} onClick={submit}>
          {vi.users.save}
        </Button>
      </Group>
    </Stack>
  );
}

export function UserForm({ opened, user, onClose }: Props) {
  return (
    <Modal opened={opened} onClose={onClose} title={user ? vi.users.editTitle : vi.users.add}>
      {/* key: đặt lại form mỗi lần mở cho người dùng khác */}
      {opened && <FormBody key={user?.id ?? 'new'} user={user} onClose={onClose} />}
    </Modal>
  );
}

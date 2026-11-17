// Quản lý người dùng (F35), chỉ ADMIN. Route bọc RequireRole trong App.tsx.
import {
  Badge,
  Button,
  Card,
  Group,
  Modal,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { USER_ROLES, type UserOut, type UserRole } from '../../../api/types';
import { useSetUserLocked, useUsers } from '../../../api/users';
import { useAuth } from '../../../auth/useAuth';
import { vi } from '../../../i18n/vi';
import { showUserError } from './errors';
import { ResetPasswordDialog } from './ResetPasswordDialog';
import { UserForm } from './UserForm';

const ALL = '__all__';
const roleFilterOptions = [
  { value: ALL, label: vi.users.allRoles },
  ...USER_ROLES.map((r) => ({ value: r, label: vi.role[r] })),
];

export function UsersPage() {
  const { user: me } = useAuth();
  const [role, setRole] = useState<string>(ALL);
  const [showLocked, setShowLocked] = useState(false);
  const users = useUsers({
    role: role === ALL ? undefined : (role as UserRole),
    include_inactive: showLocked || undefined,
  });
  const setLocked = useSetUserLocked();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<UserOut | null>(null);
  const [lockFor, setLockFor] = useState<UserOut | null>(null);
  const [resetFor, setResetFor] = useState<UserOut | null>(null);

  const toggle = (u: UserOut, locked: boolean, after?: () => void) =>
    setLocked.mutate(
      { id: u.id, locked },
      {
        onSuccess: () => {
          notifications.show({
            color: 'teal',
            message: locked ? vi.users.locked : vi.users.unlocked,
          });
          after?.();
        },
        onError: showUserError,
      },
    );

  const items = users.data?.items ?? [];

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{vi.users.title}</Title>
        <Button
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          {vi.users.add}
        </Button>
      </Group>
      <Group>
        <Select
          aria-label={vi.users.role}
          data={roleFilterOptions}
          value={role}
          onChange={(v) => setRole(v ?? ALL)}
          allowDeselect={false}
          w={200}
        />
        <Switch
          label={vi.users.showLocked}
          checked={showLocked}
          onChange={(e) => setShowLocked(e.currentTarget.checked)}
        />
      </Group>
      <Card withBorder>
        {users.isError && <Text c="red">{vi.common.loadError}</Text>}
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{vi.users.username}</Table.Th>
              <Table.Th>{vi.users.fullName}</Table.Th>
              <Table.Th>{vi.users.role}</Table.Th>
              <Table.Th>{vi.users.statusLabel}</Table.Th>
              <Table.Th>{vi.users.actions}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.length === 0 && !users.isLoading && (
              <Table.Tr>
                <Table.Td colSpan={5}>
                  <Text c="dimmed">{vi.users.empty}</Text>
                </Table.Td>
              </Table.Tr>
            )}
            {items.map((u) => (
              <Table.Tr key={u.id}>
                <Table.Td ff="monospace">{u.username}</Table.Td>
                <Table.Td>{u.full_name}</Table.Td>
                <Table.Td>{vi.role[u.role]}</Table.Td>
                <Table.Td>
                  <Badge color={u.is_active ? 'teal' : 'gray'} variant="light">
                    {u.is_active ? vi.users.status.active : vi.users.status.locked}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    <Button
                      size="xs"
                      variant="default"
                      onClick={() => {
                        setEditing(u);
                        setFormOpen(true);
                      }}
                    >
                      {vi.users.edit}
                    </Button>
                    <Button size="xs" variant="default" onClick={() => setResetFor(u)}>
                      {vi.users.resetPassword}
                    </Button>
                    {u.is_active ? (
                      <Button
                        size="xs"
                        color="red"
                        variant="light"
                        disabled={u.id === me?.id}
                        onClick={() => setLockFor(u)}
                      >
                        {vi.users.lock}
                      </Button>
                    ) : (
                      <Button size="xs" variant="light" onClick={() => toggle(u, false)}>
                        {vi.users.unlock}
                      </Button>
                    )}
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>

      <UserForm opened={formOpen} user={editing} onClose={() => setFormOpen(false)} />
      <ResetPasswordDialog user={resetFor} onClose={() => setResetFor(null)} />
      <Modal opened={lockFor !== null} onClose={() => setLockFor(null)} title={vi.users.lock}>
        <Stack>
          <Text>{vi.users.confirmLock}</Text>
          {lockFor && (
            <Text size="sm" c="dimmed">
              {lockFor.full_name} ({lockFor.username})
            </Text>
          )}
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setLockFor(null)}>
              {vi.common.cancel}
            </Button>
            <Button
              color="red"
              loading={setLocked.isPending}
              onClick={() => lockFor && toggle(lockFor, true, () => setLockFor(null))}
            >
              {vi.common.confirm}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}

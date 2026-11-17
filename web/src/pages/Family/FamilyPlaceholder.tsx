// Trang của vai trò người nhà trước khi có F36 (F35 R2). Không mở WebSocket, không gọi API nhân viên.
import { Button, Center, Paper, Stack, Text, Title } from '@mantine/core';

import { useAuth } from '../../auth/useAuth';
import { vi } from '../../i18n/vi';

export function FamilyPlaceholder() {
  const { user, logout } = useAuth();
  return (
    <Center mih="100vh" bg="gray.0">
      <Paper withBorder shadow="sm" p="xl" w={420}>
        <Stack>
          <Title order={3} c="teal.8">
            {vi.app.name}
          </Title>
          {user && (
            <Text size="sm">
              <b>{user.full_name}</b> · {vi.role[user.role]}
            </Text>
          )}
          <Title order={4}>{vi.family.noAccess}</Title>
          <Text c="dimmed">{vi.family.noAccessHint}</Text>
          <Button variant="default" onClick={logout}>
            {vi.auth.logout}
          </Button>
        </Stack>
      </Paper>
    </Center>
  );
}

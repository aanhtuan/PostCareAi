import {
  Alert,
  Button,
  Center,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState, type FormEvent } from 'react';
import { Navigate } from 'react-router';

import { ApiError } from '../../api/client';
import { useAuth } from '../../auth/useAuth';
import { vi } from '../../i18n/vi';

export function LoginPage() {
  const { user, login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? vi.auth.invalid
          : err instanceof ApiError
            ? err.message
            : vi.common.genericError,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Center mih="100vh" bg="gray.0">
      <Paper withBorder shadow="sm" p="xl" w={380}>
        <form onSubmit={submit}>
          <Stack>
            <div>
              <Title order={2} c="teal.8">
                {vi.app.name}
              </Title>
              <Text c="dimmed" size="sm">
                {vi.app.tagline}
              </Text>
            </div>
            <Title order={4}>{vi.auth.title}</Title>
            {error && <Alert color="red">{error}</Alert>}
            <TextInput
              label={vi.auth.username}
              value={username}
              onChange={(e) => setUsername(e.currentTarget.value)}
              autoComplete="username"
              required
            />
            <PasswordInput
              label={vi.auth.password}
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
              autoComplete="current-password"
              required
            />
            <Button type="submit" loading={busy}>
              {vi.auth.submit}
            </Button>
          </Stack>
        </form>
      </Paper>
    </Center>
  );
}

import { AppShell, Badge, Burger, Button, Group, NavLink, Stack, Text } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { useContext } from 'react';
import { Link, Outlet, useLocation } from 'react-router';

import type { UserRole } from '../api/types';
import { useAuth } from '../auth/useAuth';
import { vi } from '../i18n/vi';
import { RealtimeContext } from '../realtime/RealtimeProvider';

type NavItem = { to: string; label: string; roles?: readonly UserRole[] };

const NAV: NavItem[] = [
  { to: '/', label: vi.nav.overview },
  { to: '/live', label: vi.nav.live },
  { to: '/alerts', label: vi.nav.alerts },
  { to: '/timeline', label: vi.nav.timeline },
  { to: '/handover', label: vi.nav.handover },
  { to: '/management', label: vi.nav.management },
  { to: '/management/users', label: vi.users.title, roles: ['ADMIN'] }, // F35
];

function matches(pathname: string, to: string): boolean {
  if (to === '/') return pathname === '/';
  if (to === '/live') return pathname === '/live' || pathname.endsWith('/live');
  return pathname === to || pathname.startsWith(`${to}/`);
}

/** Chỉ mục khớp dài nhất được tô (ví dụ `/management/users` không tô cả `/management`). */
function isActive(pathname: string, to: string, items: NavItem[]): boolean {
  if (!matches(pathname, to)) return false;
  return !items.some((n) => n.to.length > to.length && matches(pathname, n.to));
}

function RealtimeStatus() {
  const status = useContext(RealtimeContext);
  if (status === 'open') {
    return (
      <Badge color="green" variant="dot">
        {vi.realtime.connected}
      </Badge>
    );
  }
  return (
    <Badge color="orange" variant="light">
      {vi.realtime.reconnecting}
    </Badge>
  );
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const [opened, { toggle, close }] = useDisclosure();
  const nav = NAV.filter((n) => !n.roles || (user !== null && n.roles.includes(user.role)));

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 220, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header className="no-print">
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Text fw={800} c="teal.8">
              {vi.app.name}
            </Text>
            <Text size="sm" c="dimmed" visibleFrom="md">
              {vi.app.tagline}
            </Text>
          </Group>
          <Group gap="sm" wrap="nowrap">
            <RealtimeStatus />
            {user && (
              <Text size="sm">
                <b>{user.full_name}</b> · {vi.role[user.role]}
              </Text>
            )}
            <Button size="xs" variant="default" onClick={logout}>
              {vi.auth.logout}
            </Button>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs" className="no-print">
        <Stack gap={2} justify="space-between" h="100%">
          <div>
            {nav.map((n) => (
              <NavLink
                key={n.to}
                component={Link}
                to={n.to}
                label={n.label}
                active={isActive(pathname, n.to, nav)}
                onClick={close}
              />
            ))}
          </div>
          <Text size="xs" c="dimmed" p="xs">
            {vi.app.prototype}. {vi.app.disclaimer}
          </Text>
        </Stack>
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}

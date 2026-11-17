// Hook quản lý người dùng (F35), chỉ ADMIN. Tách khỏi hooks.ts để dễ gộp với F03.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from './client';
import type { Page, UserCreate, UserOut, UserRole, UserUpdate } from './types';

export type UserFilter = { role?: UserRole; include_inactive?: boolean };

export const usersKey = ['users'] as const;

export function useUsers(filter: UserFilter) {
  return useQuery({
    queryKey: [...usersKey, filter],
    queryFn: () => api<Page<UserOut>>('/users', { query: { ...filter, limit: 200 } }),
  });
}

function useInvalidateUsers() {
  const qc = useQueryClient();
  return () => void qc.invalidateQueries({ queryKey: usersKey });
}

export function useCreateUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: (body: UserCreate) => api<UserOut>('/users', { method: 'POST', body }),
    onSettled: invalidate,
  });
}

export function useUpdateUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: UserUpdate }) =>
      api<UserOut>(`/users/${id}`, { method: 'PATCH', body }),
    onSettled: invalidate,
  });
}

export function useSetUserLocked() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: ({ id, locked }: { id: number; locked: boolean }) =>
      api<UserOut>(`/users/${id}/${locked ? 'lock' : 'unlock'}`, { method: 'POST' }),
    onSettled: invalidate,
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: ({ id, new_password }: { id: number; new_password: string }) =>
      api<null>(`/users/${id}/reset-password`, { method: 'POST', body: { new_password } }),
  });
}

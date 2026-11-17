// Route guard phía web theo vai trò (F02 R12). Backend vẫn là nơi kiểm tra quyền chính.
import type { ReactNode } from 'react';
import { Navigate } from 'react-router';

import type { UserRole } from '../api/types';
import { useAuth } from './useAuth';

type Props = {
  roles: readonly UserRole[];
  children: ReactNode;
  /** Không có quyền: hiện `fallback` (ví dụ ẩn nút) thay vì chuyển về trang Tổng quan. */
  fallback?: ReactNode;
};

/** Chỉ hiện `children` khi người dùng có một trong `roles`. Chưa đăng nhập → trang đăng nhập. */
export function RequireRole({ roles, children, fallback }: Props) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) {
    return fallback !== undefined ? <>{fallback}</> : <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

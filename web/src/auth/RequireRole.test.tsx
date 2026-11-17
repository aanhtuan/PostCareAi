import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';

import type { UserOut } from '../api/types';
import { renderWithProviders } from '../test/render';
import { RequireRole } from './RequireRole';

const admin: UserOut = {
  id: 4,
  username: 'admin',
  full_name: 'Phạm Thu Hà',
  role: 'ADMIN',
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
};
const doctor: UserOut = {
  id: 3,
  username: 'doctor',
  full_name: 'Lê Quốc Bảo',
  role: 'DOCTOR',
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
};

function routes() {
  return (
    <Routes>
      <Route path="/" element={<p>home</p>} />
      <Route
        path="/admin"
        element={
          <RequireRole roles={['ADMIN']}>
            <p>admin-screen</p>
          </RequireRole>
        }
      />
    </Routes>
  );
}

describe('RequireRole', () => {
  it('shows the page for an allowed role', () => {
    renderWithProviders(routes(), admin, '/admin');
    expect(screen.getByText('admin-screen')).toBeInTheDocument();
  });

  it('redirects a role without permission to the overview', () => {
    renderWithProviders(routes(), doctor, '/admin');
    expect(screen.queryByText('admin-screen')).not.toBeInTheDocument();
    expect(screen.getByText('home')).toBeInTheDocument();
  });

  it('renders the fallback instead of redirecting when given', () => {
    renderWithProviders(
      <RequireRole roles={['NURSE', 'CHARGE_NURSE', 'ADMIN']} fallback={null}>
        <button>write</button>
      </RequireRole>,
      doctor,
    );
    expect(screen.queryByRole('button', { name: 'write' })).not.toBeInTheDocument();
  });
});

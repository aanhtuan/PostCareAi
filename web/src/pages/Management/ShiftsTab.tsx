// Mục "Ca trực" trong Quản lý (F37 R13): tên, giờ bắt đầu, giờ kết thúc (ghi "qua nửa đêm"
// nếu vắt ngày), trạng thái; ADMIN thêm/sửa/xóa mềm/khôi phục. Chồng giờ → 409, hiện `message`.
import { Table, Text } from '@mantine/core';
import { useState } from 'react';

import { useShifts } from '../../api/hooks';
import type { ShiftOut } from '../../api/types';
import { fmt, vi } from '../../i18n/vi';
import { isOvernight } from '../../utils/shift';
import { shortClock } from '../../utils/time';
import { useRestore } from './catalogActions';
import {
  ConfirmDeleteDialog,
  RowActions,
  Section,
  UsageBadge,
  type DeleteTarget,
} from './CatalogParts';
import { ShiftForm } from './ShiftForm';

type Props = { isAdmin: boolean; showDeleted: boolean };

export function ShiftsTab({ isAdmin, showDeleted }: Props) {
  const shifts = useShifts(showDeleted);
  const restore = useRestore();
  const [form, setForm] = useState<{ item: ShiftOut | null } | null>(null);
  const [toDelete, setToDelete] = useState<DeleteTarget | null>(null);

  return (
    <Section title={vi.shift.title} canAdd={isAdmin} onAdd={() => setForm({ item: null })}>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{vi.shift.name}</Table.Th>
            <Table.Th>{vi.shift.start}</Table.Th>
            <Table.Th>{vi.shift.end}</Table.Th>
            <Table.Th>{vi.catalog.usage}</Table.Th>
            {isAdmin && <Table.Th>{vi.management.actions}</Table.Th>}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {(shifts.data ?? []).map((s) => {
            const name = fmt(vi.shift.item, { name: s.name });
            return (
              <Table.Tr key={s.id}>
                <Table.Td fw={600}>{s.name}</Table.Td>
                <Table.Td>{shortClock(s.start_time)}</Table.Td>
                <Table.Td>
                  {shortClock(s.end_time)}
                  {isOvernight(s) && (
                    <Text span c="dimmed" size="sm">
                      {` (${vi.shift.overnight})`}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <UsageBadge active={s.is_active} />
                </Table.Td>
                {isAdmin && (
                  <Table.Td>
                    <RowActions
                      active={s.is_active}
                      onEdit={() => setForm({ item: s })}
                      onDelete={() => setToDelete({ resource: 'shifts', id: s.id, name })}
                      onRestore={() => restore('shifts', s.id, name)}
                    />
                  </Table.Td>
                )}
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
      {form && (
        <ShiftForm key={form.item?.id ?? 'new'} shift={form.item} onClose={() => setForm(null)} />
      )}
      <ConfirmDeleteDialog target={toDelete} onClose={() => setToDelete(null)} />
    </Section>
  );
}

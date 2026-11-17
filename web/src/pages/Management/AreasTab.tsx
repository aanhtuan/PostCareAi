// Mục "Khu vực" trong Quản lý (F37 R13): mã, tên, số giường, trạng thái; ADMIN thêm/sửa/xóa
// mềm/khôi phục (QA#36). Xóa khu vực còn giường đang dùng → API trả 409, hiện `message`.
import { Table } from '@mantine/core';
import { useState } from 'react';

import { useAreas } from '../../api/hooks';
import type { AreaOut } from '../../api/types';
import { fmt, vi } from '../../i18n/vi';
import { AreaForm } from './AreaForm';
import { useRestore } from './catalogActions';
import {
  ConfirmDeleteDialog,
  RowActions,
  Section,
  UsageBadge,
  type DeleteTarget,
} from './CatalogParts';

type Props = { isAdmin: boolean; showDeleted: boolean };

export function AreasTab({ isAdmin, showDeleted }: Props) {
  const areas = useAreas(showDeleted);
  const restore = useRestore();
  const [form, setForm] = useState<{ item: AreaOut | null } | null>(null);
  const [toDelete, setToDelete] = useState<DeleteTarget | null>(null);

  return (
    <Section title={vi.area.title} canAdd={isAdmin} onAdd={() => setForm({ item: null })}>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{vi.area.code}</Table.Th>
            <Table.Th>{vi.area.name}</Table.Th>
            <Table.Th>{vi.area.bedCount}</Table.Th>
            <Table.Th>{vi.catalog.usage}</Table.Th>
            {isAdmin && <Table.Th>{vi.management.actions}</Table.Th>}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {(areas.data ?? []).map((a) => {
            const name = fmt(vi.area.item, { name: a.name });
            return (
              <Table.Tr key={a.id}>
                <Table.Td fw={600}>{a.code}</Table.Td>
                <Table.Td>{a.name}</Table.Td>
                <Table.Td>{a.bed_count}</Table.Td>
                <Table.Td>
                  <UsageBadge active={a.is_active} />
                </Table.Td>
                {isAdmin && (
                  <Table.Td>
                    <RowActions
                      active={a.is_active}
                      onEdit={() => setForm({ item: a })}
                      onDelete={() => setToDelete({ resource: 'areas', id: a.id, name })}
                      onRestore={() => restore('areas', a.id, name)}
                    />
                  </Table.Td>
                )}
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
      {form && (
        <AreaForm key={form.item?.id ?? 'new'} area={form.item} onClose={() => setForm(null)} />
      )}
      <ConfirmDeleteDialog target={toDelete} onClose={() => setToDelete(null)} />
    </Section>
  );
}

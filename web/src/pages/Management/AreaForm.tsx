// Form thêm/sửa khu vực: mã, tên (F37 R1, R4).
import { TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { useSaveCatalogItem } from '../../api/hooks';
import type { AreaCreate, AreaOut } from '../../api/types';
import { fmt, vi } from '../../i18n/vi';
import { CatalogFormModal } from './CatalogFormModal';

type Props = { area: AreaOut | null; onClose: () => void };

export function AreaForm({ area, onClose }: Props) {
  const save = useSaveCatalogItem<AreaCreate>('areas');
  const [code, setCode] = useState(area?.code ?? '');
  const [name, setName] = useState(area?.name ?? '');
  const [touched, setTouched] = useState(false);

  const submit = () => {
    setTouched(true);
    if (!code.trim() || !name.trim()) return;
    save.mutate(
      { id: area?.id, body: { code: code.trim(), name: name.trim() } },
      {
        onSuccess: () => {
          notifications.show({ color: 'teal', message: vi.catalog.savedDone });
          onClose();
        },
      },
    );
  };

  return (
    <CatalogFormModal
      opened
      title={area ? fmt(vi.area.editTitle, { code: area.code }) : vi.area.add}
      onClose={onClose}
      onSubmit={submit}
      saving={save.isPending}
      error={save.error}
    >
      <TextInput
        label={vi.area.code}
        required
        value={code}
        onChange={(e) => setCode(e.currentTarget.value)}
        error={touched && !code.trim() ? vi.catalog.required : undefined}
        data-autofocus
      />
      <TextInput
        label={vi.area.name}
        required
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        error={touched && !name.trim() ? vi.catalog.required : undefined}
      />
    </CatalogFormModal>
  );
}

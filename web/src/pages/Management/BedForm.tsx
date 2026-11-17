// Form thêm/sửa giường: mã giường, khu vực (F03 R3; QA#15).
import { TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { useSaveCatalogItem } from '../../api/hooks';
import type { BedCreate, BedOut } from '../../api/types';
import { fmt, vi } from '../../i18n/vi';
import { CatalogFormModal } from './CatalogFormModal';

type Props = { bed: BedOut | null; onClose: () => void };

/** `bed = null`: thêm mới. Gắn `key` theo mục để form khởi tạo lại giá trị. */
export function BedForm({ bed, onClose }: Props) {
  const save = useSaveCatalogItem<BedCreate>('beds');
  const [code, setCode] = useState(bed?.code ?? '');
  const [area, setArea] = useState(bed?.area ?? '');
  const [touched, setTouched] = useState(false);

  const submit = () => {
    setTouched(true);
    if (!code.trim() || !area.trim()) return;
    save.mutate(
      { id: bed?.id, body: { code: code.trim(), area: area.trim() } },
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
      title={bed ? fmt(vi.catalog.editBed, { code: bed.code }) : vi.catalog.addBed}
      onClose={onClose}
      onSubmit={submit}
      saving={save.isPending}
      error={save.error}
    >
      <TextInput
        label={vi.bed.code}
        required
        value={code}
        onChange={(e) => setCode(e.currentTarget.value)}
        error={touched && !code.trim() ? vi.catalog.required : undefined}
        data-autofocus
      />
      <TextInput
        label={vi.bed.area}
        required
        value={area}
        onChange={(e) => setArea(e.currentTarget.value)}
        error={touched && !area.trim() ? vi.catalog.required : undefined}
      />
    </CatalogFormModal>
  );
}

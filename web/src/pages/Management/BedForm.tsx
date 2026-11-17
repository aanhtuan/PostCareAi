// Form thêm/sửa giường: mã giường, khu vực chọn từ danh sách khu vực đang dùng
// (F03 R3; F37 R3, R13; QA#15).
import { Select, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { useAreas, useSaveCatalogItem } from '../../api/hooks';
import type { BedCreate, BedOut } from '../../api/types';
import { fmt, vi } from '../../i18n/vi';
import { CatalogFormModal } from './CatalogFormModal';

type Props = { bed: BedOut | null; onClose: () => void };

/** `bed = null`: thêm mới. Gắn `key` theo mục để form khởi tạo lại giá trị. */
export function BedForm({ bed, onClose }: Props) {
  const save = useSaveCatalogItem<BedCreate>('beds');
  const areas = useAreas();
  const [code, setCode] = useState(bed?.code ?? '');
  const [areaId, setAreaId] = useState<string | null>(bed ? String(bed.area.id) : null);
  const [touched, setTouched] = useState(false);

  const options = (areas.data ?? []).map((a) => ({ value: String(a.id), label: a.name }));
  if (bed && !options.some((o) => o.value === String(bed.area.id))) {
    // Khu vực hiện tại đã bị xóa: vẫn hiện để không đổi ngầm.
    options.push({
      value: String(bed.area.id),
      label: fmt(vi.area.deletedLabel, { name: bed.area.name }),
    });
  }

  const submit = () => {
    setTouched(true);
    if (!code.trim() || !areaId) return;
    save.mutate(
      { id: bed?.id, body: { code: code.trim(), area_id: Number(areaId) } },
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
      <Select
        label={vi.bed.area}
        placeholder={vi.area.choose}
        required
        data={options}
        value={areaId}
        onChange={setAreaId}
        allowDeselect={false}
        error={touched && !areaId ? vi.catalog.required : undefined}
      />
    </CatalogFormModal>
  );
}

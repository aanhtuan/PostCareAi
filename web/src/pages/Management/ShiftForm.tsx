// Form thêm/sửa ca trực: tên, giờ bắt đầu, giờ kết thúc dạng HH:mm (F37 R7, R8).
// Sửa ca có sẵn: cảnh báo bàn giao các ngày trước được tổng hợp lại theo giờ mới (R9).
import { Alert, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { useSaveCatalogItem } from '../../api/hooks';
import type { ShiftCreate, ShiftOut } from '../../api/types';
import { fmt, vi } from '../../i18n/vi';
import { shortClock } from '../../utils/time';
import { CatalogFormModal } from './CatalogFormModal';

type Props = { shift: ShiftOut | null; onClose: () => void };

export function ShiftForm({ shift, onClose }: Props) {
  const save = useSaveCatalogItem<ShiftCreate>('shifts');
  const [name, setName] = useState(shift?.name ?? '');
  const [start, setStart] = useState(shift ? shortClock(shift.start_time) : '');
  const [end, setEnd] = useState(shift ? shortClock(shift.end_time) : '');
  const [touched, setTouched] = useState(false);
  const same = start !== '' && start === end;

  const submit = () => {
    setTouched(true);
    if (!name.trim() || !start || !end || same) return;
    save.mutate(
      { id: shift?.id, body: { name: name.trim(), start_time: start, end_time: end } },
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
      title={shift ? fmt(vi.shift.editTitle, { name: shift.name }) : vi.shift.add}
      onClose={onClose}
      onSubmit={submit}
      saving={save.isPending}
      error={save.error}
    >
      {shift && (
        <Alert color="yellow" variant="light">
          {vi.shift.editWarning}
        </Alert>
      )}
      <TextInput
        label={vi.shift.name}
        required
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        error={touched && !name.trim() ? vi.catalog.required : undefined}
        data-autofocus
      />
      <TextInput
        type="time"
        label={vi.shift.start}
        required
        value={start}
        onChange={(e) => setStart(e.currentTarget.value)}
        error={touched && !start ? vi.catalog.required : undefined}
      />
      <TextInput
        type="time"
        label={vi.shift.end}
        description={vi.shift.timeHint}
        required
        value={end}
        onChange={(e) => setEnd(e.currentTarget.value)}
        error={
          touched && !end ? vi.catalog.required : touched && same ? vi.shift.sameTime : undefined
        }
      />
    </CatalogFormModal>
  );
}

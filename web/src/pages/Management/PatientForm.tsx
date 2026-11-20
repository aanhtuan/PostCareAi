// Form thêm/sửa bệnh nhân: chỉ mã thử nghiệm và ghi chú, không có họ tên hay ảnh (F03 R4).
import { Textarea, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { useSaveCatalogItem } from '../../api/hooks';
import type { PatientCreate, PatientOut } from '../../api/types';
import { fmt, vi } from '../../i18n/vi';
import { CatalogFormModal } from './CatalogFormModal';

type Props = { patient: PatientOut | null; onClose: () => void };

export function PatientForm({ patient, onClose }: Props) {
  const save = useSaveCatalogItem<PatientCreate>('patients');
  const [code, setCode] = useState(patient?.code ?? '');
  const [note, setNote] = useState(patient?.note ?? '');
  const [touched, setTouched] = useState(false);

  const submit = () => {
    setTouched(true);
    if (!code.trim()) return;
    save.mutate(
      { id: patient?.id, body: { code: code.trim(), note: note.trim() || null } },
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
      title={patient ? fmt(vi.catalog.editPatient, { code: patient.code }) : vi.catalog.addPatient}
      onClose={onClose}
      onSubmit={submit}
      saving={save.isPending}
      error={save.error}
    >
      <TextInput
        label={vi.management.patientCode}
        required
        value={code}
        onChange={(e) => setCode(e.currentTarget.value)}
        error={touched && !code.trim() ? vi.catalog.required : undefined}
        data-autofocus
      />
      <Textarea
        label={vi.management.patientNote}
        value={note}
        onChange={(e) => setNote(e.currentTarget.value)}
        autosize
        minRows={2}
      />
    </CatalogFormModal>
  );
}

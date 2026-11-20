// Form thêm/sửa camera: tên, loại nguồn, địa chỉ nguồn, giường (F03 R5, R7).
import { Select, Text, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { useBeds, useSaveCatalogItem } from '../../api/hooks';
import {
  SOURCE_TYPES,
  OBSERVATION_PROFILES,
  type CameraCreate,
  type CameraOut,
  type CameraSourceType,
  type ObservationProfile,
} from '../../api/types';
import { fmt, vi } from '../../i18n/vi';
import { CatalogFormModal } from './CatalogFormModal';

type Props = {
  camera: CameraOut | null;
  onClose: () => void;
  connect?: { bedId: number; bedCode: string; onSaved: (camera: CameraOut) => void };
};

const NO_BED = '';

export function CameraForm({ camera, onClose, connect }: Props) {
  const save = useSaveCatalogItem<CameraCreate, CameraOut>('cameras');
  const beds = useBeds();
  const [name, setName] = useState(
    camera?.name ?? (connect ? fmt(vi.live.cameraName, { code: connect.bedCode }) : ''),
  );
  const [sourceType, setSourceType] = useState<CameraSourceType>(camera?.source_type ?? 'WEBCAM');
  const [source, setSource] = useState(camera?.source ?? '');
  const [bedId, setBedId] = useState<string>(camera?.bed_id ? String(camera.bed_id) : NO_BED);
  const [observationProfile, setObservationProfile] = useState<ObservationProfile>(
    camera?.observation_profile ?? 'BED_MONITORING',
  );
  const [touched, setTouched] = useState(false);

  // Giường đang dùng, chưa có camera khác (QA#13); giường hiện tại của camera vẫn chọn được.
  const bedOptions = [
    { value: NO_BED, label: vi.catalog.noBed },
    ...(beds.data ?? [])
      .filter((b) => !b.camera || b.camera.id === camera?.id)
      .map((b) => ({ value: String(b.id), label: b.code })),
  ];

  const submit = () => {
    setTouched(true);
    if (!name.trim() || !source.trim()) return;
    const body: CameraCreate = {
      name: name.trim(),
      source_type: sourceType,
      source: source.trim(),
      bed_id: connect?.bedId ?? (bedId === NO_BED ? null : Number(bedId)),
      observation_profile: observationProfile,
    };
    save.mutate(
      { id: camera?.id, body },
      {
        onSuccess: (saved) => {
          if (connect) connect.onSaved(saved);
          else notifications.show({ color: 'teal', message: vi.catalog.savedDone });
          onClose();
        },
      },
    );
  };

  return (
    <CatalogFormModal
      opened
      title={
        connect
          ? fmt(vi.live.connectTitle, { code: connect.bedCode })
          : camera
            ? fmt(vi.catalog.editCamera, { name: camera.name })
            : vi.catalog.addCamera
      }
      onClose={onClose}
      onSubmit={submit}
      saving={save.isPending}
      error={save.error}
      submitLabel={connect ? vi.live.saveAndConnect : undefined}
    >
      <TextInput
        label={vi.camera.name}
        required
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        error={touched && !name.trim() ? vi.catalog.required : undefined}
        data-autofocus
      />
      <Select
        label={vi.camera.observationProfile}
        description={vi.camera.observationProfileHint}
        required
        allowDeselect={false}
        data={OBSERVATION_PROFILES.map((profile) => ({
          value: profile,
          label: vi.observationProfile[profile],
        }))}
        value={observationProfile}
        onChange={(value) => value && setObservationProfile(value as ObservationProfile)}
      />
      <Text size="xs" c="dimmed">
        {vi.observationProfileDescription[observationProfile]}
      </Text>
      <Select
        label={vi.camera.sourceType}
        required
        allowDeselect={false}
        data={SOURCE_TYPES.map((t) => ({ value: t, label: vi.sourceType[t] }))}
        value={sourceType}
        onChange={(v) => v && setSourceType(v as CameraSourceType)}
      />
      <TextInput
        label={vi.camera.source}
        description={vi.catalog.sourceHint[sourceType]}
        required
        value={source}
        onChange={(e) => setSource(e.currentTarget.value)}
        error={touched && !source.trim() ? vi.catalog.required : undefined}
      />
      {!connect && (
        <Select
          label={vi.common.bed}
          allowDeselect={false}
          data={bedOptions}
          value={bedId}
          onChange={(v) => setBedId(v ?? NO_BED)}
        />
      )}
    </CatalogFormModal>
  );
}

// Form ngưỡng chính của camera (F08 R5, R9; HS §5.5; QA#22). Hiện giá trị đang áp dụng và giá trị
// mặc định bên cạnh. Lưu = thay toàn bộ override: khóa trên form bằng mặc định thì bỏ khỏi override,
// override của khóa không có trên form được giữ nguyên. "Khôi phục mặc định" gửi `{}` sau khi xác nhận.
import { Button, Group, Modal, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core';
import { useState } from 'react';

import { fmt, vi } from '../../i18n/vi';
import { getPath, setPath, THRESHOLD_GROUPS, THRESHOLD_KEYS } from './thresholdKeys';

export type ThresholdsData = {
  defaults: Record<string, unknown>;
  overrides: Record<string, unknown>;
  effective: Record<string, unknown>;
  config_version: number;
};

type Props = {
  data: ThresholdsData;
  saving?: boolean;
  onSave: (overrides: Record<string, unknown>) => void;
  onReset: () => void;
};

const t = vi.cameraConfig.thresholds;

function toText(v: unknown): string {
  return typeof v === 'number' ? String(v) : '';
}

function initialValues(data: ThresholdsData): Record<string, string> {
  return Object.fromEntries(THRESHOLD_KEYS.map((k) => [k, toText(getPath(data.effective, k))]));
}

function parse(text: string): number | null {
  const v = Number(text.trim().replace(',', '.'));
  return text.trim() !== '' && Number.isFinite(v) && v >= 0 ? v : null;
}

export function ThresholdsForm(props: Props) {
  // Dữ liệu server đổi (lưu xong, khôi phục mặc định) → dựng lại form từ giá trị mới.
  const key = JSON.stringify([props.data.config_version, props.data.overrides]);
  return <ThresholdsFormInner key={key} {...props} />;
}

function ThresholdsFormInner({ data, saving = false, onSave, onReset }: Props) {
  const [values, setValues] = useState(() => initialValues(data));
  const [confirmReset, setConfirmReset] = useState(false);
  const invalid = THRESHOLD_KEYS.filter((k) => parse(values[k]) === null);

  function submit() {
    let overrides: Record<string, unknown> = structuredClone(data.overrides);
    for (const k of THRESHOLD_KEYS) {
      const v = parse(values[k]);
      overrides = setPath(overrides, k, v === getPath(data.defaults, k) ? undefined : v);
    }
    onSave(overrides);
  }

  return (
    <Stack>
      <Title order={4}>{t.title}</Title>
      {THRESHOLD_GROUPS.map(({ group, keys }) => (
        <Stack key={group} gap="xs">
          <Text fw={600}>{t.groups[group]}</Text>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            {keys.map((k) => (
              <TextInput
                key={k}
                label={t.labels[k]}
                inputMode="decimal"
                value={values[k]}
                onChange={(e) => {
                  const text = e.currentTarget.value;
                  setValues((prev) => ({ ...prev, [k]: text }));
                }}
                error={parse(values[k]) === null ? t.required : undefined}
                description={fmt(t.default, { value: toText(getPath(data.defaults, k)) })}
              />
            ))}
          </SimpleGrid>
        </Stack>
      ))}
      <Group justify="flex-end">
        <Button variant="default" color="red" onClick={() => setConfirmReset(true)}>
          {t.reset}
        </Button>
        <Button onClick={submit} disabled={invalid.length > 0} loading={saving}>
          {t.save}
        </Button>
      </Group>
      <Modal opened={confirmReset} onClose={() => setConfirmReset(false)} title={t.reset}>
        <Stack>
          <Text>{t.resetConfirm}</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfirmReset(false)}>
              {vi.common.cancel}
            </Button>
            <Button
              color="red"
              onClick={() => {
                setConfirmReset(false);
                onReset();
              }}
            >
              {vi.common.confirm}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}

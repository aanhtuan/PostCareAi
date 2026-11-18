// Form ngưỡng chính của camera (F08 R5, R9; HS §5.5; QA#22). Hiện giá trị đang áp dụng và giá trị
// mặc định bên cạnh. Lưu = thay toàn bộ override: khóa trên form bằng mặc định thì bỏ khỏi override,
// override của khóa không có trên form được giữ nguyên. "Khôi phục mặc định" gửi `{}` sau khi xác nhận.
import { Button, Group, Modal, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core';
import { useState } from 'react';

import { fmt, vi } from '../../i18n/vi';
import { getPath, setPath, THRESHOLD_GROUPS, THRESHOLD_KEYS } from './thresholdKeys';

type Limit = { min?: number | null; max?: number | null };

/** Quy tắc override do API trả (`config/camera_overrides.yaml`): web kiểm tra giống backend. */
export type ThresholdRules = {
  allowed: string[];
  limits?: Record<string, Limit>;
  relations?: { low: string; high: string; strict?: boolean }[];
};

export type ThresholdsData = {
  defaults: Record<string, unknown>;
  overrides: Record<string, unknown>;
  effective: Record<string, unknown>;
  config_version: number;
  rules: ThresholdRules;
};

/** Mẫu `a.*` khớp mọi khóa trong khối `a`; khác thì phải trùng hẳn. */
function matches(pattern: string, path: string): boolean {
  return pattern.endsWith('.*') ? path.startsWith(pattern.slice(0, -1)) : pattern === path;
}

function limitFor(rules: ThresholdRules, path: string): Limit | undefined {
  const entry = Object.entries(rules.limits ?? {}).find(([p]) => matches(p, path));
  return entry?.[1];
}

/** Lỗi từng ô: trống/âm, ngoài giới hạn an toàn, sai quan hệ (lỗi gắn vào ô `high`). */
function fieldErrors(
  values: Record<string, string>,
  data: ThresholdsData,
): Record<string, string | undefined> {
  const errors: Record<string, string | undefined> = {};
  const num = (path: string): number | null =>
    path in values ? parse(values[path]) : ((getPath(data.effective, path) as number) ?? null);
  for (const k of THRESHOLD_KEYS) {
    const v = parse(values[k]);
    const limit = limitFor(data.rules, k);
    if (v === null) errors[k] = t.required;
    else if (limit?.min != null && v < limit.min) errors[k] = fmt(t.min, { value: limit.min });
    else if (limit?.max != null && v > limit.max) errors[k] = fmt(t.max, { value: limit.max });
  }
  for (const rel of data.rules.relations ?? []) {
    const low = num(rel.low);
    const high = num(rel.high);
    if (low === null || high === null || errors[rel.high]) continue;
    if (low > high || (rel.strict && low >= high)) {
      const other = t.labels[rel.low] ?? rel.low;
      errors[rel.high] = fmt(rel.strict ? t.mustBeAbove : t.mustBeAtLeast, { other });
    }
  }
  return errors;
}

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
  const errors = fieldErrors(values, data);
  const invalid = Object.values(errors).filter(Boolean);

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
                error={errors[k]}
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

import { Group, Stack, Table, Text, Title } from '@mantine/core';

import type { BedStateOut } from '../../api/types';
import { vi } from '../../i18n/vi';
import { FaceSignalsPanel } from './FaceSignalsPanel';

export function ObservationDetails({
  cameraName,
  state,
}: {
  cameraName?: string;
  state: BedStateOut | null;
}) {
  const face =
    state?.face_status === 'OK' ? (
      <FaceSignalsPanel state={state} />
    ) : state ? (
      vi.faceStatus[state.face_status]
    ) : (
      vi.common.none
    );
  const rows = [
    [vi.live.activity, state ? vi.activity[state.activity_level] : vi.common.none],
    [vi.live.rest, state ? vi.rest[state.rest_status] : vi.common.none],
    [vi.live.faceSignals, face],
  ] as const;

  return (
    <Stack gap="xs">
      <Group justify="space-between" gap="xs">
        <Title order={3} size="h4">
          {vi.live.observationTitle}
        </Title>
        <Text size="sm" fw={500}>
          {cameraName ?? vi.camera.notAssigned}
        </Text>
      </Group>
      <Table verticalSpacing="xs" horizontalSpacing="xs" fz="md">
        <Table.Tbody>
          {rows.map(([label, value]) => (
            <Table.Tr key={label}>
              <Table.Th scope="row" w="42%" fw={500} c="dimmed">
                {label}
              </Table.Th>
              <Table.Td>{value}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}

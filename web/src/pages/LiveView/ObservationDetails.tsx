import { Accordion, Group, Stack, Text, Title } from '@mantine/core';

import type { BedStateOut } from '../../api/types';
import { RestStatusBadge } from '../../components/RestStatusBadge';
import { vi } from '../../i18n/vi';
import { FaceSignalsPanel } from './FaceSignalsPanel';

export function ObservationDetails({
  cameraName,
  state,
}: {
  cameraName?: string;
  state: BedStateOut | null;
}) {
  return (
    <Stack gap="xs">
      <Group justify="space-between" gap="xs">
        <Title order={3} size="h5">
          {vi.live.observationTitle}
        </Title>
        <Text size="sm" c="dimmed">
          {cameraName ?? vi.camera.notAssigned}
        </Text>
      </Group>
      {state ? (
        <>
          <Group gap="xs">
            {state.activity_level !== 'UNKNOWN' && (
              <Text size="sm">{vi.activity[state.activity_level]}</Text>
            )}
            {state.rest_status !== 'UNKNOWN' && <RestStatusBadge status={state.rest_status} />}
            {state.face_status === 'OK' && Object.values(state.face_signals).some(Boolean) && (
              <FaceSignalsPanel state={state} />
            )}
          </Group>
          <Accordion>
            <Accordion.Item value="details">
              <Accordion.Control>{vi.live.observationDetails}</Accordion.Control>
              <Accordion.Panel>
                <Stack gap="xs">
                  <Text size="sm">
                    {vi.live.activity} · {vi.activity[state.activity_level]}
                  </Text>
                  <Group gap="xs">
                    <Text size="sm">{vi.live.rest}</Text>
                    <RestStatusBadge status={state.rest_status} />
                  </Group>
                  <Stack gap={2}>
                    <Text size="sm">{vi.live.faceSignals}</Text>
                    <FaceSignalsPanel state={state} />
                  </Stack>
                </Stack>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        </>
      ) : (
        <Text size="sm" c="dimmed">
          {vi.live.noOtherSignals}
        </Text>
      )}
    </Stack>
  );
}

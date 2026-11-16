import {
  Badge,
  Button,
  Card,
  Group,
  Modal,
  Select,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { ApiError } from '../../api/client';
import { useBeds, useCameras, useEndSession, usePatients, useStartSession } from '../../api/hooks';
import type { BedOut } from '../../api/types';
import { useAuth } from '../../auth/useAuth';
import { vi } from '../../i18n/vi';
import { formatDateTime } from '../../utils/time';

function showError(err: unknown) {
  const message =
    err instanceof ApiError
      ? err.status === 403
        ? vi.common.forbidden
        : err.message
      : vi.common.genericError;
  notifications.show({ color: 'red', message });
}

function StartSessionDialog({ bed, onClose }: { bed: BedOut | null; onClose: () => void }) {
  const patients = usePatients();
  const start = useStartSession();
  const [patientId, setPatientId] = useState<string | null>(null);
  const free = (patients.data ?? []).filter((p) => p.active_session_id === null);

  return (
    <Modal
      opened={bed !== null}
      onClose={onClose}
      title={`${vi.session.start} - ${bed?.code ?? ''}`}
    >
      <Stack>
        {free.length === 0 ? (
          <Text c="dimmed">{vi.session.noFreePatient}</Text>
        ) : (
          <Select
            label={vi.session.choosePatient}
            data={free.map((p) => ({ value: String(p.id), label: p.code }))}
            value={patientId}
            onChange={setPatientId}
          />
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {vi.common.cancel}
          </Button>
          <Button
            disabled={!patientId || !bed}
            loading={start.isPending}
            onClick={() =>
              bed &&
              patientId &&
              start.mutate(
                { bed_id: bed.id, patient_id: Number(patientId) },
                {
                  onSuccess: () => {
                    notifications.show({ color: 'teal', message: vi.session.started });
                    setPatientId(null);
                    onClose();
                  },
                  onError: showError,
                },
              )
            }
          >
            {vi.common.confirm}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function ManagementPage() {
  const { canWrite } = useAuth();
  const beds = useBeds();
  const patients = usePatients();
  const cameras = useCameras();
  const end = useEndSession();
  const [startFor, setStartFor] = useState<BedOut | null>(null);
  const [endFor, setEndFor] = useState<BedOut | null>(null);

  return (
    <Stack>
      <Title order={2}>{vi.management.title}</Title>
      {!canWrite && <Text c="dimmed">{vi.management.readOnly}</Text>}
      <Card withBorder>
        <Title order={4} mb="xs">
          {vi.management.beds}
        </Title>
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{vi.bed.code}</Table.Th>
              <Table.Th>{vi.bed.area}</Table.Th>
              <Table.Th>{vi.management.cameras}</Table.Th>
              <Table.Th>{vi.management.currentPatient}</Table.Th>
              <Table.Th>{vi.management.startedAt}</Table.Th>
              {canWrite && <Table.Th>{vi.management.actions}</Table.Th>}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {(beds.data ?? []).map((b) => (
              <Table.Tr key={b.id}>
                <Table.Td fw={700}>{b.code}</Table.Td>
                <Table.Td>{b.area}</Table.Td>
                <Table.Td>
                  {b.camera
                    ? `${b.camera.name} · ${vi.cameraStatus[b.camera.status]}`
                    : vi.camera.notAssigned}
                </Table.Td>
                <Table.Td>{b.active_session?.patient_code ?? vi.bedCard.NOT_MONITORED}</Table.Td>
                <Table.Td>
                  {b.active_session ? formatDateTime(b.active_session.started_at) : vi.common.none}
                </Table.Td>
                {canWrite && (
                  <Table.Td>
                    {b.active_session ? (
                      <Button size="xs" color="gray" onClick={() => setEndFor(b)}>
                        {vi.session.end}
                      </Button>
                    ) : (
                      <Button size="xs" onClick={() => setStartFor(b)}>
                        {vi.session.start}
                      </Button>
                    )}
                  </Table.Td>
                )}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>

      <Group align="flex-start" grow>
        <Card withBorder>
          <Title order={4} mb="xs">
            {vi.management.patients}
          </Title>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{vi.management.patientCode}</Table.Th>
                <Table.Th>{vi.management.patientNote}</Table.Th>
                <Table.Th>{vi.camera.status}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(patients.data ?? []).map((p) => (
                <Table.Tr key={p.id}>
                  <Table.Td fw={600}>{p.code}</Table.Td>
                  <Table.Td>{p.note ?? vi.common.none}</Table.Td>
                  <Table.Td>
                    <Badge color={p.active_session_id ? 'teal' : 'gray'} variant="light">
                      {p.active_session_id ? vi.management.inSession : vi.management.free}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Card>
        <Card withBorder>
          <Title order={4} mb="xs">
            {vi.management.cameras}
          </Title>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{vi.camera.name}</Table.Th>
                <Table.Th>{vi.camera.sourceType}</Table.Th>
                <Table.Th>{vi.camera.source}</Table.Th>
                <Table.Th>{vi.common.bed}</Table.Th>
                <Table.Th>{vi.camera.status}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(cameras.data ?? []).map((c) => (
                <Table.Tr key={c.id}>
                  <Table.Td>{c.name}</Table.Td>
                  <Table.Td>{vi.sourceType[c.source_type]}</Table.Td>
                  <Table.Td ff="monospace">{c.source}</Table.Td>
                  <Table.Td>{c.bed_code ?? vi.common.none}</Table.Td>
                  <Table.Td>{vi.cameraStatus[c.status]}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Card>
      </Group>

      <StartSessionDialog bed={startFor} onClose={() => setStartFor(null)} />
      <Modal opened={endFor !== null} onClose={() => setEndFor(null)} title={vi.session.end}>
        <Stack>
          <Text>{vi.session.confirmEnd}</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setEndFor(null)}>
              {vi.common.cancel}
            </Button>
            <Button
              color="red"
              loading={end.isPending}
              onClick={() =>
                endFor?.active_session &&
                end.mutate(endFor.active_session.id, {
                  onSuccess: () => {
                    notifications.show({ color: 'teal', message: vi.session.ended });
                    setEndFor(null);
                  },
                  onError: showError,
                })
              }
            >
              {vi.common.confirm}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}

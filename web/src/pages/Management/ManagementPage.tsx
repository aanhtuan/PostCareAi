// Màn hình "Quản lý giường" (PDF §9.1; F03): giường, bệnh nhân, camera.
// ADMIN thêm/sửa/xóa (mềm)/khôi phục; vai trò khác chỉ xem danh mục (QA#15, QA#36).
// Mở/kết thúc phiên (F04) vẫn dành cho vai trò được ghi. Khu vực, ca trực: F37.
import { Badge, Button, Group, Stack, Switch, Table, Text, Title } from '@mantine/core';
import { useState } from 'react';

import { useBeds, useCameras, usePatients } from '../../api/hooks';
import { CATALOG_ADMIN_ROLES, type BedOut, type CameraOut, type PatientOut } from '../../api/types';
import { useAuth } from '../../auth/useAuth';
import { fmt, vi } from '../../i18n/vi';
import { formatTime } from '../../utils/time';
import { AreasTab } from './AreasTab';
import { BedForm } from './BedForm';
import { CameraForm } from './CameraForm';
import { useRestore } from './catalogActions';
import {
  ConfirmDeleteDialog,
  RowActions,
  Section,
  UsageBadge,
  type DeleteTarget,
} from './CatalogParts';
import { EndSessionButton } from './EndSessionButton';
import { PatientForm } from './PatientForm';
import { PauseCaptureButton } from './PauseCaptureButton';
import { ShiftsTab } from './ShiftsTab';
import { StartSessionDialog } from './StartSessionDialog';
import { TransferSessionDialog } from './TransferSessionDialog';

/** Bệnh nhân của phiên đang mở, kèm "Chuyển từ giường …" và nhãn tạm dừng thu hình. */
function SessionCell({ bed }: { bed: BedOut }) {
  const s = bed.active_session;
  if (!s) return <>{vi.common.none}</>;
  return (
    <Stack gap={2}>
      <Text size="sm">{s.patient_code}</Text>
      {s.previous_bed_code && (
        <Text size="xs" c="dimmed">
          {fmt(vi.session.transferredFrom, { bed: s.previous_bed_code })}
        </Text>
      )}
      {s.paused_at && (
        <Badge color="orange" variant="light" title={vi.capture.paused}>
          {vi.capture.pausedShort}
        </Badge>
      )}
    </Stack>
  );
}

type FormState =
  | { kind: 'bed'; item: BedOut | null }
  | { kind: 'patient'; item: PatientOut | null }
  | { kind: 'camera'; item: CameraOut | null }
  | null;

export function ManagementPage() {
  const { user, canWrite } = useAuth();
  const isAdmin = user !== null && CATALOG_ADMIN_ROLES.includes(user.role);
  const [showDeleted, setShowDeleted] = useState(false);
  const beds = useBeds(showDeleted);
  const patients = usePatients(showDeleted);
  const cameras = useCameras(showDeleted);
  const restore = useRestore();
  const [startFor, setStartFor] = useState<BedOut | null>(null);
  const [transferFor, setTransferFor] = useState<BedOut | null>(null);
  const [form, setForm] = useState<FormState>(null);
  const [toDelete, setToDelete] = useState<DeleteTarget | null>(null);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{vi.management.title}</Title>
        <Switch
          label={vi.catalog.showDeleted}
          checked={showDeleted}
          onChange={(e) => setShowDeleted(e.currentTarget.checked)}
        />
      </Group>
      {!isAdmin && <Text c="dimmed">{vi.catalog.readOnly}</Text>}

      <Section
        title={vi.management.beds}
        canAdd={isAdmin}
        onAdd={() => setForm({ kind: 'bed', item: null })}
      >
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{vi.bed.code}</Table.Th>
              <Table.Th>{vi.bed.area}</Table.Th>
              <Table.Th>{vi.management.cameras}</Table.Th>
              <Table.Th>{vi.management.currentPatient}</Table.Th>
              <Table.Th>{vi.management.startedAt}</Table.Th>
              <Table.Th>{vi.catalog.usage}</Table.Th>
              {(canWrite || isAdmin) && <Table.Th>{vi.management.actions}</Table.Th>}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {(beds.data ?? []).map((b) => (
              <Table.Tr key={b.id}>
                <Table.Td fw={700}>{b.code}</Table.Td>
                <Table.Td>{b.area.name}</Table.Td>
                <Table.Td>
                  {b.camera
                    ? `${b.camera.name} · ${vi.cameraStatus[b.camera.status]}`
                    : vi.camera.notAssigned}
                </Table.Td>
                <Table.Td>
                  <SessionCell bed={b} />
                </Table.Td>
                <Table.Td>
                  {b.active_session ? formatTime(b.active_session.started_at) : vi.common.none}
                </Table.Td>
                <Table.Td>
                  <UsageBadge active={b.is_active} />
                </Table.Td>
                {(canWrite || isAdmin) && (
                  <Table.Td>
                    <Group gap="xs" wrap="nowrap">
                      {canWrite &&
                        b.is_active &&
                        (b.active_session ? (
                          <>
                            <EndSessionButton session={b.active_session} />
                            <Button size="xs" variant="light" onClick={() => setTransferFor(b)}>
                              {vi.session.transfer}
                            </Button>
                            <PauseCaptureButton session={b.active_session} />
                          </>
                        ) : (
                          <Button size="xs" onClick={() => setStartFor(b)}>
                            {vi.session.start}
                          </Button>
                        ))}
                      {isAdmin && (
                        <RowActions
                          active={b.is_active}
                          onEdit={() => setForm({ kind: 'bed', item: b })}
                          onDelete={() =>
                            setToDelete({
                              resource: 'beds',
                              id: b.id,
                              name: fmt(vi.bed.title, { code: b.code }),
                            })
                          }
                          onRestore={() =>
                            restore('beds', b.id, fmt(vi.bed.title, { code: b.code }))
                          }
                        />
                      )}
                    </Group>
                  </Table.Td>
                )}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Section>

      <Group align="flex-start" grow>
        <Section
          title={vi.management.patients}
          canAdd={isAdmin}
          onAdd={() => setForm({ kind: 'patient', item: null })}
        >
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{vi.management.patientCode}</Table.Th>
                <Table.Th>{vi.management.patientNote}</Table.Th>
                <Table.Th>{vi.camera.status}</Table.Th>
                {isAdmin && <Table.Th>{vi.management.actions}</Table.Th>}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(patients.data ?? []).map((p) => (
                <Table.Tr key={p.id}>
                  <Table.Td fw={600}>{p.code}</Table.Td>
                  <Table.Td>{p.note ?? vi.common.none}</Table.Td>
                  <Table.Td>
                    {p.is_active ? (
                      <Badge color={p.active_session_id ? 'teal' : 'gray'} variant="light">
                        {p.active_session_id ? vi.management.inSession : vi.management.free}
                      </Badge>
                    ) : (
                      <UsageBadge active={false} />
                    )}
                  </Table.Td>
                  {isAdmin && (
                    <Table.Td>
                      <RowActions
                        active={p.is_active}
                        onEdit={() => setForm({ kind: 'patient', item: p })}
                        onDelete={() =>
                          setToDelete({
                            resource: 'patients',
                            id: p.id,
                            name: fmt(vi.bedCard.patient, { code: p.code }),
                          })
                        }
                        onRestore={() =>
                          restore('patients', p.id, fmt(vi.bedCard.patient, { code: p.code }))
                        }
                      />
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Section>

        <Section
          title={vi.management.cameras}
          canAdd={isAdmin}
          onAdd={() => setForm({ kind: 'camera', item: null })}
        >
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{vi.camera.name}</Table.Th>
                <Table.Th>{vi.camera.sourceType}</Table.Th>
                <Table.Th>{vi.camera.source}</Table.Th>
                <Table.Th>{vi.common.bed}</Table.Th>
                <Table.Th>{vi.camera.status}</Table.Th>
                {isAdmin && <Table.Th>{vi.management.actions}</Table.Th>}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(cameras.data ?? []).map((c) => (
                <Table.Tr key={c.id}>
                  <Table.Td>{c.name}</Table.Td>
                  <Table.Td>{vi.sourceType[c.source_type]}</Table.Td>
                  <Table.Td ff="monospace">{c.source}</Table.Td>
                  <Table.Td>{c.bed_code ?? vi.common.none}</Table.Td>
                  <Table.Td>
                    {c.is_active ? vi.cameraStatus[c.status] : <UsageBadge active={false} />}
                  </Table.Td>
                  {isAdmin && (
                    <Table.Td>
                      <RowActions
                        active={c.is_active}
                        onEdit={() => setForm({ kind: 'camera', item: c })}
                        onDelete={() =>
                          setToDelete({ resource: 'cameras', id: c.id, name: c.name })
                        }
                        onRestore={() => restore('cameras', c.id, c.name)}
                      />
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Section>
      </Group>

      <Group align="flex-start" grow>
        <AreasTab isAdmin={isAdmin} showDeleted={showDeleted} />
        <ShiftsTab isAdmin={isAdmin} showDeleted={showDeleted} />
      </Group>

      {form?.kind === 'bed' && (
        <BedForm key={form.item?.id ?? 'new'} bed={form.item} onClose={() => setForm(null)} />
      )}
      {form?.kind === 'patient' && (
        <PatientForm
          key={form.item?.id ?? 'new'}
          patient={form.item}
          onClose={() => setForm(null)}
        />
      )}
      {form?.kind === 'camera' && (
        <CameraForm key={form.item?.id ?? 'new'} camera={form.item} onClose={() => setForm(null)} />
      )}
      <ConfirmDeleteDialog target={toDelete} onClose={() => setToDelete(null)} />
      <StartSessionDialog bed={startFor} onClose={() => setStartFor(null)} />
      <TransferSessionDialog
        bed={transferFor}
        beds={beds.data ?? []}
        onClose={() => setTransferFor(null)}
      />
    </Stack>
  );
}

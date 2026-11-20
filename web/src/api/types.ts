// Alias cho type sinh từ OpenAPI (schema.d.ts: không sửa tay, chạy `npm run gen-api-types`).
import type { components } from './schema';

type S = components['schemas'];

export type UserRole = S['UserRole'];
export type UserOut = S['UserOut'];
export type UserRef = S['UserRef'];
export type LoginOut = S['LoginOut'];
export type BodyState = S['BodyState'];
export type ObservationQuality = S['ObservationQuality'];
export type ActivityLevel = S['ActivityLevel'];
export type RestStatus = S['RestStatus'];
export type FaceStatus = S['FaceStatus'];
export type Priority = S['Priority'];
export type AlertStatus = S['AlertStatus'];
export type AlertOutcome = S['AlertOutcome'];
export type EventCode = S['EventCode'];
export type CameraStatus = S['CameraStatus'];
export type CameraSourceType = S['CameraSourceType'];
export type DisplayMode = S['DisplayMode'];
export type ObservationProfile = S['ObservationProfile'];

export type ShiftOut = S['ShiftOut'];
// F37: khu vực, quản lý ca trực.
export type AreaOut = S['AreaOut'];
export type AreaRef = S['AreaRef'];
export type AreaCreate = S['AreaCreate'];
export type ShiftCreate = S['ShiftCreate'];
export type BedOut = S['BedOut'];
export type PatientOut = S['PatientOut'];
export type CameraOut = S['CameraOut'];
export type CameraDetailOut = S['CameraDetailOut'];
export type CameraRuntimeOut = S['CameraRuntimeOut'];
export type CameraRoiOut = S['CameraRoiOut'];
export type CameraThresholdsOut = S['CameraThresholdsOut'];
export type BedCreate = S['BedCreate'];
export type BedUpdate = S['BedUpdate'];
export type PatientCreate = S['PatientCreate'];
export type PatientUpdate = S['PatientUpdate'];
export type CameraCreate = S['CameraCreate'];
export type CameraUpdate = S['CameraUpdate'];
export type SessionOut = S['SessionOut'];
export type BedStateOut = S['BedStateOut'];
export type EventOut = S['EventOut'];
export type AlertOut = S['AlertOut'];
export type OverviewOut = S['OverviewOut'];
export type OverviewBedOut = S['OverviewBedOut'];
export type TimelineItemOut = S['TimelineItemOut'];
export type HandoverOut = S['HandoverOut'];
export type HandoverBedOut = S['HandoverBedOut'];

export type Page<T> = { items: T[]; total: number };

// Payload WebSocket không có trong OpenAPI (chỉ phát qua /api/v1/ws).
export type AlertCreatedOut = { alert: AlertOut; event: EventOut };
export type CameraStatusOut = {
  camera_id: number;
  bed_id: number | null;
  status: CameraStatus;
  fps: number | null;
  brightness: number | null;
};

export const PRIORITIES: Priority[] = ['LOG', 'INFO', 'MEDIUM', 'HIGH'];
export const ALERT_STATUSES: AlertStatus[] = ['PENDING', 'ACKNOWLEDGED', 'RESOLVED'];
export const WRITE_ROLES: UserRole[] = ['NURSE', 'CHARGE_NURSE', 'ADMIN'];
/** Quản lý danh mục giường, bệnh nhân, camera (F03; api-conventions.md). */
export const CATALOG_ADMIN_ROLES: UserRole[] = ['ADMIN'];
export const SOURCE_TYPES: CameraSourceType[] = ['WEBCAM', 'URL', 'FILE'];
export const OBSERVATION_PROFILES: ObservationProfile[] = [
  'BED_MONITORING',
  'ABNORMAL_MOVEMENT',
  'FACE_SIGNALS',
];
// F35: vai trò nhân viên (FAMILY không vào được giao diện nhân viên) và thứ tự hiển thị.
export const STAFF_ROLES: UserRole[] = ['NURSE', 'CHARGE_NURSE', 'DOCTOR', 'ADMIN'];
export const USER_ROLES: UserRole[] = [...STAFF_ROLES, 'FAMILY'];
export type UserCreate = S['UserCreate'];
export type UserUpdate = S['UserUpdate'];

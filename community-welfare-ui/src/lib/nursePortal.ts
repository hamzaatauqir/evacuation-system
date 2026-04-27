export type NurseComplaintItem = {
  complaint_id?: string;
  subject?: string;
  category?: string;
  priority?: string;
  status?: string;
  submitted_date?: string;
  last_update_date?: string;
  public_response?: string;
};

export type NursePortalContext = {
  referenceId: string;
  nurseDbId?: number;
  fullName: string;
  email: string;
  passportMasked: string;
  civilIdMasked: string;
  passportNumber: string;
  civilId: string;
  mobile: string;
  hospital: string;
  registrationStatus: string;
  lastUpdated: string;
  remarks: string;
  complaints: NurseComplaintItem[];
  /** Opaque marker from server after password login (not a secret session token). */
  sessionMarker?: string;
};

export type LocalPortalRequest = {
  id: string;
  type: 'Accommodation' | 'Complaint' | 'Leaving Notice';
  status: 'Submitted';
  submittedAt: string;
  summary: string;
};

const SESSION_KEY = 'cwa_nurse_portal';
const REQUESTS_KEY = 'cwa_nurse_requests';

function maskValue(v: string, keepEnd = 3) {
  const s = (v || '').trim();
  if (!s) return '';
  if (s.length <= keepEnd + 1) return '*'.repeat(Math.max(1, s.length - 1)) + s.slice(-1);
  return '*'.repeat(s.length - keepEnd) + s.slice(-keepEnd);
}

function readJson<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function getNursePortal(): NursePortalContext | null {
  if (typeof window === 'undefined') return null;
  return readJson<NursePortalContext>(SESSION_KEY);
}

export function setNursePortal(ctx: NursePortalContext) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(ctx));
}

export function clearNursePortal() {
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(REQUESTS_KEY);
}

export function hasNursePortal() {
  return !!getNursePortal();
}

export function maskPassport(value: string) {
  return maskValue(value, 3);
}

export function maskCivilId(value: string) {
  return maskValue(value, 3);
}

export function buildPortalContextFromApiData(data: any): NursePortalContext {
  const ref = (data?.reference_id || '').toString();
  const passport = (data?.passport_number || '').toString();
  const civil = (data?.civil_id || '').toString();
  return {
    referenceId: ref,
    nurseDbId: typeof data?.nurse_db_id === "number" ? data.nurse_db_id : undefined,
    fullName: (data?.full_name || '').toString(),
    email: (data?.email || '').toString(),
    passportMasked: maskPassport(passport),
    civilIdMasked: maskCivilId(civil),
    passportNumber: passport,
    civilId: civil,
    mobile: (data?.mobile || '').toString(),
    hospital: (data?.hospital || '').toString(),
    registrationStatus: (data?.registration_status || '').toString(),
    lastUpdated: (data?.process_last_updated_at || '').toString(),
    remarks: (data?.latest_admin_remarks || data?.remarks || '').toString(),
    complaints: Array.isArray(data?.complaints) ? data.complaints : [],
    sessionMarker: (data?.session_marker || "").toString() || undefined,
  };
}

/** @deprecated use buildPortalContextFromApiData */
export const buildPortalContextFromTrackResponse = buildPortalContextFromApiData;

export function getLocalPortalRequests(): LocalPortalRequest[] {
  if (typeof window === 'undefined') return [];
  return readJson<LocalPortalRequest[]>(REQUESTS_KEY) || [];
}

export function addLocalPortalRequest(item: Omit<LocalPortalRequest, 'id' | 'submittedAt' | 'status'>) {
  const list = getLocalPortalRequests();
  const next: LocalPortalRequest = {
    id: `REQ-${Date.now()}`,
    submittedAt: new Date().toLocaleString(),
    status: 'Submitted',
    ...item,
  };
  sessionStorage.setItem(REQUESTS_KEY, JSON.stringify([next, ...list].slice(0, 30)));
}

// Backward-compatible aliases during transition
export const getNursePortalContext = getNursePortal;
export const setNursePortalContext = setNursePortal;
export const clearNursePortalContext = clearNursePortal;

// TODO: Backend should enforce nurse verification for request endpoints (not only frontend UX guards).

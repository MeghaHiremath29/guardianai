import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

const TOKEN_KEY = 'guardianai_access_token'
const REFRESH_KEY = 'guardianai_refresh_token'

export const tokenStorage = {
  getAccess: () => localStorage.getItem(TOKEN_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access: string, refresh: string) => {
    localStorage.setItem(TOKEN_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStorage.getAccess()
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On a 401, try exactly one silent refresh before giving up and logging out.
let isRefreshing = false

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry && !isRefreshing) {
      const refreshToken = tokenStorage.getRefresh()
      if (!refreshToken) {
        tokenStorage.clear()
        return Promise.reject(error)
      }

      originalRequest._retry = true
      isRefreshing = true
      try {
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken })
        tokenStorage.set(data.access_token, data.refresh_token)
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${data.access_token}`
        }
        return api(originalRequest)
      } catch (refreshError) {
        tokenStorage.clear()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  },
)

// ---- Types matching the backend Pydantic schemas exactly ----

export type UserRole = 'ADMIN' | 'CARETAKER' | 'FAMILY' | 'DOCTOR' | 'EMERGENCY_RESPONDER'

export interface UserOut {
  id: string
  full_name: string
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

// ---- API calls ----

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>('/auth/login', { email, password })
  return data
}

export async function register(
  full_name: string,
  email: string,
  password: string,
  role: UserRole,
): Promise<UserOut> {
  const { data } = await api.post<UserOut>('/auth/register', { full_name, email, password, role })
  return data
}

export async function fetchCurrentUser(): Promise<UserOut> {
  const { data } = await api.get<UserOut>('/users/me')
  return data
}

// ---- Phase 2: People, Devices, Sensors, Emergencies ----

export interface EmergencyContact {
  id?: string
  name: string
  relation: string
  phone?: string | null
  email?: string | null
  priority_order: number
}

export interface Person {
  id: string
  name: string
  age: number | null
  address: string | null
  latitude: number | null
  longitude: number | null
  medical_notes: string | null
  assigned_caretaker_id: string | null
  doctor_id: string | null
  created_by_id: string
  created_at: string
  emergency_contacts: EmergencyContact[]
}

export interface PersonCreate {
  name: string
  age?: number
  address?: string
  latitude?: number
  longitude?: number
  medical_notes?: string
  emergency_contacts?: EmergencyContact[]
}

export async function listPeople(): Promise<Person[]> {
  const { data } = await api.get<Person[]>('/people')
  return data
}

export async function createPerson(payload: PersonCreate): Promise<Person> {
  const { data } = await api.post<Person>('/people', payload)
  return data
}

export type DeviceStatus = 'ONLINE' | 'OFFLINE'

export interface Device {
  id: string
  device_name: string
  device_type: string
  person_id: string
  status: DeviceStatus
  battery_level: number
  last_seen: string | null
  created_at: string
}

export async function listDevices(): Promise<Device[]> {
  const { data } = await api.get<Device[]>('/devices')
  return data
}

export async function createDevice(device_name: string, person_id: string): Promise<Device> {
  const { data } = await api.post<Device>('/devices', { device_name, person_id })
  return data
}

export interface SensorReadingOut {
  id: string
  device_id: string
  timestamp: string
  heart_rate: number | null
  accel_x: number
  accel_y: number
  accel_z: number
  accel_magnitude: number
  orientation: string
  movement: string
  inactivity_duration: number
}

export async function getReadingHistory(deviceId: string, limit = 50): Promise<SensorReadingOut[]> {
  const { data } = await api.get<SensorReadingOut[]>(`/sensors/${deviceId}/history`, { params: { limit } })
  return data
}

export type Scenario = 'NORMAL' | 'WALKING' | 'FALL' | 'FALL_HIGH_HEART_RATE' | 'INACTIVITY_AFTER_FALL'

export interface DetectionResultOut {
  event_type: string
  confidence: number
  severity: 'NORMAL' | 'WARNING' | 'HIGH' | 'CRITICAL'
  reasons: string[]
  emergency_created: boolean
  emergency_id: string | null
}

export async function runSimulation(
  deviceId: string,
  scenario: Scenario,
  duration_seconds = 20,
): Promise<DetectionResultOut> {
  const { data } = await api.post<DetectionResultOut>(`/sensors/${deviceId}/simulate`, {
    scenario,
    duration_seconds,
  })
  return data
}

export type EmergencySeverity = 'NORMAL' | 'WARNING' | 'HIGH' | 'CRITICAL'
export type EmergencyStatusValue = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED' | 'FALSE_ALARM'

export interface EmergencyOut {
  id: string
  event_type: string
  person_id: string
  device_id: string | null
  source: string
  confidence: number
  severity: EmergencySeverity
  status: EmergencyStatusValue
  reasons: string[]
  location_lat: number | null
  location_lng: number | null
  created_at: string
  acknowledged_at: string | null
  resolved_at: string | null
}

export interface EmergencyTimelineEntry {
  id: string
  event_text: string
  actor_id: string | null
  timestamp: string
}

export interface EmergencyDetailOut extends EmergencyOut {
  timeline: EmergencyTimelineEntry[]
}

export async function listEmergencies(): Promise<EmergencyOut[]> {
  const { data } = await api.get<EmergencyOut[]>('/emergencies')
  return data
}

export async function getEmergency(id: string): Promise<EmergencyDetailOut> {
  const { data } = await api.get<EmergencyDetailOut>(`/emergencies/${id}`)
  return data
}

export async function acknowledgeEmergency(id: string): Promise<EmergencyDetailOut> {
  const { data } = await api.post<EmergencyDetailOut>(`/emergencies/${id}/acknowledge`)
  return data
}

export async function resolveEmergency(id: string): Promise<EmergencyDetailOut> {
  const { data } = await api.post<EmergencyDetailOut>(`/emergencies/${id}/resolve`)
  return data
}

export async function markFalseAlarm(id: string): Promise<EmergencyDetailOut> {
  const { data } = await api.post<EmergencyDetailOut>(`/emergencies/${id}/false-alarm`)
  return data
}

// ---- Notifications ----

export type NotificationChannelType = 'EMAIL' | 'TELEGRAM'
export type NotificationDeliveryStatus = 'SENT' | 'FAILED' | 'SKIPPED'
export type RecipientRole = 'CARETAKER' | 'FAMILY' | 'DOCTOR'

export interface NotificationOut {
  id: string
  emergency_id: string
  recipient_role: RecipientRole
  recipient_name: string | null
  recipient_address: string | null
  channel: NotificationChannelType
  status: NotificationDeliveryStatus
  detail: string | null
  escalation_step: number
  created_at: string
}

export async function listNotifications(emergencyId?: string): Promise<NotificationOut[]> {
  const { data } = await api.get<NotificationOut[]>('/notifications', {
    params: emergencyId ? { emergency_id: emergencyId } : undefined,
  })
  return data
}

export async function sendTestNotification(recipientEmail: string): Promise<{ status: string; detail: string }> {
  const { data } = await api.post('/notifications/test', null, { params: { recipient_email: recipientEmail } })
  return data
}

// ---- Video / image analysis ----

export type AnalysisType = 'TRAFFIC_ACCIDENT' | 'FIRE_SMOKE'
export type MediaType = 'VIDEO' | 'IMAGE'
export type AnalysisStatusValue = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'

export interface EvidenceItem {
  id: string
  file_path: string
  file_type: string
  description: string | null
}

export interface VideoAnalysisOut {
  id: string
  person_id: string | null
  emergency_id: string | null
  analysis_type: AnalysisType
  media_type: MediaType
  status: AnalysisStatusValue
  original_filename: string
  location_lat: number | null
  location_lng: number | null
  location_label: string | null
  detected: boolean | null
  confidence: number | null
  severity: EmergencySeverity | null
  reasons: string[]
  event_timestamp_seconds: number | null
  error_detail: string | null
  created_at: string
  processed_at: string | null
  evidence: EvidenceItem[]
}

export async function uploadVideoForAnalysis(
  file: File,
  analysisType: AnalysisType,
  personId?: string,
): Promise<VideoAnalysisOut> {
  const form = new FormData()
  form.append('file', file)
  form.append('analysis_type', analysisType)
  if (personId) form.append('person_id', personId)

  const { data } = await api.post<VideoAnalysisOut>('/videos/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // video processing can genuinely take a while on CPU
  })
  return data
}

export async function listVideoAnalyses(): Promise<VideoAnalysisOut[]> {
  const { data } = await api.get<VideoAnalysisOut[]>('/videos')
  return data
}

export async function fetchEvidenceFrameBlobUrl(analysisId: string, evidenceId: string): Promise<string> {
  const { data } = await api.get(`/videos/${analysisId}/evidence/${evidenceId}`, { responseType: 'blob' })
  return URL.createObjectURL(data)
}

// ---- Analytics ----

export interface AnalyticsSummary {
  total_emergencies: number
  open_count: number
  acknowledged_count: number
  resolved_count: number
  false_alarm_count: number
  critical_count: number
  high_count: number
  warning_count: number
  false_alarm_rate: number
  avg_acknowledgement_seconds: number | null
  avg_response_seconds: number | null
  devices_online: number
  devices_total: number
}

export interface TypeBreakdownItem {
  event_type: string
  count: number
}

export interface SeverityBreakdownItem {
  severity: string
  count: number
}

export interface TrendPoint {
  date: string
  count: number
}

export interface AnalyticsTrends {
  by_type: TypeBreakdownItem[]
  by_severity: SeverityBreakdownItem[]
  daily_counts: TrendPoint[]
}

export interface DeviceUptimeItem {
  device_id: string
  device_name: string
  status: string
  last_seen: string | null
  battery_level: number
}

export async function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  const { data } = await api.get<AnalyticsSummary>('/analytics/summary')
  return data
}

export async function getAnalyticsTrends(days = 14): Promise<AnalyticsTrends> {
  const { data } = await api.get<AnalyticsTrends>('/analytics/trends', { params: { days } })
  return data
}

export async function getDeviceUptime(): Promise<DeviceUptimeItem[]> {
  const { data } = await api.get<DeviceUptimeItem[]>('/analytics/device-uptime')
  return data
}

// ---- Audit logs (admin only) ----

export interface AuditLogEntry {
  id: string
  action: string
  actor_id: string | null
  actor_email: string | null
  entity_type: string | null
  entity_id: string | null
  detail: string | null
  created_at: string
}

export async function listAuditLogs(limit = 100): Promise<AuditLogEntry[]> {
  const { data } = await api.get<AuditLogEntry[]>('/audit-logs', { params: { limit } })
  return data
}

// ---- System config (admin only, read-only) ----

export interface SystemConfig {
  environment: string
  fall_detection: {
    acceleration_spike_score: number
    orientation_change_score: number
    inactivity_max_score: number
    abnormal_heart_rate_score: number
    critical_threshold: number
    high_threshold: number
    warning_threshold: number
  }
  escalation: {
    step1_delay_seconds: number
    step2_delay_seconds: number
    check_interval_seconds: number
  }
  uploads: { max_upload_size_mb: number }
  notifications: { smtp_configured: boolean; telegram_configured: boolean }
  editable_note: string
}

export async function getSystemConfig(): Promise<SystemConfig> {
  const { data } = await api.get<SystemConfig>('/system/config')
  return data
}

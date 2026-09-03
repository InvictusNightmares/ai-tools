import { apiClient } from '../client'

export interface PolicyRecord {
  id: string
  recorded_at: string
  request_id: string
  api_key_id: number
  api_key_name: string
  user_id: number
  group_name?: string
  account_id: number
  model: string
  error_code: string
  protocol: string
  body_bytes: number
  body_encoding?: string
  [key: string]: unknown
}
export interface PolicyQuery {
  page: number
  page_size: number
  key?: string
  model?: string
  error_code?: string
  start_time?: string
  end_time?: string
}
export interface PolicyList {
  records: { items: PolicyRecord[]; total: number; page: number; page_size: number; index_pending: boolean; index_limited: boolean; unreadable_files: number; disk_bytes: number }
  status: { enabled: boolean; retention_days: number; max_disk_mb: number; runtime: { written: number; dropped: number; write_errors: number } }
}
export interface PolicyDetail { record: Omit<PolicyRecord, 'id'>; body_preview: string; preview_truncated: boolean }
export const policyRequestsAPI = {
  async list(params: PolicyQuery, signal?: AbortSignal): Promise<PolicyList> {
    return (await apiClient.get('/admin/policy-requests', { params, signal })).data
  },
  async get(id: string, signal?: AbortSignal): Promise<PolicyDetail> {
    return (await apiClient.get(`/admin/policy-requests/${encodeURIComponent(id)}`, { signal })).data
  },
  async download(id: string): Promise<Blob> {
    return (await apiClient.get(`/admin/policy-requests/${encodeURIComponent(id)}/body`, { responseType: 'blob' })).data
  }
}

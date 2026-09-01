import type { QrResolution } from '../types/api'
import { apiFetch } from './apiClient'

export function resolveQrToken(token: string): Promise<QrResolution> {
  return apiFetch<QrResolution>(`/api/qr/${token}`)
}

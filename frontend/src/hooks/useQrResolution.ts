import { useQuery } from '@tanstack/react-query'
import { resolveQrToken } from '../services/qr'

export function useQrResolution(token: string) {
  return useQuery({
    queryKey: ['qr-resolution', token],
    queryFn: () => resolveQrToken(token),
  })
}

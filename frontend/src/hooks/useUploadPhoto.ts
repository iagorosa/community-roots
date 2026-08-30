import { useMutation, useQueryClient } from '@tanstack/react-query'
import { uploadPhoto, type UploadPhotoParams } from '../services/photos'

// The first `useMutation` in the frontend (`useRegion`/`usePhotos` are
// reads) — `PhotoUploadForm` is the only caller today. Invalidating
// `['photos', identifier]` on success is exactly `usePhotos`' query key, so
// a successful upload makes the timeline refetch and show the new photo on
// its own, with no manual refresh or navigation (issue #29's scope).
export function useUploadPhoto(identifier: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (params: UploadPhotoParams) => uploadPhoto(identifier, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['photos', identifier] })
    },
  })
}

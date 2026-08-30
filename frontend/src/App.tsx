import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router'
import AppRoutes from './AppRoutes.tsx'

// One client for the app's lifetime — hooks/useRegions.ts (and the hooks
// that follow it: useRegion, useRegionPhotos, useUploadPhoto) are useless
// without a QueryClientProvider ancestor.
const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Photo } from '../../types/api'
import PhotoUploadForm from './PhotoUploadForm.tsx'

const UPLOADED_PHOTO: Photo = {
  id: '1a2b3c4d-5e6f-7890-abcd-ef1234567890',
  description: null,
  contributor_name: null,
  captured_at: null,
  uploaded_at: '2026-08-24T14:05:00Z',
  latitude: null,
  longitude: null,
  width: 1080,
  height: 1350,
  photo_url: '/api/photos/1a2b3c4d-5e6f-7890-abcd-ef1234567890/file',
}

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response
}

function selectFile(input: HTMLElement, file: File) {
  fireEvent.change(input, { target: { files: [file] } })
}

function makeFile() {
  return new File(['fake-image-bytes'], 'canteiro.jpg', { type: 'image/jpeg' })
}

function renderForm(queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return { queryClient, ...render(<PhotoUploadForm slug="canteiro-do-ipe" />, { wrapper: Wrapper }) }
}

describe('PhotoUploadForm', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows an image preview once a file is selected', () => {
    renderForm()

    selectFile(screen.getByLabelText('Foto'), makeFile())

    const preview = screen.getByAltText(/pré-visualização/i)
    expect(preview).toBeInTheDocument()
    expect(preview.getAttribute('src')).toMatch(/^blob:/)
  })

  it('starts with the share-location checkbox unchecked', () => {
    renderForm()

    expect(screen.getByRole('checkbox', { name: /compartilhar/i })).not.toBeChecked()
  })

  it('disables the submit button until a file is selected', () => {
    renderForm()

    expect(screen.getByRole('button', { name: /enviar foto/i })).toBeDisabled()

    selectFile(screen.getByLabelText('Foto'), makeFile())

    expect(screen.getByRole('button', { name: /enviar foto/i })).toBeEnabled()
  })

  it('submits successfully with the name and observation left blank', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(UPLOADED_PHOTO, 201))
    vi.stubGlobal('fetch', fetchMock)
    renderForm()

    selectFile(screen.getByLabelText('Foto'), makeFile())
    fireEvent.click(screen.getByRole('button', { name: /enviar foto/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(path).toBe('/api/plantings/canteiro-do-ipe/photos')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
  })

  it('sends a FormData body containing the selected file', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(UPLOADED_PHOTO, 201))
    vi.stubGlobal('fetch', fetchMock)
    renderForm()
    const file = makeFile()

    selectFile(screen.getByLabelText('Foto'), file)
    fireEvent.click(screen.getByRole('button', { name: /enviar foto/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const body = init.body as FormData
    expect(body.get('file')).toBe(file)
  })

  it('disables the submit button while the upload is in flight', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))
    renderForm()

    selectFile(screen.getByLabelText('Foto'), makeFile())
    fireEvent.click(screen.getByRole('button', { name: /enviar foto/i }))

    await waitFor(() => expect(screen.getByRole('button', { name: /enviando/i })).toBeDisabled())
  })

  it('clears the form and invalidates the photos query once the upload succeeds', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(UPLOADED_PHOTO, 201))
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    renderForm(queryClient)

    selectFile(screen.getByLabelText('Foto'), makeFile())
    fireEvent.click(screen.getByRole('button', { name: /enviar foto/i }))

    // Exactly `usePhotos`' query key (`hooks/usePhotos.ts`) — this is what
    // makes the timeline refetch and show the new photo on its own, with
    // no manual refresh or navigation (issue #29's scope).
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['photos', 'canteiro-do-ipe'] }),
    )
    expect(screen.queryByAltText(/pré-visualização/i)).not.toBeInTheDocument()
  })

  it('shows the backend error message as plain readable text, not a status code or raw JSON', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ detail: 'O arquivo excede o limite de 10 MB.', code: 'image_too_large' }, 422))
    vi.stubGlobal('fetch', fetchMock)
    renderForm()

    selectFile(screen.getByLabelText('Foto'), makeFile())
    fireEvent.click(screen.getByRole('button', { name: /enviar foto/i }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('O arquivo excede o limite de 10 MB.')
    expect(alert).not.toHaveTextContent('422')
    expect(alert).not.toHaveTextContent('{')
  })
})

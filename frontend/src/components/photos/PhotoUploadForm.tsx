import { useEffect, useId, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useUploadPhoto } from '../../hooks/useUploadPhoto.ts'
import { ApiError } from '../../services/apiClient.ts'

interface PhotoUploadFormProps {
  slug: string
}

// The genuinely generic "network failed" case — an `ApiError` (the only
// error type `apiFetch` ever rejects with, per apiClient.ts) always already
// carries a readable `message`, so this only shows up if something other
// than the network call itself throws.
const FALLBACK_ERROR_MESSAGE = 'Não foi possível enviar a foto. Tente novamente.'

/** The form described by issue #29: someone standing at the canteiro,
 * one-handed, submitting a photo in a few taps. Kept to exactly the fields
 * the issue asks for — no multi-step flow, nothing optional made
 * required — since every extra field/step works against that goal. */
function PhotoUploadForm({ slug }: PhotoUploadFormProps) {
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [contributorName, setContributorName] = useState('')
  const [description, setDescription] = useState('')
  const [shareLocation, setShareLocation] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // One `useId()` call, suffixed per field, instead of five separate
  // calls — same guarantee (stable, SSR-safe, unique per instance).
  const formId = useId()
  const fileFieldId = `${formId}-file`
  const nameFieldId = `${formId}-name`
  const descriptionFieldId = `${formId}-description`
  const shareLocationFieldId = `${formId}-share-location`
  const shareLocationHintId = `${formId}-share-location-hint`

  const { mutate, isPending, isError, error, reset } = useUploadPhoto(slug)

  // Revoked on every file change and on unmount — an object URL otherwise
  // keeps its backing blob alive in memory for the page's whole lifetime.
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
    }
    setFile(selected)
    setPreviewUrl(selected ? URL.createObjectURL(selected) : null)
    if (isError) {
      reset()
    }
  }

  function clearForm() {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
    }
    setFile(null)
    setPreviewUrl(null)
    setContributorName('')
    setDescription('')
    setShareLocation(false)
    // Uncontrolled by design (`<input type="file">` can't take a `value`),
    // so clearing the visible filename after a successful submit needs a
    // direct reset alongside the `file` state above.
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!file) {
      return
    }

    mutate(
      {
        file,
        contributorName: contributorName.trim() || undefined,
        description: description.trim() || undefined,
        shareLocation,
      },
      { onSuccess: clearForm },
    )
  }

  const errorMessage = isError
    ? error instanceof ApiError
      ? error.message
      : FALLBACK_ERROR_MESSAGE
    : null

  return (
    <form onSubmit={handleSubmit} aria-label="Enviar foto" className="mt-6 flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor={fileFieldId} className="text-sm font-semibold text-slate-700">
          Foto
        </label>
        <input
          ref={fileInputRef}
          id={fileFieldId}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleFileChange}
          className="text-sm text-slate-600"
        />
      </div>

      {previewUrl && (
        <img
          src={previewUrl}
          alt="Pré-visualização da foto selecionada"
          className="h-48 w-full rounded-lg object-cover"
        />
      )}

      <div className="flex flex-col gap-1">
        <label htmlFor={nameFieldId} className="text-sm font-semibold text-slate-700">
          Seu nome (opcional)
        </label>
        <input
          id={nameFieldId}
          type="text"
          value={contributorName}
          onChange={(event) => setContributorName(event.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor={descriptionFieldId} className="text-sm font-semibold text-slate-700">
          Observação (opcional)
        </label>
        <textarea
          id={descriptionFieldId}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={2}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      <div className="flex items-start gap-2">
        <input
          id={shareLocationFieldId}
          type="checkbox"
          checked={shareLocation}
          onChange={(event) => setShareLocation(event.target.checked)}
          aria-describedby={shareLocationHintId}
          className="mt-1"
        />
        <div className="flex flex-col gap-0.5">
          <label htmlFor={shareLocationFieldId} className="text-sm font-semibold text-slate-700">
            Compartilhar onde esta foto foi tirada
          </label>
          <p id={shareLocationHintId} className="text-xs text-slate-500">
            Isso guarda a localização registrada na foto. Deixe desmarcado se não quiser.
          </p>
        </div>
      </div>

      <button
        type="submit"
        disabled={!file || isPending}
        className="rounded-lg bg-emerald-600 px-6 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500"
      >
        {isPending ? 'Enviando...' : 'Enviar foto'}
      </button>

      {errorMessage && (
        <p role="alert" className="text-sm text-red-600">
          {errorMessage}
        </p>
      )}
    </form>
  )
}

export default PhotoUploadForm

import { useEffect, useId, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useUploadPhoto } from '../../hooks/useUploadPhoto.ts'
import { ApiError } from '../../services/apiClient.ts'

interface PhotoUploadFormProps {
  plantingId: string
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
function PhotoUploadForm({ plantingId }: PhotoUploadFormProps) {
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [contributorName, setContributorName] = useState('')
  const [description, setDescription] = useState('')
  const [shareLocation, setShareLocation] = useState(false)
  // Issue #38 (LGPD, docs/architecture.md §9): checkbox A, always visible,
  // unchecked by default. Checkbox B only renders once A is checked (see
  // JSX below) and is required to submit while A stays checked — the
  // `consentValidationMessage` computed further down enforces that.
  const [includesIdentifiablePerson, setIncludesIdentifiablePerson] = useState(false)
  const [identifiablePersonConsentConfirmed, setIdentifiablePersonConsentConfirmed] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // One `useId()` call, suffixed per field, instead of five separate
  // calls — same guarantee (stable, SSR-safe, unique per instance).
  const formId = useId()
  const fileFieldId = `${formId}-file`
  const nameFieldId = `${formId}-name`
  const descriptionFieldId = `${formId}-description`
  const shareLocationFieldId = `${formId}-share-location`
  const shareLocationHintId = `${formId}-share-location-hint`
  const identifiablePersonFieldId = `${formId}-identifiable-person`
  const identifiablePersonConsentFieldId = `${formId}-identifiable-person-consent`

  const { mutate, isPending, isError, error, reset } = useUploadPhoto(plantingId)

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
    setIncludesIdentifiablePerson(false)
    setIdentifiablePersonConsentConfirmed(false)
    // Uncontrolled by design (`<input type="file">` can't take a `value`),
    // so clearing the visible filename after a successful submit needs a
    // direct reset alongside the `file` state above.
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  function handleIncludesIdentifiablePersonChange(event: ChangeEvent<HTMLInputElement>) {
    const checked = event.target.checked
    setIncludesIdentifiablePerson(checked)
    // Unchecking A hides checkbox B (JSX below) — also reset its value, so
    // re-checking A later never silently carries over a stale confirmation
    // the person never actually gave for *this* photo.
    if (!checked) {
      setIdentifiablePersonConsentConfirmed(false)
    }
  }

  // Issue #38: checkbox A checked without checkbox B blocks submission,
  // with a message following this form's own error pattern (the
  // `role="alert"` paragraph also used for the backend error below) — there
  // was no other client-side validation message pattern already in this
  // form to match instead.
  const consentValidationMessage =
    includesIdentifiablePerson && !identifiablePersonConsentConfirmed
      ? 'Marque a confirmação de autorização do responsável para enviar esta foto, ou desmarque a opção acima.'
      : null

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!file || consentValidationMessage) {
      return
    }

    mutate(
      {
        file,
        contributorName: contributorName.trim() || undefined,
        description: description.trim() || undefined,
        shareLocation,
        includesIdentifiablePerson,
        identifiablePersonConsentConfirmed,
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
        {/* The native `<input type="file">` renders its own tiny "Escolher
            arquivo" button (issue #34: measured ~20px tall) that can't be
            resized directly by CSS in every browser. Visually hidden
            (`sr-only`, not `hidden` — it must stay in the tab order and
            keep receiving the `change` event) in favor of this `<label>`
            styled as a proper 44px button; a `<label for>` opens the same
            native file picker as a real click on the input. */}
        <label
          htmlFor={fileFieldId}
          className="flex min-h-11 w-fit cursor-pointer items-center rounded-md border border-emerald-600 px-4 text-sm font-semibold text-emerald-700"
        >
          {file ? 'Trocar foto' : 'Escolher foto'}
        </label>
        <input
          ref={fileInputRef}
          id={fileFieldId}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleFileChange}
          className="sr-only"
        />
        {file && <p className="text-sm text-slate-600">{file.name}</p>}
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
        {/* `py-3` (issue #34): `py-2` alone measured ~38px tall. */}
        <input
          id={nameFieldId}
          type="text"
          value={contributorName}
          onChange={(event) => setContributorName(event.target.value)}
          className="rounded-md border border-slate-300 px-3 py-3 text-sm"
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

      {/* A native checkbox renders at ~13px regardless of CSS (issue #34) —
          rather than fighting browser-native checkbox rendering, the whole
          row is one `<label>` (min-h-11), so tapping the text hits the same
          44px target as tapping the checkbox itself; `htmlFor` here is
          redundant with the label wrapping its control, kept for clarity. */}
      <label htmlFor={shareLocationFieldId} className="flex min-h-11 items-start gap-2 py-1">
        <input
          id={shareLocationFieldId}
          type="checkbox"
          checked={shareLocation}
          onChange={(event) => setShareLocation(event.target.checked)}
          aria-describedby={shareLocationHintId}
          className="mt-1"
        />
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-semibold text-slate-700">
            Compartilhar onde esta foto foi tirada
          </span>
          <p id={shareLocationHintId} className="text-xs text-slate-500">
            Isso guarda a localização registrada na foto. Deixe desmarcado se não quiser.
          </p>
        </div>
      </label>

      {/* Issue #38 (LGPD, docs/architecture.md §9): checkbox A, always
          visible, unchecked by default — self-declared, like
          `contributor_name` is: nothing here verifies the claim, only
          records that the uploader made it. */}
      <label htmlFor={identifiablePersonFieldId} className="flex min-h-11 items-start gap-2 py-1">
        <input
          id={identifiablePersonFieldId}
          type="checkbox"
          checked={includesIdentifiablePerson}
          onChange={handleIncludesIdentifiablePersonChange}
          className="mt-1"
        />
        <span className="text-sm font-semibold text-slate-700">
          Esta foto inclui uma ou mais pessoas identificáveis (ex.: rosto de alguém aparece na foto)
        </span>
      </label>

      {/* Checkbox B: only rendered once A is checked, and required to
          submit while A stays checked (`consentValidationMessage` below). */}
      {includesIdentifiablePerson && (
        <label
          htmlFor={identifiablePersonConsentFieldId}
          className="flex min-h-11 items-start gap-2 py-1 pl-6"
        >
          <input
            id={identifiablePersonConsentFieldId}
            type="checkbox"
            checked={identifiablePersonConsentConfirmed}
            onChange={(event) => setIdentifiablePersonConsentConfirmed(event.target.checked)}
            className="mt-1"
          />
          <span className="text-sm font-semibold text-slate-700">
            Confirmo que tenho autorização do responsável para publicar esta foto com pessoa(s)
            identificável(is).
          </span>
        </label>
      )}

      {consentValidationMessage && (
        <p role="alert" className="text-sm text-red-600">
          {consentValidationMessage}
        </p>
      )}

      {/* `bg-emerald-700`, not `-600` (issue #35): white text on `-600`
          measures 3.77:1, under WCAG AA's 4.5:1 floor for this
          normal-weight text — `-700` clears it at 5.48:1. Disabled state is
          exempt (an inoperable control isn't a contrast requirement). */}
      <button
        type="submit"
        disabled={!file || isPending || Boolean(consentValidationMessage)}
        className="rounded-lg bg-emerald-700 px-6 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500"
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

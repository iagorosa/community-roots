import { useParams } from 'react-router'

/**
 * Placeholder for issue #14 (routing only). The real region detail page —
 * timeline, mini-map, photo upload — is issue #23.
 */
function RegionPage() {
  const { slug } = useParams<{ slug: string }>()

  return (
    <div className="flex flex-1 items-center justify-center bg-slate-50">
      <p className="text-slate-700">
        Canteiro: <strong>{slug}</strong>
      </p>
    </div>
  )
}

export default RegionPage

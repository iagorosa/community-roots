interface EmptyStateProps {
  message: string
}

/** A successful request that came back with zero results — distinct from
 * `ErrorState`, which is for a failed request. `role="status"` (polite),
 * matching `LoadingState`: an empty result isn't an urgent interruption. */
function EmptyState({ message }: EmptyStateProps) {
  return (
    <div className="flex flex-1 items-center justify-center" role="status">
      <p className="text-slate-500">{message}</p>
    </div>
  )
}

export default EmptyState

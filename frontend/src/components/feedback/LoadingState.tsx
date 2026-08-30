interface LoadingStateProps {
  message: string
}

/** Announced to screen readers via `role="status"` (a polite live region) —
 * appropriate for progress that isn't urgent, unlike `ErrorState`'s
 * `role="alert"`. Used wherever a page is waiting on `services/*` data
 * (docs/architecture.md §8). */
function LoadingState({ message }: LoadingStateProps) {
  return (
    <div className="flex flex-1 items-center justify-center" role="status">
      <p className="text-slate-500">{message}</p>
    </div>
  )
}

export default LoadingState

interface ErrorStateProps {
  message: string
}

/** Announced to screen readers via `role="alert"` (an assertive live
 * region) — a failed request deserves immediate attention, unlike
 * `LoadingState`'s polite `role="status"`. Renders instead of the page's
 * normal content whenever a `services/*` call fails, so a dead backend
 * shows a readable message rather than a blank page (issue #18). */
function ErrorState({ message }: ErrorStateProps) {
  return (
    <div className="flex flex-1 items-center justify-center" role="alert">
      <p className="text-red-600">{message}</p>
    </div>
  )
}

export default ErrorState

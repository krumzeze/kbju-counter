import { tr } from "../lib/i18n";

export function Spinner({ label = tr("Загрузка…", "Loading…") }: { label?: string }) {
  return (
    <div className="state">
      <div className="spinner" aria-hidden />
      <span className="muted">{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state">
      <p>{message}</p>
      {onRetry && (
        <button className="btn" onClick={onRetry}>
          {tr("Повторить", "Retry")}
        </button>
      )}
    </div>
  );
}

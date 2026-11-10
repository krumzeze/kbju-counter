import { Component, type ErrorInfo, type ReactNode } from "react";
import { tr } from "../lib/i18n";
import { report } from "../lib/errorReporting";

export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown, info: ErrorInfo) {
    report(error, info.componentStack ?? undefined);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="state crash">
        <h2>{tr("Что-то сломалось", "Something broke")}</h2>
        <p className="muted">
          {tr("Мы уже получили отчёт об ошибке. Попробуйте открыть заново.", "We've received an error report. Please try reloading.")}
        </p>
        <button className="btn" onClick={() => location.reload()}>
          {tr("Перезагрузить", "Reload")}
        </button>
      </div>
    );
  }
}

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import { Logo } from "../components/Logo";
import type { Lang } from "../lib/i18n";

export function LanguagePicker() {
  const client = useQueryClient();
  const choose = useMutation({
    mutationFn: (lang: Lang) => api.setLanguage(lang),
    onSuccess: (me) => client.setQueryData(["me"], me),
  });

  return (
    <div className="page center">
      <div className="card paywall">
        <Logo size={88} />
        <h1>Выбери язык · Choose your language</h1>
        <div className="stack">
          <button className="btn btn-block" disabled={choose.isPending} onClick={() => choose.mutate("ru")}>
            🇷🇺 Русский
          </button>
          <button className="btn btn-block" disabled={choose.isPending} onClick={() => choose.mutate("en")}>
            🇬🇧 English
          </button>
        </div>
        {choose.isError && <p className="error">{errorMessage(choose.error)}</p>}
      </div>
    </div>
  );
}

import { useMutation } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import { tr } from "../lib/i18n";
import { haptic, isMiniApp } from "../lib/telegram";
import { Icon } from "./Icon";

export function DayCardLink() {
  const send = useMutation({
    mutationFn: api.sendDayCard,
    onSuccess: () => haptic("success"),
    onError: () => haptic("error"),
  });
  if (!isMiniApp) return null;

  const label = send.isSuccess
    ? tr("Карточка в чате с ботом и закреплена", "The card is pinned in the bot chat")
    : send.isError
      ? errorMessage(send.error)
      : tr("Карточка дня в чате с ботом", "Day card in the bot chat");
  return (
    <button
      type="button"
      className="card premium-note home-screen-link"
      disabled={send.isPending}
      onClick={() => send.mutate()}
    >
      <span>
        {label}
        {!send.isSuccess && !send.isError && (
          <span className="muted small day-card-hint">
            {tr(
              "Калории, БЖУ, вода и быстрые кнопки прямо в Telegram. Обновляется сама.",
              "Calories, macros, water and quick buttons right in Telegram. Updates itself.",
            )}
          </span>
        )}
      </span>
      <Icon name="chevron" />
    </button>
  );
}

import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Me, Recipe, RecipeItem } from "../api/types";
import { Icon } from "../components/Icon";
import { IngredientSheet } from "../components/IngredientSheet";
import { ErrorState, Spinner } from "../components/States";
import { round } from "../lib/format";
import { tr } from "../lib/i18n";
import { prepareImage } from "../lib/image";
import { useInvalidate } from "../lib/queries";
import { RECIPE_KEYS, portionsWord, scaleMacros, statusLabel, sumItems, useRecipe } from "../lib/recipes";
import { haptic } from "../lib/telegram";

interface Photo {
  key: string;
  url: string | null;
}

interface Step {
  text: string;
  photo: Photo | null;
}

export function RecipeEdit({ me }: { me: Me }) {
  const id = useParams().id;
  const recipe = useRecipe(Number(id));
  if (!id) return <RecipeForm me={me} />;
  if (recipe.isPending) return <Spinner />;
  if (recipe.error) return <ErrorState message={errorMessage(recipe.error)} onRetry={() => recipe.refetch()} />;
  return <RecipeForm me={me} recipe={recipe.data} key={recipe.data.id} />;
}

function usePhotoUpload(onDone: (photo: Photo) => void) {
  return useMutation({
    mutationFn: async (file: File) => api.uploadRecipePhoto(await prepareImage(file)),
    onSuccess: (r) => {
      haptic("success");
      onDone({ key: r.photo, url: r.photo_url });
    },
    onError: () => haptic("error"),
  });
}

function PhotoPicker({
  photo,
  label,
  onChange,
  big = false,
}: {
  photo: Photo | null;
  label: string;
  onChange: (photo: Photo | null) => void;
  big?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const upload = usePhotoUpload(onChange);
  return (
    <div className={big ? "photo-picker big" : "photo-picker"}>
      {photo ? (
        <span className="photo-picked">
          {photo.url ? <img src={photo.url} alt="" /> : <span className="recipe-photo-empty" />}
          <button type="button" className="photo-remove" aria-label={tr("Убрать фото", "Remove photo")} onClick={() => onChange(null)}>
            ×
          </button>
        </span>
      ) : (
        <button type="button" className="photo-add" disabled={upload.isPending} onClick={() => input.current?.click()}>
          {big && <Icon name="camera" size={28} />}
          {upload.isPending ? tr("Загружаю…", "Uploading…") : label}
        </button>
      )}
      <input
        ref={input}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) upload.mutate(file);
        }}
      />
      {upload.isError && <p className="error small">{errorMessage(upload.error)}</p>}
    </div>
  );
}

function RecipeForm({ me, recipe }: { me: Me; recipe?: Recipe }) {
  const navigate = useNavigate();
  const invalidate = useInvalidate();
  const [title, setTitle] = useState(recipe?.title ?? "");
  const [portions, setPortions] = useState(recipe?.portions ?? 2);
  const [cooked, setCooked] = useState(recipe?.cooked_grams ? String(Math.round(recipe.cooked_grams)) : "");
  const [items, setItems] = useState<RecipeItem[]>(recipe?.items ?? []);
  const [steps, setSteps] = useState<Step[]>(
    recipe?.steps.map((s) => ({ text: s.text, photo: s.photo ? { key: s.photo, url: s.photo_url } : null })) ?? [],
  );
  const [photo, setPhoto] = useState<Photo | null>(
    recipe?.photo ? { key: recipe.photo, url: recipe.photo_url } : null,
  );
  const [adding, setAdding] = useState(false);

  const save = useMutation({
    mutationFn: () => {
      const body = {
        title: title.trim(),
        portions,
        cooked_grams: Number(cooked) > 0 ? Number(cooked) : null,
        items,
        steps: steps
          .filter((s) => s.text.trim())
          .map((s) => ({ text: s.text.trim(), photo: s.photo?.key ?? null })),
        photo: photo?.key ?? null,
      };
      return recipe ? api.updateRecipe(recipe.id, body) : api.createRecipe(body);
    },
    onSuccess: async (saved) => {
      haptic("success");
      await invalidate(...RECIPE_KEYS);
      navigate(`/recipes/${saved.id}`, { replace: true });
    },
    onError: () => haptic("error"),
  });

  const total = sumItems(items);
  const perPortion = scaleMacros(total, 1 / portions);
  const raw = items.reduce((s, i) => s + i.grams, 0);
  const valid = title.trim().length > 0 && items.length > 0;
  const setStep = (n: number, patch: Partial<Step>) => setSteps(steps.map((s, i) => (i === n ? { ...s, ...patch } : s)));
  const resize = (n: number, grams: number) =>
    setItems(
      items.map((it, i) => {
        if (i !== n || it.grams <= 0 || grams <= 0) return it;
        const k = grams / it.grams;
        return { ...it, grams, kcal: it.kcal * k, protein: it.protein * k, fat: it.fat * k, carbs: it.carbs * k };
      }),
    );

  return (
    <div className="page recipe-edit">
      <header className="recipes-head">
        <h1>{recipe ? tr("Мой рецепт", "My recipe") : tr("Новый рецепт", "New recipe")}</h1>
        {recipe && <span className={`recipe-status ${recipe.status}`}>{statusLabel(recipe.status)}</span>}
      </header>
      {recipe?.forked_from && (
        <p className="card recipe-note accent">
          {tr("Это твоя копия рецепта", "Your copy of")} «{recipe.forked_from.title}».{" "}
          {tr("Оригинал не изменится, в избранном видны обе версии.", "The original won't change.")}
        </p>
      )}
      {recipe?.status === "public" && !me.is_admin && (
        <p className="card recipe-note pending small">
          {tr(
            "Рецепт опубликован. После сохранения изменений он снова уйдёт на проверку.",
            "This recipe is published. Saving changes sends it back for review.",
          )}
        </p>
      )}

      <label className="field">
        <span>{tr("Название", "Name")}</span>
        <input
          className="input"
          maxLength={255}
          value={title}
          placeholder={tr("Например: курица с булгуром", "E.g. chicken with bulgur")}
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>

      <div className="fields-2">
        <div className="card field-card">
          <span className="muted small">{tr("Порций", "Servings")}</span>
          <span className="mini-stepper">
            <button type="button" aria-label={tr("Меньше порций", "Fewer servings")} onClick={() => setPortions(Math.max(1, portions - 1))}>
              −
            </button>
            <b>{portions}</b>
            <button type="button" aria-label={tr("Больше порций", "More servings")} onClick={() => setPortions(Math.min(50, portions + 1))}>
              +
            </button>
          </span>
        </div>
        <label className="card field-card">
          <span className="muted small">{tr("Вес готового блюда, г", "Cooked weight, g")}</span>
          <input
            className="bare-input"
            inputMode="numeric"
            placeholder={raw ? String(Math.round(raw)) : "1200"}
            value={cooked}
            onChange={(e) => setCooked(e.target.value.replace(/\D/g, ""))}
          />
        </label>
      </div>
      <p className="muted small">
        {tr(
          "Вес готового нужен, чтобы записывать в граммах: вода в крупе и мясе меняет вес. Не знаешь, оставь пустым, возьмём сумму сырых продуктов.",
          "The cooked weight lets you log in grams, since cooking changes weight. Leave it empty to use the raw total.",
        )}
      </p>

      <section className="card">
        <div className="section-head">
          <h2>{tr("Продукты", "Ingredients")}</h2>
          <span className="muted small">{tr("в сыром виде", "raw")}</span>
        </div>
        {items.length === 0 && <p className="muted small">{tr("Пока пусто.", "Nothing yet.")}</p>}
        <ul className="ingredient-list editable">
          {items.map((i, n) => (
            <li key={`${n}-${i.name}-${Math.round(i.grams)}`}>
              <span>
                {i.name}
                <span className="muted small block">
                  {round(i.kcal)} {tr("ккал", "kcal")} · {tr("Б", "P")} {round(i.protein)} · {tr("Ж", "F")} {round(i.fat)} · {tr("У", "C")}{" "}
                  {round(i.carbs)}
                </span>
              </span>
              <span className="grams-input">
                <input
                  className="bare-input"
                  inputMode="numeric"
                  aria-label={tr("Граммы", "Grams")}
                  defaultValue={Math.round(i.grams)}
                  onBlur={(e) => {
                    const g = Number(e.target.value.replace(",", "."));
                    if (g > 0 && g <= 10000) resize(n, g);
                    else e.target.value = String(Math.round(i.grams));
                  }}
                />
                {tr("г", "g")}
              </span>
              <button type="button" className="icon-btn small" aria-label={tr("Удалить продукт", "Remove ingredient")} onClick={() => setItems(items.filter((_, j) => j !== n))}>
                ×
              </button>
            </li>
          ))}
        </ul>
        <button type="button" className="btn btn-block dashed" onClick={() => setAdding(true)}>
          + {tr("Добавить продукты", "Add ingredients")}
        </button>
      </section>

      {items.length > 0 && (
        <div className="card hero recipe-total">
          <span>
            <b>{round(perPortion.kcal)}</b> <span className="hero-muted">{tr("ккал на порцию", "kcal per serving")}</span>
          </span>
          <span className="small">
            {tr("Б", "P")} {round(perPortion.protein)} · {tr("Ж", "F")} {round(perPortion.fat)} · {tr("У", "C")} {round(perPortion.carbs)}
          </span>
        </div>
      )}

      <section className="card stack">
        <h2>{tr("Фото блюда", "Dish photo")}</h2>
        <PhotoPicker big photo={photo} onChange={setPhoto} label={tr("Добавить фото", "Add a photo")} />
        <p className="muted small">{tr("Для себя по желанию, для публикации обязательно.", "Optional for you, required to publish.")}</p>
      </section>

      <section className="card stack">
        <h2>{tr("Как готовить", "Method")}</h2>
        {steps.map((s, n) => (
          <div key={n} className="step-edit">
            <b className="step-num">{n + 1}</b>
            <span className="stack-tight grow">
              <textarea
                className="input textarea"
                rows={2}
                maxLength={2000}
                aria-label={`${tr("Шаг", "Step")} ${n + 1}`}
                value={s.text}
                onChange={(e) => setStep(n, { text: e.target.value })}
              />
              <span className="step-tools">
                <PhotoPicker photo={s.photo} onChange={(p) => setStep(n, { photo: p })} label={tr("+ Фото к шагу, по желанию", "+ Step photo, optional")} />
                <button type="button" className="btn-ghost inline" onClick={() => setSteps(steps.filter((_, j) => j !== n))}>
                  {tr("Удалить шаг", "Remove step")}
                </button>
              </span>
            </span>
          </div>
        ))}
        <button type="button" className="btn btn-block dashed" onClick={() => setSteps([...steps, { text: "", photo: null }])}>
          + {tr("Шаг", "Step")}
        </button>
      </section>

      {save.isError && <p className="error">{errorMessage(save.error)}</p>}
      <button className="btn btn-accent btn-cta" disabled={!valid || save.isPending} onClick={() => save.mutate()}>
        {recipe ? tr("Сохранить", "Save") : tr("Сохранить для себя", "Save for myself")}
      </button>
      <p className="muted small center">
        {portions} {portionsWord(portions)} · {round(raw)} {tr("г сырых продуктов", "g raw")}
      </p>

      {adding && (
        <IngredientSheet
          features={me.features}
          onClose={() => setAdding(false)}
          onAdd={(added) => {
            setItems([...items, ...added]);
            setAdding(false);
          }}
        />
      )}
    </div>
  );
}

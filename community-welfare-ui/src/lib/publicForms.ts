/**
 * Public Embassy forms library for the React site.
 *
 * The backend owns the data: staff publish forms from /admin/forms and this
 * page renders whatever the read-only public API returns. Nothing about the
 * catalogue is hard-coded here — categories, ordering and copy all come from
 * the payload, so staff never need a developer to change the page.
 *
 * Pure functions only; fetch and storage are injected by the caller so the
 * filtering rules stay testable without a DOM (see scripts/publicFormsSmoke.ts).
 *
 * Safety: every field below is staff-entered and is rendered exclusively as
 * React text nodes — never dangerouslySetInnerHTML.
 */

export const PUBLIC_FORMS_ENDPOINT = "/api/public/forms";

/** The backend can cold-start; give up rather than hanging the page forever. */
export const FORMS_FETCH_TIMEOUT_MS = 12000;

/** Sentinel for "no category filter". Never a real slug (slugs are [a-z0-9-]). */
export const ALL_CATEGORIES = "all";

export interface PublicForm {
  id: number;
  title: string;
  titleUr: string;
  description: string;
  descriptionUr: string;
  category: string;
  categorySlug: string;
  language: string;
  languageLabel: string;
  fileType: string;
  fileSize: number;
  fileSizeDisplay: string;
  versionLabel: string;
  effectiveDate: string;
  updatedDisplay: string;
  updatedAt: string;
  featured: boolean;
  downloadUrl: string;
}

export interface FormCategory {
  slug: string;
  label: string;
  labelUr: string;
}

export interface PublicFormsResponse {
  success?: boolean;
  forms?: unknown;
  categories?: unknown;
  updatedDisplay?: unknown;
}

export interface PublicFormsData {
  forms: PublicForm[];
  categories: FormCategory[];
  updatedDisplay: string;
}

export const EMPTY_FORMS_DATA: PublicFormsData = {
  forms: [],
  categories: [],
  updatedDisplay: "",
};

function str(value: unknown) {
  return typeof value === "string" ? value : "";
}

function num(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

/**
 * Coerce one API row into a PublicForm, or null when it is unusable.
 *
 * A form with no id, no title or no download URL cannot be rendered usefully,
 * so it is dropped rather than shown as an empty card.
 */
export function normalizeForm(raw: unknown): PublicForm | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const id = num(row.id);
  const title = str(row.title).trim();
  const downloadUrl = str(row.downloadUrl).trim();
  if (!id || !title || !downloadUrl) return null;
  return {
    id,
    title,
    titleUr: str(row.titleUr),
    description: str(row.description),
    descriptionUr: str(row.descriptionUr),
    category: str(row.category) || "Other",
    categorySlug: str(row.categorySlug) || "other",
    language: str(row.language) || "en",
    languageLabel: str(row.languageLabel),
    fileType: str(row.fileType) || "PDF",
    fileSize: num(row.fileSize),
    fileSizeDisplay: str(row.fileSizeDisplay),
    versionLabel: str(row.versionLabel),
    effectiveDate: str(row.effectiveDate),
    updatedDisplay: str(row.updatedDisplay),
    updatedAt: str(row.updatedAt),
    featured: row.featured === true,
    downloadUrl,
  };
}

export function normalizeCategory(raw: unknown): FormCategory | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const slug = str(row.slug).trim();
  const label = str(row.label).trim();
  if (!slug || !label) return null;
  return { slug, label, labelUr: str(row.labelUr) };
}

/** Whole-response coercion. A malformed body yields empty data, never a throw. */
export function normalizeFormsResponse(raw: PublicFormsResponse | null | undefined): PublicFormsData {
  if (!raw || typeof raw !== "object") return EMPTY_FORMS_DATA;
  const forms = Array.isArray(raw.forms)
    ? raw.forms.map(normalizeForm).filter((form): form is PublicForm => form !== null)
    : [];
  const categories = Array.isArray(raw.categories)
    ? raw.categories.map(normalizeCategory).filter((cat): cat is FormCategory => cat !== null)
    : [];
  return { forms, categories, updatedDisplay: str(raw.updatedDisplay) };
}

/**
 * Case-insensitive substring match across the fields a citizen would type.
 *
 * Urdu title is included so an Urdu-speaking visitor can search in Urdu; the
 * description is included so "correction" finds the NICOP modification form.
 */
export function matchesQuery(form: PublicForm, query: string) {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return [form.title, form.titleUr, form.description, form.category, form.versionLabel]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
    .includes(needle);
}

export function filterForms(forms: PublicForm[], query: string, category: string) {
  const slug = category || ALL_CATEGORIES;
  return forms.filter((form) => {
    if (slug !== ALL_CATEGORIES && form.categorySlug !== slug) return false;
    return matchesQuery(form, query);
  });
}

/**
 * Resolve ?category=… against the categories the API actually returned.
 *
 * An unknown or absent slug falls back to "all" rather than rendering an empty
 * page — a stale bookmark should still show the library.
 */
export function categoryFromSearch(search: string, categories: FormCategory[]) {
  let value = "";
  try {
    value = new URLSearchParams(search || "").get("category") || "";
  } catch (_err) {
    return ALL_CATEGORIES;
  }
  if (!value) return ALL_CATEGORIES;
  return categories.some((cat) => cat.slug === value) ? value : ALL_CATEGORIES;
}

/** "PDF · English/Urdu · 240 KB · Updated 10 Aug 2026" */
export function formMetaLine(form: PublicForm) {
  return [
    form.fileType || "PDF",
    form.languageLabel,
    form.fileSizeDisplay,
    form.updatedDisplay ? `Updated ${form.updatedDisplay}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

/** Screen-reader label: says what the link does and what it will cost to fetch. */
export function downloadAriaLabel(form: PublicForm) {
  const size = form.fileSizeDisplay ? `, ${form.fileSizeDisplay}` : "";
  return `Download ${form.title} (${form.fileType || "PDF"}${size})`;
}

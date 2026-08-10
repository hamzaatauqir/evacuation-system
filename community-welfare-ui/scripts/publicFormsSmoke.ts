/**
 * Node smoke test for the public forms library logic.
 *
 * Exercises the pure helpers in src/lib/publicForms.ts without a DOM or a
 * network: response coercion, search matching, category filtering, and URL
 * parameter resolution. Run with:
 *   node --experimental-strip-types scripts/publicFormsSmoke.ts
 */
import {
  type PublicForm,
  ALL_CATEGORIES,
  EMPTY_FORMS_DATA,
  categoryFromSearch,
  downloadAriaLabel,
  filterForms,
  formMetaLine,
  matchesQuery,
  normalizeForm,
  normalizeFormsResponse,
} from "../src/lib/publicForms.ts";

let passes = 0;
const failures: string[] = [];

function check(name: string, ok: boolean, detail = "") {
  if (ok) {
    passes += 1;
    console.log(`  PASS  ${name}`);
  } else {
    failures.push(name);
    console.log(`  FAIL  ${name} ${detail}`);
  }
}

function makeForm(over: Partial<PublicForm> = {}): PublicForm {
  return {
    id: 1,
    title: "NICOP Modification Form",
    titleUr: "نادرا ترمیمی فارم",
    description: "For modification or correction of NICOP information.",
    descriptionUr: "",
    category: "NADRA",
    categorySlug: "nadra",
    language: "en+ur",
    languageLabel: "English/Urdu",
    fileType: "PDF",
    fileSize: 245760,
    fileSizeDisplay: "240 KB",
    versionLabel: "Aug 2026 revision",
    effectiveDate: "2026-08-01",
    updatedDisplay: "10 Aug 2026",
    updatedAt: "2026-08-10 09:00:00",
    featured: false,
    downloadUrl: "https://evacuation-system.onrender.com/forms/download/1",
    ...over,
  };
}

console.log("Public forms library logic smoke\n");

// ── Response coercion ────────────────────────────────────────────
console.log("1. Response coercion");
check("null response yields empty data",
  JSON.stringify(normalizeFormsResponse(null)) === JSON.stringify(EMPTY_FORMS_DATA));
check("garbage response yields empty data",
  JSON.stringify(normalizeFormsResponse({ forms: "nope", categories: 7 } as never))
    === JSON.stringify(EMPTY_FORMS_DATA));
check("form without an id is dropped", normalizeForm({ title: "x", downloadUrl: "y" }) === null);
check("form without a title is dropped", normalizeForm({ id: 1, downloadUrl: "y" }) === null);
check("form without a download URL is dropped", normalizeForm({ id: 1, title: "x" }) === null);
check("valid form is kept",
  normalizeForm({ id: 3, title: "T", downloadUrl: "https://x/forms/download/3" })?.id === 3);
check("missing category defaults to Other",
  normalizeForm({ id: 3, title: "T", downloadUrl: "u" })?.category === "Other");
check("featured coerces to a real boolean",
  normalizeForm({ id: 3, title: "T", downloadUrl: "u", featured: "yes" })?.featured === false);

const mixed = normalizeFormsResponse({
  success: true,
  forms: [makeForm({ id: 1 }), { id: 0, title: "bad" }, makeForm({ id: 2, title: "Passport Renewal", categorySlug: "passport", category: "Passport" })],
  categories: [{ slug: "nadra", label: "NADRA" }, { slug: "", label: "Broken" }],
  updatedDisplay: "10 Aug 2026",
});
check("unusable rows are filtered out", mixed.forms.length === 2, String(mixed.forms.length));
check("unusable categories are filtered out", mixed.categories.length === 1, String(mixed.categories.length));
check("updatedDisplay preserved", mixed.updatedDisplay === "10 Aug 2026");

// ── Search ───────────────────────────────────────────────────────
console.log("\n2. Search matching");
const form = makeForm();
check("empty query matches everything", matchesQuery(form, ""));
check("whitespace query matches everything", matchesQuery(form, "   "));
check("title match is case-insensitive", matchesQuery(form, "nicop"));
check("description is searched", matchesQuery(form, "correction"));
check("category is searched", matchesQuery(form, "nadra"));
check("version label is searched", matchesQuery(form, "aug 2026"));
check("Urdu title is searchable", matchesQuery(form, "نادرا"));
check("unrelated term does not match", !matchesQuery(form, "passport"));

// ── Filtering ────────────────────────────────────────────────────
console.log("\n3. Category filtering");
// Descriptions and version labels are overridden too: makeForm's defaults
// mention NICOP, which would otherwise make every row match a "nicop" query.
const forms = [
  makeForm({ id: 1, title: "NICOP Modification", categorySlug: "nadra", category: "NADRA",
    description: "Correct NICOP details.", titleUr: "", versionLabel: "" }),
  makeForm({ id: 2, title: "Passport Renewal", categorySlug: "passport", category: "Passport",
    description: "Renew an expiring passport.", titleUr: "", versionLabel: "" }),
  makeForm({ id: 3, title: "Attestation Request", categorySlug: "attestation", category: "Attestation",
    description: "Request document attestation.", titleUr: "", versionLabel: "" }),
];
check("all returns everything", filterForms(forms, "", ALL_CATEGORIES).length === 3);
check("empty category behaves as all", filterForms(forms, "", "").length === 3);
check("category narrows the list", filterForms(forms, "", "passport").length === 1);
check("category and query combine",
  filterForms(forms, "renewal", "passport").length === 1);
check("category and non-matching query yield nothing",
  filterForms(forms, "nicop", "passport").length === 0);
check("unknown category yields nothing", filterForms(forms, "", "no-such").length === 0);

// ── URL parameter ────────────────────────────────────────────────
console.log("\n4. Category from the URL");
const cats = [{ slug: "nadra", label: "NADRA", labelUr: "" }];
check("known slug is honoured", categoryFromSearch("?category=nadra", cats) === "nadra");
check("unknown slug falls back to all", categoryFromSearch("?category=bogus", cats) === ALL_CATEGORIES);
check("absent parameter falls back to all", categoryFromSearch("?x=1", cats) === ALL_CATEGORIES);
check("empty search falls back to all", categoryFromSearch("", cats) === ALL_CATEGORIES);
check("malformed search does not throw",
  categoryFromSearch("?%", cats) === ALL_CATEGORIES || true);

// ── Presentation strings ─────────────────────────────────────────
console.log("\n5. Presentation strings");
check("meta line joins the populated parts",
  formMetaLine(form) === "PDF · English/Urdu · 240 KB · Updated 10 Aug 2026", formMetaLine(form));
check("meta line omits blanks",
  formMetaLine(makeForm({ languageLabel: "", fileSizeDisplay: "", updatedDisplay: "" })) === "PDF",
  formMetaLine(makeForm({ languageLabel: "", fileSizeDisplay: "", updatedDisplay: "" })));
check("aria label names the form and size",
  downloadAriaLabel(form) === "Download NICOP Modification Form (PDF, 240 KB)",
  downloadAriaLabel(form));
check("aria label copes with an unknown size",
  downloadAriaLabel(makeForm({ fileSizeDisplay: "" })) === "Download NICOP Modification Form (PDF)");

console.log(`\nPassed: ${passes}   Failed: ${failures.length}`);
if (failures.length) {
  failures.forEach((name) => console.log(`  - ${name}`));
  process.exit(1);
}

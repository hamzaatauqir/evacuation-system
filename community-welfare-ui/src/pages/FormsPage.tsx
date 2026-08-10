import { useEffect, useMemo, useState } from "react";
import { PublicHeader } from "../components/PublicHeader";
import { Section, SecTitle } from "../components/Layout";
import { ContactCard } from "../components/ContactCard";
import { PageFooter } from "../components/PageFooter";
import { Icon } from "../components/Icon";
import { T } from "../lib/tokens";
import { buildApiUrl } from "../lib/api";
import {
  type PublicForm,
  type PublicFormsData,
  type PublicFormsResponse,
  ALL_CATEGORIES,
  EMPTY_FORMS_DATA,
  FORMS_FETCH_TIMEOUT_MS,
  PUBLIC_FORMS_ENDPOINT,
  categoryFromSearch,
  downloadAriaLabel,
  filterForms,
  formMetaLine,
  normalizeFormsResponse,
} from "../lib/publicForms";

type LoadState = "loading" | "ready" | "error";

function FormCard({ form }: { form: PublicForm }) {
  return (
    <article
      className="card-hover"
      style={{
        background: T.surface,
        borderRadius: 14,
        border: `1px solid ${T.borderLt}`,
        borderTop: `3px solid ${T.navy}`,
        boxShadow: "0 2px 8px rgba(0,33,71,.06)",
        padding: "22px 22px 20px",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: ".08em",
          textTransform: "uppercase",
          color: T.muted,
          marginBottom: 8,
        }}
      >
        {form.category}
      </div>

      <h2 style={{ fontSize: 15.5, fontWeight: 700, color: T.navy, lineHeight: 1.4, margin: "0 0 8px" }}>
        {form.title}
      </h2>

      {form.titleUr ? (
        <p dir="rtl" lang="ur" style={{ fontSize: 14, color: T.muted, margin: "0 0 8px", textAlign: "right" }}>
          {form.titleUr}
        </p>
      ) : null}

      {form.description ? (
        <p style={{ fontSize: 13, color: T.muted, lineHeight: 1.65, flex: 1, margin: "0 0 14px" }}>
          {form.description}
        </p>
      ) : (
        <div style={{ flex: 1 }} />
      )}

      <p style={{ fontSize: 12, color: T.mutedLt, margin: "0 0 14px", fontVariantNumeric: "tabular-nums" }}>
        {formMetaLine(form)}
      </p>

      {/*
        A plain anchor, deliberately. The download route sits outside /api/ and
        carries no CORS headers, so it must be reached by top-level navigation;
        a fetch() from this origin would be blocked by the browser.
      */}
      <a
        href={form.downloadUrl}
        rel="noopener"
        aria-label={downloadAriaLabel(form)}
        style={{
          display: "block",
          textAlign: "center",
          padding: "11px 14px",
          borderRadius: 9,
          background: T.green,
          border: `1px solid ${T.green}`,
          color: "#fff",
          fontWeight: 700,
          fontSize: 13.5,
          textDecoration: "none",
        }}
      >
        Download Form
      </a>
    </article>
  );
}

export function FormsPage() {
  const [data, setData] = useState<PublicFormsData>(EMPTY_FORMS_DATA);
  const [state, setState] = useState<LoadState>("loading");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>(ALL_CATEGORIES);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FORMS_FETCH_TIMEOUT_MS);
    (async () => {
      try {
        const res = await fetch(buildApiUrl(PUBLIC_FORMS_ENDPOINT), {
          signal: controller.signal,
          // Public and uncredentialed: keeps the response cacheable and avoids
          // sending portal cookies on a cross-origin request.
          credentials: "omit",
        });
        if (!res.ok) throw new Error(`status ${res.status}`);
        const parsed = normalizeFormsResponse((await res.json()) as PublicFormsResponse);
        setData(parsed);
        setCategory(categoryFromSearch(window.location.search, parsed.categories));
        setState("ready");
      } catch (_err) {
        // Unlike the homepage advertisement, the catalogue IS the page — a
        // failure must be visible and actionable, not silently blank.
        setState("error");
      } finally {
        clearTimeout(timer);
      }
    })();
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, []);

  const visible = useMemo(
    () => filterForms(data.forms, query, category),
    [data.forms, query, category]
  );

  function selectCategory(slug: string) {
    setCategory(slug);
    try {
      const url = slug === ALL_CATEGORIES ? "?" : `?category=${encodeURIComponent(slug)}`;
      window.history.replaceState({}, "", url);
    } catch (_err) {
      /* history is unavailable in some embedded browsers; filtering still works */
    }
  }

  const filters = [{ slug: ALL_CATEGORIES, label: "All" }, ...data.categories];

  return (
    <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />

      <main style={{ flex: 1 }}>
        <Section bg={T.bg} style={{ paddingTop: 52, paddingBottom: 60 }}>
          <SecTitle
            title="Embassy Forms & Downloads"
            sub="Official forms issued by the Embassy of Pakistan, Kuwait. Download the form you need, print it, complete it, and bring it with you to your appointment or visit."
          />

          {state === "ready" && data.updatedDisplay ? (
            <p style={{ fontSize: 12.5, color: T.mutedLt, margin: "-22px 0 26px" }}>
              Library last updated {data.updatedDisplay}.
            </p>
          ) : null}

          {state === "loading" ? (
            <p style={{ fontSize: 14, color: T.muted }}>Loading forms…</p>
          ) : null}

          {state === "error" ? (
            <div
              style={{
                background: T.surface,
                border: `1px solid ${T.borderLt}`,
                borderLeft: `4px solid ${T.error}`,
                borderRadius: 12,
                padding: "22px 24px",
              }}
            >
              <strong style={{ display: "block", color: T.navy, marginBottom: 6, fontSize: 15 }}>
                The forms library could not be loaded.
              </strong>
              <p style={{ fontSize: 13.5, color: T.muted, lineHeight: 1.7, margin: 0 }}>
                Please refresh the page in a moment. If it keeps failing, contact the Community
                Welfare Wing at{" "}
                <a href="mailto:parepkuwaitcwa37@gmail.com" style={{ color: T.green }}>
                  parepkuwaitcwa37@gmail.com
                </a>{" "}
                or +965 5597 7292 and we will send you the form directly.
              </p>
            </div>
          ) : null}

          {state === "ready" ? (
            <>
              <div style={{ display: "flex", flexDirection: "column", gap: 14, marginBottom: 24 }}>
                <div style={{ position: "relative", maxWidth: 520 }}>
                  <label htmlFor="forms-search" style={{ position: "absolute", left: -9999 }}>
                    Search forms
                  </label>
                  <input
                    id="forms-search"
                    type="search"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search forms — passport, NICOP, attestation…"
                    autoComplete="off"
                    spellCheck={false}
                    style={{
                      width: "100%",
                      padding: "12px 14px",
                      border: `1px solid ${T.border}`,
                      borderRadius: 10,
                      font: "inherit",
                      background: T.surface,
                      color: T.text,
                    }}
                  />
                </div>

                {data.categories.length > 1 ? (
                  <div role="group" aria-label="Filter forms by category" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {filters.map((cat) => {
                      const active = cat.slug === category;
                      return (
                        <a
                          key={cat.slug}
                          href={cat.slug === ALL_CATEGORIES ? "?" : `?category=${encodeURIComponent(cat.slug)}`}
                          aria-current={active ? "true" : "false"}
                          onClick={(e) => {
                            e.preventDefault();
                            selectCategory(cat.slug);
                          }}
                          style={{
                            padding: "7px 14px",
                            borderRadius: 999,
                            border: `1px solid ${active ? T.navy : T.border}`,
                            background: active ? T.navy : T.surface,
                            color: active ? "#fff" : T.navy,
                            fontSize: 13,
                            fontWeight: 600,
                            textDecoration: "none",
                            lineHeight: 1.4,
                          }}
                        >
                          {cat.label}
                        </a>
                      );
                    })}
                  </div>
                ) : null}
              </div>

              <p aria-live="polite" style={{ fontSize: 12.5, color: T.mutedLt, margin: "0 0 14px" }}>
                {data.forms.length === 0
                  ? ""
                  : visible.length === data.forms.length
                    ? `${data.forms.length} ${data.forms.length === 1 ? "form" : "forms"} available`
                    : `Showing ${visible.length} of ${data.forms.length} forms`}
              </p>

              {data.forms.length === 0 ? (
                <div
                  style={{
                    background: T.surface,
                    border: `1px solid ${T.borderLt}`,
                    borderRadius: 12,
                    padding: 28,
                    textAlign: "center",
                    color: T.muted,
                  }}
                >
                  <strong style={{ display: "block", color: T.navy, marginBottom: 6, fontSize: 15 }}>
                    No forms are published yet.
                  </strong>
                  Please check back shortly, or contact the Community Welfare Wing for the form you need.
                </div>
              ) : visible.length === 0 ? (
                <div
                  style={{
                    background: T.surface,
                    border: `1px solid ${T.borderLt}`,
                    borderRadius: 12,
                    padding: 28,
                    textAlign: "center",
                    color: T.muted,
                  }}
                >
                  <strong style={{ display: "block", color: T.navy, marginBottom: 6, fontSize: 15 }}>
                    No forms match that search.
                  </strong>
                  Try a different word, or browse by category above.
                </div>
              ) : (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit,minmax(270px,1fr))",
                    gap: 18,
                  }}
                >
                  {visible.map((form) => (
                    <FormCard key={form.id} form={form} />
                  ))}
                </div>
              )}
            </>
          ) : null}
        </Section>

        <Section bg={T.surfaceLow} style={{ paddingTop: 0 }}>
          <ContactCard
            email="parepkuwaitcwa37@gmail.com"
            phone="+965 5597 7292"
            hours="Sunday – Thursday, 8:00 AM – 3:30 PM (Kuwait Time)"
          />
        </Section>
      </main>

      <PageFooter />
    </div>
  );
}

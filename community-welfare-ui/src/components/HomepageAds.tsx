/**
 * Admin-managed homepage advertisement (popup + banner) for the public site.
 *
 * Fetches the active advertisement from the backend's public, read-only API
 * and renders it. The Flask homepage gets the same payload embedded server-side
 * and rendered by static/js/site-ads.js; this is the React equivalent for
 * cwakuwait.com, which is a separate origin from the backend.
 *
 * Safety model, carried over from site-ads.js: administrator-entered content is
 * rendered exclusively as React text nodes — never dangerouslySetInnerHTML — so
 * it can never be interpreted as HTML. Click-through URLs are re-validated
 * client-side (defence in depth; the server already rejects unsafe schemes).
 * Any failure is swallowed: the homepage must keep working without the ad.
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  type AdBanner,
  type AdPayload,
  type AdPopup,
  type PublicAdsResponse,
  AD_FETCH_TIMEOUT_MS,
  PUBLIC_ADS_ENDPOINT,
  bannerDismissalKey,
  ctaAttributes,
  popupDismissalKey,
  shouldCollapseDetails,
  shouldShowPopup,
  telHref,
} from "../lib/homepageAds";
import { buildApiUrl } from "../lib/api";

// ── Storage wrappers (private modes throw on access) ───────────────

function storageGet(store: Storage | undefined, key: string) {
  try {
    return store?.getItem(key) ?? null;
  } catch (_err) {
    return null;
  }
}

function storageSet(store: Storage | undefined, key: string, value: string) {
  try {
    store?.setItem(key, value);
  } catch (_err) {
    /* best-effort */
  }
}

function currentHost() {
  return (typeof window !== "undefined" && window.location?.host) || "";
}

// ── Shared pieces ──────────────────────────────────────────────────

interface AdMediaProps {
  image: string;
  mobileImage: string;
  alt: string;
  eager?: boolean;
  className?: string;
}

/** Poster image. Never cropped: natural aspect ratio, no height cap. */
function AdMedia({ image, mobileImage, alt, eager, className }: AdMediaProps) {
  const [broken, setBroken] = useState(false);
  if (!image || broken) return null;
  const img = (
    <img
      src={image}
      alt={alt || ""}
      loading={eager ? "eager" : "lazy"}
      onError={() => setBroken(true)}
    />
  );
  return (
    <div className={className ? `cwa-ad-media ${className}` : "cwa-ad-media"}>
      {mobileImage ? (
        <picture>
          <source media="(max-width: 640px)" srcSet={mobileImage} />
          {img}
        </picture>
      ) : (
        img
      )}
    </div>
  );
}

interface AdLinkProps {
  label: string;
  url: string;
  newTab?: boolean;
  className?: string;
}

/** Link with a validated href; renders nothing when the URL is unsafe. */
function AdLink({ label, url, newTab, className }: AdLinkProps) {
  const attrs = useMemo(() => ctaAttributes(url, newTab, currentHost()), [url, newTab]);
  if (!attrs) return null;
  return (
    <a
      className={className}
      href={attrs.href}
      target={attrs.target || undefined}
      rel={attrs.rel || undefined}
    >
      {label}
      {attrs.external ? (
        <>
          <span className="cwa-ad-external" aria-hidden="true">
            {" ↗"}
          </span>
          <span className="cwa-sr-only"> (external website)</span>
        </>
      ) : null}
    </a>
  );
}

function UrduBlock({ heading, description }: { heading: string; description: string }) {
  if (!heading && !description) return null;
  return (
    <div className="cwa-ad-urdu" dir="rtl" lang="ur">
      {heading ? <strong>{heading}</strong> : null}
      {description ? <p>{description}</p> : null}
    </div>
  );
}

// ── Popup ──────────────────────────────────────────────────────────

const FOCUSABLE =
  'button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

function AdPopupDialog({ popup, onClose }: { popup: AdPopup; onClose: () => void }) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const headingId = useId();
  const descId = useId();
  const detailsId = useId();

  const collapsible = shouldCollapseDetails(popup);
  const [expanded, setExpanded] = useState(false);
  const showDetails = !collapsible || expanded;

  // Focus trap + Escape. Capture phase so the dialog wins over page handlers.
  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();

    function onKeydown(event: KeyboardEvent) {
      if (event.key === "Escape" || event.key === "Esc") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const items = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!items?.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeydown, true);
    return () => {
      document.removeEventListener("keydown", onKeydown, true);
      try {
        previousFocus?.focus?.();
      } catch (_err) {
        /* the trigger may have unmounted */
      }
    };
  }, [onClose]);

  // Lock background scroll. Compensating padding for the removed scrollbar
  // keeps the page from shifting sideways as the dialog opens.
  useEffect(() => {
    const { body, documentElement } = document;
    const previousOverflow = body.style.overflow;
    const previousPadding = body.style.paddingRight;
    const scrollbar = window.innerWidth - documentElement.clientWidth;
    body.style.overflow = "hidden";
    if (scrollbar > 0) body.style.paddingRight = `${scrollbar}px`;
    return () => {
      body.style.overflow = previousOverflow;
      body.style.paddingRight = previousPadding;
    };
  }, []);

  const tel = telHref(popup.contact);
  const hasContactRow = Boolean(popup.contact || popup.website);

  return (
    <div
      className="cwa-ad-overlay"
      onMouseDown={(event) => {
        // Backdrop click closes; never the only way out.
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="cwa-ad-dialog"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={popup.heading ? headingId : undefined}
        aria-label={popup.heading ? undefined : popup.disclosure || "Announcement"}
        aria-describedby={popup.description && showDetails ? descId : undefined}
      >
        <button
          type="button"
          className="cwa-ad-close"
          aria-label="Close advertisement"
          onClick={onClose}
          ref={closeRef}
        >
          ✕
        </button>

        {/* Only this region scrolls, so the close button stays reachable. */}
        <div className="cwa-ad-scroll">
          <AdMedia
            image={popup.image}
            mobileImage={popup.mobileImage}
            alt={popup.alt}
            eager
          />
          <div className="cwa-ad-body">
            <span className="cwa-ad-badge">{popup.disclosure || "Announcement"}</span>
            {popup.heading ? (
              <h2 className="cwa-ad-heading" id={headingId}>
                {popup.heading}
              </h2>
            ) : null}

            {collapsible ? (
              <button
                type="button"
                className="cwa-ad-disclosure"
                aria-expanded={expanded}
                aria-controls={detailsId}
                onClick={() => setExpanded((value) => !value)}
              >
                {expanded ? "Show less" : "Show full details"}
              </button>
            ) : null}

            {/* Collapsed only — never dropped. */}
            {showDetails ? (
              <div className="cwa-ad-details" id={detailsId}>
                {popup.description ? (
                  <p className="cwa-ad-desc" id={descId}>
                    {popup.description}
                  </p>
                ) : null}
                <UrduBlock heading={popup.headingUr} description={popup.descriptionUr} />
              </div>
            ) : null}

            {popup.ctaLabel ? (
              <div className="cwa-ad-actions">
                <AdLink
                  label={popup.ctaLabel}
                  url={popup.ctaUrl}
                  newTab={popup.ctaNewTab}
                  className="cwa-ad-btn cwa-ad-cta"
                />
              </div>
            ) : null}

            {hasContactRow ? (
              <div className="cwa-ad-contact-row">
                {popup.contact ? (
                  tel ? (
                    <a className="cwa-ad-contact" href={tel}>
                      {popup.contact}
                    </a>
                  ) : (
                    <span className="cwa-ad-contact">{popup.contact}</span>
                  )
                ) : null}
                {popup.website ? (
                  <AdLink
                    label={popup.website}
                    url={popup.website}
                    newTab
                    className="cwa-ad-website"
                  />
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Banner ─────────────────────────────────────────────────────────

function AdBannerCard({ banner, onDismiss }: { banner: AdBanner; onDismiss: () => void }) {
  return (
    <article
      className="cwa-ad-banner"
      aria-label={`${banner.disclosure || "Announcement"}: ${banner.heading || ""}`}
    >
      <div className="cwa-ad-banner-copy">
        <span className="cwa-ad-badge">{banner.disclosure || "Announcement"}</span>
        {banner.heading ? <h2 className="cwa-ad-banner-heading">{banner.heading}</h2> : null}
        {banner.description ? <p className="cwa-ad-banner-desc">{banner.description}</p> : null}
        <UrduBlock heading={banner.headingUr} description={banner.descriptionUr} />
        {banner.buttonLabel ? (
          <div className="cwa-ad-actions">
            <AdLink
              label={banner.buttonLabel}
              url={banner.buttonUrl}
              newTab
              className="cwa-ad-btn"
            />
          </div>
        ) : null}
      </div>
      <AdMedia
        image={banner.image}
        mobileImage={banner.mobileImage}
        alt={banner.alt}
        className="cwa-ad-banner-media"
      />
      {banner.dismissible ? (
        <button
          type="button"
          className="cwa-ad-banner-close"
          aria-label={`Dismiss this ${(banner.disclosure || "announcement").toLowerCase()}`}
          onClick={onDismiss}
        >
          ✕
        </button>
      ) : null}
    </article>
  );
}

// ── Container ──────────────────────────────────────────────────────

export interface HomepageAdsProps {
  /** Injected in tests; defaults to the live public endpoint. */
  payloadOverride?: AdPayload | null;
}

export function HomepageAds({ payloadOverride }: HomepageAdsProps = {}) {
  const [payload, setPayload] = useState<AdPayload | null>(payloadOverride ?? null);
  const [popupOpen, setPopupOpen] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  useEffect(() => {
    if (payloadOverride !== undefined) return;
    const controller = new AbortController();
    // The backend is a separate service that can cold-start; give up rather
    // than leaving a request hanging for the life of the page.
    const timer = setTimeout(() => controller.abort(), AD_FETCH_TIMEOUT_MS);
    (async () => {
      try {
        const res = await fetch(buildApiUrl(PUBLIC_ADS_ENDPOINT), {
          signal: controller.signal,
          // Public, uncredentialed: keeps the response cacheable and avoids
          // sending portal cookies to a cross-origin request.
          credentials: "omit",
        });
        if (!res.ok) return;
        const data = (await res.json()) as PublicAdsResponse;
        const next = data?.advertisement ?? null;
        // Ignore anything that is not a usable payload; a malformed body must
        // leave `payload` null so nothing renders.
        if (next && typeof next === "object" && (next.popup || next.banner)) {
          setPayload(next);
        }
      } catch (_err) {
        // Never let an advertisement failure affect the homepage: on abort,
        // timeout, network error, non-2xx or invalid JSON, payload stays null
        // and neither the popup nor the banner is rendered.
      } finally {
        clearTimeout(timer);
      }
    })();
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [payloadOverride]);

  const popup = payload?.popup ?? null;
  // The public API never sends preview payloads; honoured only for parity with
  // site-ads.js so a preview surface would not write dismissal state.
  const isPreview = Boolean(payload?.preview);

  useEffect(() => {
    if (!popup) return;
    const key = popupDismissalKey(popup.id, popup.v);
    const show =
      isPreview ||
      shouldShowPopup(popup, {
        localValue: storageGet(window.localStorage, key),
        sessionValue: storageGet(window.sessionStorage, key),
        now: Date.now(),
      });
    if (!show) return;
    setPopupOpen(true);
    if (!isPreview && popup.frequency === "once_per_session") {
      storageSet(window.sessionStorage, key, "1");
    }
  }, [popup, isPreview]);

  const closePopup = useCallback(() => {
    setPopupOpen(false);
    if (popup && !isPreview) {
      storageSet(
        window.localStorage,
        popupDismissalKey(popup.id, popup.v),
        String(Date.now())
      );
    }
  }, [popup, isPreview]);

  const banner = payload?.banner ?? null;
  const bannerHidden = useMemo(() => {
    if (!banner) return true;
    if (bannerDismissed) return true;
    if (isPreview || !banner.dismissible) return false;
    return Boolean(storageGet(window.localStorage, bannerDismissalKey(banner.id, banner.v)));
  }, [banner, bannerDismissed, isPreview]);

  const dismissBanner = useCallback(() => {
    setBannerDismissed(true);
    if (banner && !isPreview) {
      storageSet(
        window.localStorage,
        bannerDismissalKey(banner.id, banner.v),
        String(Date.now())
      );
    }
  }, [banner, isPreview]);

  return (
    <>
      {banner && !bannerHidden ? (
        <div className="cwa-ad-banner-slot">
          <AdBannerCard banner={banner} onDismiss={dismissBanner} />
        </div>
      ) : null}
      {popup && popupOpen && typeof document !== "undefined"
        ? createPortal(<AdPopupDialog popup={popup} onClose={closePopup} />, document.body)
        : null}
    </>
  );
}

/**
 * CWA Website Advertisements — public homepage popup + banner renderer.
 *
 * Reads the server-embedded payload (window.CWA_ADS, JSON injected by
 * render_public_home / the admin preview) and renders:
 *   - a large accessible popup dialog over a dimmed backdrop, and/or
 *   - a smaller banner card inside #cwaAdBannerSlot (below the hero,
 *     before the services grid).
 *
 * Safety model: every visible element is built with document.createElement /
 * textContent / setAttribute — admin-entered content is NEVER interpreted as
 * HTML. Click-through URLs are re-validated here (defence in depth; the
 * server already rejects unsafe schemes). Any thrown error is swallowed so
 * the homepage keeps working without the advertisement.
 *
 * Dismissal persistence (per owner decision #16):
 *   popup:  localStorage  cwa_ad_dismissed:<id>:<content_version>
 *   banner: localStorage  cwa_ad_banner_dismissed:<id>:<content_version>
 *   session frequency uses sessionStorage with the popup key.
 * A new content_version therefore re-shows an ad dismissed at an older
 * version. Preview mode (payload.preview) never reads or writes storage.
 */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.CwaSiteAds = api;
    if (typeof document !== 'undefined') {
      api._autoInit();
    }
  }
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';

  // ── Pure logic (unit-tested by tests/smoke/site_ads_logic.mjs) ──

  function popupDismissalKey(id, version) {
    return 'cwa_ad_dismissed:' + String(id) + ':' + String(version);
  }

  function bannerDismissalKey(id, version) {
    return 'cwa_ad_banner_dismissed:' + String(id) + ':' + String(version);
  }

  /**
   * Decide whether the popup should show.
   * opts: { localValue, sessionValue, now } — storage reads are injected so
   * this stays pure and testable.
   */
  function shouldShowPopup(popup, opts) {
    if (!popup) return false;
    opts = opts || {};
    var frequency = popup.frequency || 'once_per_version';
    if (frequency === 'every_visit') return true;
    if (frequency === 'once_per_session') return !opts.sessionValue;
    // once_per_version (default)
    if (!opts.localValue) return true;
    var dismissedAt = parseInt(opts.localValue, 10);
    if (isNaN(dismissedAt)) return true;
    var hours = parseInt(popup.dismissalHours, 10);
    if (isNaN(hours) || hours <= 0) return false; // 0 = never re-show this version
    var now = typeof opts.now === 'number' ? opts.now : Date.now();
    return (now - dismissedAt) >= hours * 3600000;
  }

  /**
   * Validate a click-through URL and derive safe link attributes.
   * Returns null when the URL must not be rendered.
   */
  function ctaAttributes(url, newTab, currentHost) {
    var s = String(url || '').trim();
    if (!s) return null;
    var external = false;
    if (s.indexOf('//') === 0) return null; // protocol-relative
    if (s.charAt(0) === '/') {
      external = false;
    } else if (/^https:\/\//i.test(s)) {
      var hostMatch = s.match(/^https:\/\/([^\/?#]+)/i);
      if (!hostMatch) return null;
      var host = hostMatch[1].toLowerCase();
      if (host.indexOf('@') !== -1) return null; // embedded credentials
      external = !currentHost || host.split(':')[0] !== String(currentHost).toLowerCase().split(':')[0];
    } else {
      return null; // javascript:, data:, http:, malformed — never render
    }
    var target = newTab ? '_blank' : '';
    return {
      href: s,
      target: target,
      rel: target === '_blank' ? 'noopener noreferrer' : '',
      external: external
    };
  }

  // ── Storage wrappers (privacy modes may throw) ──────────────────

  function storageGet(store, key) {
    try { return store.getItem(key); } catch (_err) { return null; }
  }

  function storageSet(store, key, value) {
    try { store.setItem(key, value); } catch (_err) { /* best-effort */ }
  }

  // ── DOM builders (createElement + textContent only; admin content
  //    is never parsed as HTML) ─────────────────────────────────────

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null && text !== '') node.textContent = text;
    return node;
  }

  function buildPicture(data, className, eager) {
    if (!data.image) return null;
    var wrap = el('div', className);
    var img;
    if (data.mobileImage) {
      var picture = document.createElement('picture');
      var source = document.createElement('source');
      source.setAttribute('media', '(max-width: 640px)');
      source.setAttribute('srcset', data.mobileImage);
      picture.appendChild(source);
      img = document.createElement('img');
      picture.appendChild(img);
      wrap.appendChild(picture);
    } else {
      img = document.createElement('img');
      wrap.appendChild(img);
    }
    img.setAttribute('src', data.image);
    img.setAttribute('alt', data.alt || '');
    img.setAttribute('loading', eager ? 'eager' : 'lazy');
    img.addEventListener('error', function () {
      // A missing/broken image must never break the layout.
      if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
    });
    return wrap;
  }

  function buildLink(label, attrs, className) {
    var link = el('a', className, label);
    link.setAttribute('href', attrs.href);
    if (attrs.target) link.setAttribute('target', attrs.target);
    if (attrs.rel) link.setAttribute('rel', attrs.rel);
    if (attrs.external) {
      var marker = el('span', 'cwa-ad-external');
      marker.setAttribute('aria-hidden', 'true');
      marker.textContent = ' ↗';
      link.appendChild(marker);
      var sr = el('span', 'cwa-sr-only', ' (external website)');
      link.appendChild(sr);
    }
    return link;
  }

  function buildUrduBlock(heading, description) {
    if (!heading && !description) return null;
    var block = el('div', 'cwa-ad-urdu');
    block.setAttribute('dir', 'rtl');
    block.setAttribute('lang', 'ur');
    if (heading) block.appendChild(el('strong', '', heading));
    if (description) block.appendChild(el('p', '', description));
    return block;
  }

  // ── Popup ────────────────────────────────────────────────────────

  function renderPopup(popup, isPreview) {
    var overlay = el('div', 'cwa-ad-overlay');
    var dialog = el('div', 'cwa-ad-dialog');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');

    var closeBtn = el('button', 'cwa-ad-close', '✕');
    closeBtn.setAttribute('type', 'button');
    closeBtn.setAttribute('aria-label', 'Close advertisement');
    dialog.appendChild(closeBtn);

    var media = buildPicture(popup, 'cwa-ad-media', true);
    if (media) dialog.appendChild(media);

    var body = el('div', 'cwa-ad-body');
    body.appendChild(el('span', 'cwa-ad-badge', popup.disclosure || 'Announcement'));

    if (popup.heading) {
      var heading = el('h2', 'cwa-ad-heading', popup.heading);
      heading.id = 'cwaAdPopupHeading';
      body.appendChild(heading);
      dialog.setAttribute('aria-labelledby', 'cwaAdPopupHeading');
    } else {
      dialog.setAttribute('aria-label', popup.disclosure || 'Announcement');
    }
    if (popup.description) {
      var desc = el('p', 'cwa-ad-desc', popup.description);
      desc.id = 'cwaAdPopupDesc';
      body.appendChild(desc);
      dialog.setAttribute('aria-describedby', 'cwaAdPopupDesc');
    }
    var urdu = buildUrduBlock(popup.headingUr, popup.descriptionUr);
    if (urdu) body.appendChild(urdu);

    var currentHost = (typeof location !== 'undefined' && location.host) || '';
    if (popup.ctaLabel) {
      var ctaAttrs = ctaAttributes(popup.ctaUrl, popup.ctaNewTab, currentHost);
      if (ctaAttrs) {
        var actions = el('div', 'cwa-ad-actions');
        actions.appendChild(buildLink(popup.ctaLabel, ctaAttrs, 'cwa-btn primary cwa-ad-cta'));
        body.appendChild(actions);
      }
    }

    var contactRow = el('div', 'cwa-ad-contact-row');
    if (popup.contact) {
      var digits = String(popup.contact).replace(/[^0-9+]/g, '');
      if (digits.length >= 5) {
        var tel = el('a', 'cwa-ad-contact', popup.contact);
        tel.setAttribute('href', 'tel:' + digits);
        contactRow.appendChild(tel);
      } else {
        contactRow.appendChild(el('span', 'cwa-ad-contact', popup.contact));
      }
    }
    if (popup.website) {
      var webAttrs = ctaAttributes(popup.website, true, currentHost);
      if (webAttrs) {
        contactRow.appendChild(buildLink(popup.website, webAttrs, 'cwa-ad-website'));
      }
    }
    if (contactRow.childNodes.length) body.appendChild(contactRow);

    dialog.appendChild(body);
    overlay.appendChild(dialog);

    // Focus management: trap Tab inside the dialog, restore focus on close.
    var previousFocus = document.activeElement;
    var closed = false;

    function focusables() {
      return dialog.querySelectorAll(
        'button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    }

    function onKeydown(event) {
      if (event.key === 'Escape' || event.key === 'Esc') {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== 'Tab') return;
      var items = focusables();
      if (!items.length) return;
      var first = items[0];
      var last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    function close() {
      if (closed) return;
      closed = true;
      document.removeEventListener('keydown', onKeydown, true);
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      document.body.classList.remove('cwa-ad-open');
      if (!isPreview) {
        storageSet(window.localStorage, popupDismissalKey(popup.id, popup.v), String(Date.now()));
      }
      if (previousFocus && typeof previousFocus.focus === 'function') {
        try { previousFocus.focus(); } catch (_err) {}
      }
    }

    closeBtn.addEventListener('click', close);
    overlay.addEventListener('mousedown', function (event) {
      // Backdrop click closes; never the only close mechanism.
      if (event.target === overlay) close();
    });
    document.addEventListener('keydown', onKeydown, true);

    document.body.appendChild(overlay);
    document.body.classList.add('cwa-ad-open');
    if (!isPreview && popup.frequency === 'once_per_session') {
      storageSet(window.sessionStorage, popupDismissalKey(popup.id, popup.v), '1');
    }
    closeBtn.focus();
  }

  // ── Banner ───────────────────────────────────────────────────────

  function renderBanner(banner, isPreview) {
    var slot = document.getElementById('cwaAdBannerSlot');
    if (!slot) return;
    if (!isPreview && banner.dismissible &&
        storageGet(window.localStorage, bannerDismissalKey(banner.id, banner.v))) {
      return;
    }

    var card = el('article', 'cwa-campaign-card cwa-ad-banner');
    card.setAttribute('aria-label', (banner.disclosure || 'Announcement') + ': ' + (banner.heading || ''));

    var copy = el('div', 'cwa-ad-banner-copy');
    copy.appendChild(el('span', 'cwa-ad-badge', banner.disclosure || 'Announcement'));
    if (banner.heading) copy.appendChild(el('h2', 'cwa-ad-banner-heading', banner.heading));
    if (banner.description) copy.appendChild(el('p', 'cwa-ad-banner-desc', banner.description));
    var urdu = buildUrduBlock(banner.headingUr, banner.descriptionUr);
    if (urdu) copy.appendChild(urdu);

    if (banner.buttonLabel) {
      var currentHost = (typeof location !== 'undefined' && location.host) || '';
      var attrs = ctaAttributes(banner.buttonUrl, true, currentHost);
      if (attrs) {
        var actions = el('div', 'cwa-ad-actions');
        actions.appendChild(buildLink(banner.buttonLabel, attrs, 'cwa-btn primary'));
        copy.appendChild(actions);
      }
    }
    card.appendChild(copy);

    var media = buildPicture(banner, 'cwa-ad-media cwa-ad-banner-media', false);
    if (media) card.appendChild(media);

    if (banner.dismissible) {
      var dismissBtn = el('button', 'cwa-ad-banner-close', '✕');
      dismissBtn.setAttribute('type', 'button');
      dismissBtn.setAttribute('aria-label', 'Dismiss this ' + (banner.disclosure || 'announcement').toLowerCase());
      dismissBtn.addEventListener('click', function () {
        if (card.parentNode) card.parentNode.removeChild(card);
        if (!isPreview) {
          storageSet(window.localStorage, bannerDismissalKey(banner.id, banner.v), String(Date.now()));
        }
      });
      card.appendChild(dismissBtn);
    }

    slot.appendChild(card);
  }

  // ── Init ─────────────────────────────────────────────────────────

  function renderPreviewRibbon() {
    var ribbon = el('div', 'cwa-ad-preview-ribbon', 'Preview — not published');
    ribbon.setAttribute('role', 'status');
    document.body.appendChild(ribbon);
  }

  function init(payload) {
    try {
      if (!payload || typeof payload !== 'object') return;
      var isPreview = !!payload.preview;
      if (isPreview) renderPreviewRibbon();

      if (payload.banner) {
        try { renderBanner(payload.banner, isPreview); } catch (_err) {}
      }
      if (payload.popup) {
        var show = isPreview || shouldShowPopup(payload.popup, {
          localValue: storageGet(window.localStorage,
            popupDismissalKey(payload.popup.id, payload.popup.v)),
          sessionValue: storageGet(window.sessionStorage,
            popupDismissalKey(payload.popup.id, payload.popup.v)),
          now: Date.now()
        });
        if (show) {
          try { renderPopup(payload.popup, isPreview); } catch (_err) {}
        }
      }
    } catch (_err) {
      // Advertisement failures must never affect the homepage.
    }
  }

  function _autoInit() {
    function run() { init(window.CWA_ADS); }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', run);
    } else {
      run();
    }
  }

  return {
    popupDismissalKey: popupDismissalKey,
    bannerDismissalKey: bannerDismissalKey,
    shouldShowPopup: shouldShowPopup,
    ctaAttributes: ctaAttributes,
    init: init,
    _autoInit: _autoInit
  };
});

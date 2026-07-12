// Pure-logic tests for static/js/site-ads.js (dismissal keys, display
// frequency, CTA URL safety attributes). No DOM required.
// Usage: node tests/smoke/site_ads_logic.mjs
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const require = createRequire(import.meta.url);
const api = require(join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'static', 'js', 'site-ads.js'));

let passes = 0;
const failures = [];
function check(name, ok, detail = '') {
  if (ok) { passes += 1; console.log(`  PASS  ${name}`); }
  else { failures.push(name); console.log(`  FAIL  ${name} ${detail}`); }
}

const HOUR = 3600000;

// ── Dismissal keys ──
check('popup key format', api.popupDismissalKey(3, 2) === 'cwa_ad_dismissed:3:2');
check('banner key format', api.bannerDismissalKey(3, 2) === 'cwa_ad_banner_dismissed:3:2');
check('popup and banner keys differ', api.popupDismissalKey(3, 2) !== api.bannerDismissalKey(3, 2));
check('new content version changes key', api.popupDismissalKey(3, 2) !== api.popupDismissalKey(3, 3));

// ── shouldShowPopup ──
const base = { frequency: 'once_per_version', dismissalHours: 168 };
check('no popup -> false', api.shouldShowPopup(null, {}) === false);
check('never dismissed -> show', api.shouldShowPopup(base, { localValue: null }) === true);
check('recently dismissed -> hide',
  api.shouldShowPopup(base, { localValue: String(Date.now() - HOUR), now: Date.now() }) === false);
check('dismissed beyond window -> re-show',
  api.shouldShowPopup(base, { localValue: String(Date.now() - 169 * HOUR), now: Date.now() }) === true);
check('dismissalHours 0 -> never re-show this version',
  api.shouldShowPopup({ ...base, dismissalHours: 0 },
    { localValue: String(Date.now() - 9999 * HOUR), now: Date.now() }) === false);
check('garbage stored value -> show',
  api.shouldShowPopup(base, { localValue: 'garbage' }) === true);
check('every_visit ignores dismissal',
  api.shouldShowPopup({ frequency: 'every_visit', dismissalHours: 168 },
    { localValue: String(Date.now()), sessionValue: '1' }) === true);
check('once_per_session respects session flag',
  api.shouldShowPopup({ frequency: 'once_per_session' }, { sessionValue: '1' }) === false);
check('once_per_session shows in fresh session',
  api.shouldShowPopup({ frequency: 'once_per_session' }, { sessionValue: null }) === true);

// ── ctaAttributes ──
const HOSTNAME = 'cwakuwait.com';
check('javascript: rejected', api.ctaAttributes('javascript:alert(1)', true, HOSTNAME) === null);
check('data: rejected', api.ctaAttributes('data:text/html,x', true, HOSTNAME) === null);
check('plain http rejected', api.ctaAttributes('http://x.example', true, HOSTNAME) === null);
check('protocol-relative rejected', api.ctaAttributes('//evil.example', true, HOSTNAME) === null);
check('embedded credentials rejected', api.ctaAttributes('https://a:b@evil.example', true, HOSTNAME) === null);
check('empty rejected', api.ctaAttributes('', true, HOSTNAME) === null);

const internal = api.ctaAttributes('/nurses', false, HOSTNAME);
check('internal path allowed', internal !== null && internal.href === '/nurses');
check('internal not external', internal !== null && internal.external === false);
check('same-tab has no rel', internal !== null && internal.rel === '' && internal.target === '');

const external = api.ctaAttributes('https://mangoesfrompakistan.example/x', true, HOSTNAME);
check('external https allowed', external !== null);
check('external flagged as external', external !== null && external.external === true);
check('new tab gets noopener noreferrer',
  external !== null && external.target === '_blank' && external.rel === 'noopener noreferrer');

const sameHost = api.ctaAttributes('https://cwakuwait.com/page', true, HOSTNAME);
check('same-host https not external', sameHost !== null && sameHost.external === false);

console.log(`\nPassed: ${passes}  Failed: ${failures.length}`);
if (failures.length) {
  failures.forEach((name) => console.log(`  - ${name}`));
  process.exit(1);
}

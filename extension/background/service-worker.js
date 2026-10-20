function yt() {
  const n = globalThis.browser ?? globalThis.chrome;
  return n?.runtime ? n : void 0;
}
function vt() {
  const n = yt();
  if (!n)
    throw new Error("WebExtension API unavailable in this context");
  return n;
}
function R() {
  return yt();
}
function Xt() {
  try {
    return vt().runtime.getManifest().version ?? "0.0.0";
  } catch {
    return "0.0.0";
  }
}
const en = 1;
function G(n) {
  return { ok: !0, data: n };
}
function Qe(n) {
  return { ok: !1, error: n };
}
function tn(n) {
  if (typeof n != "object" || n === null) return !1;
  const e = n;
  return e.v === en && typeof e.type == "string" && "payload" in e;
}
function nn(n) {
  const e = R();
  e?.runtime?.onMessage && e.runtime.onMessage.addListener((t, r, a) => tn(t) ? (Promise.resolve(n(t, r)).then((s) => a(s)).catch((s) => {
    a({
      ok: !1,
      error: s instanceof Error ? s.message : "handler failed"
    });
  }), !0) : !1);
}
const Ie = 1500, _t = 200, rn = /\b(?:responsibilit(?:y|ies)|qualifications?|requirements?|experience|benefits|salary|compensation|apply|candidate|role|position|skills|degree|full[- ]time|part[- ]time|remote|hybrid|equal (?:employment )?opportunity|what you(?:'|’)ll do|about (?:the|this) (?:role|job|position)|who you are)\b/giu, bt = /\b(?:talent (?:community|network|pool)|join our (?:talent|team)|search (?:jobs|results)|job search|career (?:site|portal|home)|sign in|log ?in|create (?:an )?account|my (?:profile|applications?))\b/iu, an = /\b(?:no longer (?:available|accepting applications|open|active)|(?:this|the) (?:job|position|posting|role|requisition|opening) (?:is|has been) (?:closed|filled|removed|expired|deactivated)|position has been filled|job (?:not found|has expired|is closed)|posting (?:has )?expired|page (?:you (?:are looking for|requested) )?(?:could not be|cannot be|was not) found|career section (?:is )?unavailable)\b/iu;
function qe(n) {
  const e = n?.result.job;
  if (!e) return !1;
  const t = e.description ?? "";
  return t.length >= Ie ? !1 : n?.result.metadata?.closedNotice === !0 ? !0 : an.test(`${e.title ?? ""}
${t}`);
}
function wt(n) {
  const e = /* @__PURE__ */ new Set();
  for (const t of n.matchAll(rn)) e.add(t[0].toLowerCase());
  return e.size;
}
function Ke(n) {
  const e = n.result?.job;
  if (!e) return -1;
  const t = e.description ?? "";
  let r = 0;
  return e.title && (r += 1), e.title && bt.test(e.title) && (r -= 1.5), e.company && (r += 0.4), r += Math.min(t.length, 4e3) / 4e3, r += (n.result?.extractionConfidence ?? 0) * 0.5, r += Math.min(n.classification.heads.listing, 1) * 0.3, n.providerRole === "host-shell" && (r -= 2), n.provider && (r += 0.2), r;
}
function xt(n) {
  const e = n.filter((u) => u.result);
  if (e.length === 0) return null;
  const t = [...e].sort((u, m) => Ke(m) - Ke(u)), r = t[0], a = r.result;
  let s = a.job;
  if (s) {
    const u = t.slice(1).map((A) => A.result?.job).filter((A) => !!A), m = {};
    for (const A of ["company", "location", "companyLogoUrl"]) {
      if (s[A]) continue;
      const S = u.find((U) => typeof U[A] == "string" && U[A]);
      S && (m[A] = S[A]);
    }
    Object.keys(m).length > 0 && (s = { ...s, ...m });
  }
  const i = new Map(a.questions.map((u) => [u.id, u])), o = [...a.forms];
  for (const u of e)
    if (!(u === r || !u.result)) {
      for (const m of u.result.questions) i.has(m.id) || i.set(m.id, m);
      o.push(...u.result.forms);
    }
  const f = { ...a, questions: [...i.values()], forms: o };
  return s && (f.job = s), { primary: r, result: f };
}
function kt(n) {
  const e = n?.result.job;
  if (!n || !e?.title || qe(n)) return "none";
  const t = e.description ?? "";
  return t.length < _t ? e.title && Ye(n) ? "partial" : "none" : !Ye(n) && wt(t) < 3 ? "none" : bt.test(e.title) && t.length < Ie ? "partial" : e.company && t.length >= Ie ? "complete" : "partial";
}
function Ye(n) {
  const { primary: e, result: t } = n, r = t.job?.fieldProvenance ?? {};
  return Object.values(r).some((s) => s?.layer === "structured_data") || e.provider !== null || e.classification.heads.listing >= 0.5 || wt(t.job?.description ?? "") >= 4;
}
function sn(n) {
  const e = n?.result.job;
  if (!n || !e?.title || qe(n)) return !1;
  if ((e.description ?? "").length >= _t) return kt(n) !== "none";
  const t = e.fieldProvenance ?? {};
  return n.primary.provider !== null || Object.values(t).some((r) => r?.layer === "structured_data");
}
function on(n) {
  const e = n?.result.job;
  return e ? `${e.title ?? ""}|${e.company ?? ""}|${e.location ?? ""}|${(e.description ?? "").length}` : "";
}
const Xe = 6e4;
class cn {
  sessions = /* @__PURE__ */ new Map();
  record(e, t, r) {
    const a = this.sessions.get(e) ?? {
      tabId: e,
      url: r.url,
      frames: /* @__PURE__ */ new Map(),
      updatedAt: Date.now()
    };
    r.isTopFrame && a.url !== r.url && (a.frames.clear(), a.url = r.url), a.frames.set(t, { frameId: t, report: r, receivedAt: Date.now() }), a.updatedAt = Date.now(), this.sessions.set(e, a);
  }
  clearFrame(e, t) {
    this.sessions.get(e)?.frames.delete(t);
  }
  clearTab(e) {
    this.sessions.delete(e);
  }
  /**
   * Picks the authoritative view of a tab.
   *
   * Scoring combines extraction confidence with classification confidence, then
   * demotes a host shell when a real embedded frame reported for the same
   * provider — the shell is, by definition, the frame without the content.
   */
  aggregate(e) {
    const t = this.sessions.get(e);
    if (!t) return null;
    const r = [...t.frames.values()], a = r.reduce((S, U) => Math.max(S, U.receivedAt), 0), s = r.filter((S) => a - S.receivedAt < Xe);
    if (s.length === 0)
      return {
        tabId: e,
        url: t.url,
        classification: null,
        provider: null,
        result: null,
        frameCount: 0
      };
    const i = s.some((S) => S.report.providerRole === "embedded"), f = s.map((S) => ({ entry: S, score: un(S, i) })).sort((S, U) => U.score - S.score)[0].entry, u = s.reduce(
      (S, U) => (U.report.classification.heads.application ?? 0) > (S.report.classification.heads.application ?? 0) ? U : S
    ), m = xt(s.map((S) => S.report));
    if (m?.result.job)
      return {
        tabId: e,
        url: t.url,
        classification: m.primary.classification,
        provider: m.primary.provider,
        result: m.result,
        frameCount: s.length
      };
    const A = dn(f.report, u.report);
    return {
      tabId: e,
      url: t.url,
      classification: f.report.classification,
      provider: f.report.provider,
      result: A,
      frameCount: s.length
    };
  }
  /** Every live frame report of a tab, for the save-time merge. */
  reports(e) {
    const t = this.sessions.get(e);
    if (!t) return [];
    const r = [...t.frames.values()], a = r.reduce((s, i) => Math.max(s, i.receivedAt), 0);
    return r.filter((s) => a - s.receivedAt < Xe).map((s) => s.report);
  }
  /** Drops sessions for tabs that no longer exist. Called on tab removal. */
  prune(e) {
    for (const t of this.sessions.keys())
      e.has(t) || this.sessions.delete(t);
  }
  get size() {
    return this.sessions.size;
  }
}
const ln = 0.4;
function un(n, e) {
  const { report: t } = n, r = t.result?.extractionConfidence ?? 0, a = t.classification.confidence;
  let s = r * 0.6 + a * 0.4 + t.providerScore * 0.2;
  return t.providerRole === "host-shell" && e && (s *= ln), t.isTopFrame && (s += 0.01), s;
}
function dn(n, e) {
  if (!n.result) return e.result;
  if (n === e || !e.result) return n.result;
  const t = e.result.questions;
  if (t.length === 0) return n.result;
  const r = new Map(n.result.questions.map((a) => [a.id, a]));
  for (const a of t) r.set(a.id, a);
  return {
    ...n.result,
    questions: [...r.values()],
    forms: [...n.result.forms, ...e.result.forms]
  };
}
const fn = [
  {
    pattern: "https://boards.greenhouse.io/*",
    provider: "greenhouse",
    reason: "Greenhouse hosted job boards and application forms."
  },
  {
    pattern: "https://job-boards.greenhouse.io/*",
    provider: "greenhouse",
    reason: "Current Greenhouse board host, used alongside boards.greenhouse.io."
  },
  {
    pattern: "https://*.greenhouse.io/*",
    provider: "greenhouse",
    reason: "Greenhouse embed and API subdomains used by iframe-embedded boards."
  },
  {
    pattern: "https://jobs.lever.co/*",
    provider: "lever",
    reason: "Lever hosted postings and application forms."
  },
  {
    pattern: "https://*.lever.co/*",
    provider: "lever",
    reason: "Lever embed subdomains."
  },
  {
    pattern: "https://*.myworkdayjobs.com/*",
    provider: "workday",
    reason: "Workday customer-tenant career sites and multi-step applications."
  },
  {
    pattern: "https://*.wd1.myworkdaysite.com/*",
    provider: "workday",
    reason: "Workday alternate site host."
  },
  {
    pattern: "https://jobs.ashbyhq.com/*",
    provider: "ashby",
    reason: "Ashby hosted job boards."
  },
  {
    pattern: "https://www.linkedin.com/jobs/*",
    provider: "linkedin",
    reason: "LinkedIn job detail pages. Scoped to /jobs, not all of LinkedIn."
  },
  {
    pattern: "https://*.indeed.com/*",
    provider: "indeed",
    reason: "Indeed job detail and apply pages."
  },
  {
    pattern: "https://*.smartrecruiters.com/*",
    provider: "smartrecruiters",
    reason: "SmartRecruiters hosted postings."
  },
  {
    pattern: "https://jobs.jobvite.com/*",
    provider: "jobvite",
    reason: "Jobvite hosted postings."
  },
  {
    pattern: "https://*.icims.com/*",
    provider: "icims",
    reason: "iCIMS customer career portals."
  },
  {
    pattern: "https://*.oraclecloud.com/*",
    provider: "oracle",
    reason: "Oracle Recruiting Cloud career sites. Each customer is served from its own <tenant>.fa.<region>.oraclecloud.com host, so the pattern cannot be narrower."
  },
  {
    pattern: "https://*.taleo.net/*",
    provider: "taleo",
    reason: "Oracle Taleo career sections."
  },
  {
    pattern: "https://*.bamboohr.com/*",
    provider: "bamboohr",
    reason: "BambooHR hosted career pages."
  },
  {
    pattern: "https://myjobs.adp.com/*",
    provider: "adp",
    reason: "ADP-hosted external career sites, used by employers on ADP Workforce Now."
  },
  {
    pattern: "https://workforcenow.adp.com/*",
    provider: "adp",
    reason: "ADP Workforce Now recruitment pages."
  },
  {
    pattern: "https://*.ashbyhq.com/*",
    provider: "ashby",
    reason: "Ashby embed and application subdomains used by iframe-embedded boards."
  },
  {
    pattern: "https://*.workable.com/*",
    provider: "workable",
    reason: "Workable hosted postings and application forms (apply.workable.com, jobs.workable.com)."
  },
  {
    pattern: "https://ats.rippling.com/*",
    provider: "rippling",
    reason: "Rippling ATS hosted postings and application forms."
  },
  {
    pattern: "https://*.applytojob.com/*",
    provider: "jazzhr",
    reason: "JazzHR hosted postings, served from each employer’s applytojob.com subdomain."
  },
  {
    pattern: "https://jobright.ai/jobs/*",
    provider: "jobright",
    reason: "Jobright job detail pages. Scoped to /jobs, not all of jobright.ai."
  },
  {
    pattern: "https://*.jobdiva.com/*",
    provider: "jobdiva",
    reason: "JobDiva hosted postings, common with staffing agencies."
  },
  {
    pattern: "https://recruiting.ultipro.com/*",
    provider: "ultipro",
    reason: "UKG Pro (UltiPro) recruiting portals."
  }
], St = fn.map((n) => n.pattern), pn = [
  {
    pattern: "https://*.supabase.co/*",
    provider: "backend",
    reason: "Sign in and sync saved jobs to the user’s own Supabase project. Only contacted after the user configures a project URL and signs in."
  }
];
pn.map((n) => n.pattern);
const et = "jp-dyn-", we = ["content/content.js"];
function hn(n) {
  try {
    const e = new URL(n);
    return e.protocol !== "https:" && e.protocol !== "http:" ? null : `${e.protocol}//${e.hostname}/*`;
  } catch {
    return null;
  }
}
async function mn(n) {
  const e = R(), t = hn(n);
  if (!e?.permissions || !t) return !1;
  try {
    return await e.permissions.contains({ origins: [t] });
  } catch {
    return !1;
  }
}
async function Tt() {
  const n = R();
  if (!n?.permissions) return [];
  try {
    const e = await n.permissions.getAll(), t = new Set(St);
    return (e.origins ?? []).filter((r) => !t.has(r));
  } catch {
    return [];
  }
}
async function xe() {
  const n = R();
  if (n?.scripting?.registerContentScripts)
    try {
      const e = new Map(
        (await Tt()).map((i) => [`${et}${gn(i)}`, i])
      ), t = await n.scripting.getRegisteredContentScripts(), r = t.filter(
        (i) => i.id.startsWith(et) && (!e.has(i.id) || i.runAt !== "document_end")
      ).map((i) => i.id);
      r.length > 0 && await n.scripting.unregisterContentScripts({ ids: r });
      const a = new Set(t.filter((i) => !r.includes(i.id)).map((i) => i.id)), s = [...e].filter(([i]) => !a.has(i)).map(([i, o]) => ({
        id: i,
        matches: [o],
        js: we,
        // See manifest.config.ts: idle never comes for some frames.
        runAt: "document_end",
        allFrames: !0,
        persistAcrossSessions: !0
      }));
      s.length > 0 && await n.scripting.registerContentScripts(s);
    } catch {
    }
}
async function jt(n) {
  const e = R();
  if (!(!e?.tabs?.query || !e.scripting?.executeScript || n.length === 0))
    try {
      const t = await e.tabs.query({ url: [...n] });
      await Promise.all(
        t.map(async (r) => {
          if (r.id !== void 0)
            try {
              await e.scripting.executeScript({
                target: { tabId: r.id, allFrames: !0 },
                files: we
              });
            } catch {
            }
        })
      );
    } catch {
    }
}
function gn(n) {
  let e = 2166136261;
  for (let t = 0; t < n.length; t += 1)
    e ^= n.charCodeAt(t), e = Math.imul(e, 16777619) >>> 0;
  return e.toString(16).padStart(8, "0");
}
const I = {
  /** User settings. Synced across the user's devices where available. */
  settings: "settings:v1",
  /** Recently extracted jobs, newest first. Local only. */
  recentExtractions: "extractions:v1",
  /** Anonymous rotating install id for telemetry. Local only. */
  installId: "install-id:v1",
  /** Per-origin grants the user made at runtime. Local only. */
  grantedOrigins: "granted-origins:v1",
  /** Adapter probe health counters, used to detect ATS redesigns. Local only. */
  adapterHealth: "adapter-health:v1",
  /** Supabase session. Local only, never synced: a bearer token must not be
   * copied to the user's other devices by the browser. */
  supabaseSession: "supabase-session:v1"
}, yn = {
  [I.settings]: "sync",
  [I.recentExtractions]: "local",
  [I.installId]: "local",
  [I.grantedOrigins]: "local",
  [I.adapterHealth]: "local",
  [I.supabaseSession]: "local"
}, vn = 50, _n = {
  apiBaseUrl: "",
  // Default off. Telemetry that defaults on is not opt-in.
  telemetryEnabled: !1,
  // Default off. Reading what the user typed is a meaningfully bigger ask than
  // reading the page's own markup, so it stays behind an explicit choice.
  captureCurrentValues: !1,
  autoScan: !0,
  showBadge: !0,
  supabaseUrl: "",
  supabaseAnonKey: ""
}, Ee = /* @__PURE__ */ new Map();
function At(n) {
  const e = R();
  if (!e?.storage) return null;
  const t = yn[n];
  return t === "session" ? e.storage.session ?? e.storage.local : t === "sync" ? e.storage.sync ?? e.storage.local : e.storage.local;
}
async function ue(n, e) {
  const t = At(n);
  if (!t) return Ee.get(n) ?? e;
  try {
    const a = (await t.get(n))[n];
    return a === void 0 ? e : a;
  } catch {
    return e;
  }
}
async function Ve(n, e) {
  const t = At(n);
  if (!t) {
    Ee.set(n, e);
    return;
  }
  try {
    await t.set({ [n]: e });
  } catch {
    Ee.set(n, e);
  }
}
async function ke() {
  const n = await ue(I.settings, {});
  return { ..._n, ...n };
}
async function bn(n) {
  const e = await ue(I.recentExtractions, []), t = n.job?.fingerprint ?? n.page.url, r = e.filter(
    (a) => (a.job?.fingerprint ?? a.page.url) !== t
  );
  r.unshift(n), await Ve(I.recentExtractions, r.slice(0, vn));
}
async function wn() {
  return ue(I.recentExtractions, []);
}
async function xn() {
  const n = await ue(I.installId, "");
  if (n) return n;
  const e = crypto.randomUUID();
  return await Ve(I.installId, e), e;
}
var x;
(function(n) {
  n.assertEqual = (a) => {
  };
  function e(a) {
  }
  n.assertIs = e;
  function t(a) {
    throw new Error();
  }
  n.assertNever = t, n.arrayToEnum = (a) => {
    const s = {};
    for (const i of a)
      s[i] = i;
    return s;
  }, n.getValidEnumValues = (a) => {
    const s = n.objectKeys(a).filter((o) => typeof a[a[o]] != "number"), i = {};
    for (const o of s)
      i[o] = a[o];
    return n.objectValues(i);
  }, n.objectValues = (a) => n.objectKeys(a).map(function(s) {
    return a[s];
  }), n.objectKeys = typeof Object.keys == "function" ? (a) => Object.keys(a) : (a) => {
    const s = [];
    for (const i in a)
      Object.prototype.hasOwnProperty.call(a, i) && s.push(i);
    return s;
  }, n.find = (a, s) => {
    for (const i of a)
      if (s(i))
        return i;
  }, n.isInteger = typeof Number.isInteger == "function" ? (a) => Number.isInteger(a) : (a) => typeof a == "number" && Number.isFinite(a) && Math.floor(a) === a;
  function r(a, s = " | ") {
    return a.map((i) => typeof i == "string" ? `'${i}'` : i).join(s);
  }
  n.joinValues = r, n.jsonStringifyReplacer = (a, s) => typeof s == "bigint" ? s.toString() : s;
})(x || (x = {}));
var tt;
(function(n) {
  n.mergeShapes = (e, t) => ({
    ...e,
    ...t
    // second overwrites first
  });
})(tt || (tt = {}));
const p = x.arrayToEnum([
  "string",
  "nan",
  "number",
  "integer",
  "float",
  "boolean",
  "date",
  "bigint",
  "symbol",
  "function",
  "undefined",
  "null",
  "array",
  "object",
  "unknown",
  "promise",
  "void",
  "never",
  "map",
  "set"
]), J = (n) => {
  switch (typeof n) {
    case "undefined":
      return p.undefined;
    case "string":
      return p.string;
    case "number":
      return Number.isNaN(n) ? p.nan : p.number;
    case "boolean":
      return p.boolean;
    case "function":
      return p.function;
    case "bigint":
      return p.bigint;
    case "symbol":
      return p.symbol;
    case "object":
      return Array.isArray(n) ? p.array : n === null ? p.null : n.then && typeof n.then == "function" && n.catch && typeof n.catch == "function" ? p.promise : typeof Map < "u" && n instanceof Map ? p.map : typeof Set < "u" && n instanceof Set ? p.set : typeof Date < "u" && n instanceof Date ? p.date : p.object;
    default:
      return p.unknown;
  }
}, l = x.arrayToEnum([
  "invalid_type",
  "invalid_literal",
  "custom",
  "invalid_union",
  "invalid_union_discriminator",
  "invalid_enum_value",
  "unrecognized_keys",
  "invalid_arguments",
  "invalid_return_type",
  "invalid_date",
  "invalid_string",
  "too_small",
  "too_big",
  "invalid_intersection_types",
  "not_multiple_of",
  "not_finite"
]);
class B extends Error {
  get errors() {
    return this.issues;
  }
  constructor(e) {
    super(), this.issues = [], this.addIssue = (r) => {
      this.issues = [...this.issues, r];
    }, this.addIssues = (r = []) => {
      this.issues = [...this.issues, ...r];
    };
    const t = new.target.prototype;
    Object.setPrototypeOf ? Object.setPrototypeOf(this, t) : this.__proto__ = t, this.name = "ZodError", this.issues = e;
  }
  format(e) {
    const t = e || function(s) {
      return s.message;
    }, r = { _errors: [] }, a = (s) => {
      for (const i of s.issues)
        if (i.code === "invalid_union")
          i.unionErrors.map(a);
        else if (i.code === "invalid_return_type")
          a(i.returnTypeError);
        else if (i.code === "invalid_arguments")
          a(i.argumentsError);
        else if (i.path.length === 0)
          r._errors.push(t(i));
        else {
          let o = r, f = 0;
          for (; f < i.path.length; ) {
            const u = i.path[f];
            f === i.path.length - 1 ? (o[u] = o[u] || { _errors: [] }, o[u]._errors.push(t(i))) : o[u] = o[u] || { _errors: [] }, o = o[u], f++;
          }
        }
    };
    return a(this), r;
  }
  static assert(e) {
    if (!(e instanceof B))
      throw new Error(`Not a ZodError: ${e}`);
  }
  toString() {
    return this.message;
  }
  get message() {
    return JSON.stringify(this.issues, x.jsonStringifyReplacer, 2);
  }
  get isEmpty() {
    return this.issues.length === 0;
  }
  flatten(e = (t) => t.message) {
    const t = {}, r = [];
    for (const a of this.issues)
      if (a.path.length > 0) {
        const s = a.path[0];
        t[s] = t[s] || [], t[s].push(e(a));
      } else
        r.push(e(a));
    return { formErrors: r, fieldErrors: t };
  }
  get formErrors() {
    return this.flatten();
  }
}
B.create = (n) => new B(n);
const Ne = (n, e) => {
  let t;
  switch (n.code) {
    case l.invalid_type:
      n.received === p.undefined ? t = "Required" : t = `Expected ${n.expected}, received ${n.received}`;
      break;
    case l.invalid_literal:
      t = `Invalid literal value, expected ${JSON.stringify(n.expected, x.jsonStringifyReplacer)}`;
      break;
    case l.unrecognized_keys:
      t = `Unrecognized key(s) in object: ${x.joinValues(n.keys, ", ")}`;
      break;
    case l.invalid_union:
      t = "Invalid input";
      break;
    case l.invalid_union_discriminator:
      t = `Invalid discriminator value. Expected ${x.joinValues(n.options)}`;
      break;
    case l.invalid_enum_value:
      t = `Invalid enum value. Expected ${x.joinValues(n.options)}, received '${n.received}'`;
      break;
    case l.invalid_arguments:
      t = "Invalid function arguments";
      break;
    case l.invalid_return_type:
      t = "Invalid function return type";
      break;
    case l.invalid_date:
      t = "Invalid date";
      break;
    case l.invalid_string:
      typeof n.validation == "object" ? "includes" in n.validation ? (t = `Invalid input: must include "${n.validation.includes}"`, typeof n.validation.position == "number" && (t = `${t} at one or more positions greater than or equal to ${n.validation.position}`)) : "startsWith" in n.validation ? t = `Invalid input: must start with "${n.validation.startsWith}"` : "endsWith" in n.validation ? t = `Invalid input: must end with "${n.validation.endsWith}"` : x.assertNever(n.validation) : n.validation !== "regex" ? t = `Invalid ${n.validation}` : t = "Invalid";
      break;
    case l.too_small:
      n.type === "array" ? t = `Array must contain ${n.exact ? "exactly" : n.inclusive ? "at least" : "more than"} ${n.minimum} element(s)` : n.type === "string" ? t = `String must contain ${n.exact ? "exactly" : n.inclusive ? "at least" : "over"} ${n.minimum} character(s)` : n.type === "number" ? t = `Number must be ${n.exact ? "exactly equal to " : n.inclusive ? "greater than or equal to " : "greater than "}${n.minimum}` : n.type === "bigint" ? t = `Number must be ${n.exact ? "exactly equal to " : n.inclusive ? "greater than or equal to " : "greater than "}${n.minimum}` : n.type === "date" ? t = `Date must be ${n.exact ? "exactly equal to " : n.inclusive ? "greater than or equal to " : "greater than "}${new Date(Number(n.minimum))}` : t = "Invalid input";
      break;
    case l.too_big:
      n.type === "array" ? t = `Array must contain ${n.exact ? "exactly" : n.inclusive ? "at most" : "less than"} ${n.maximum} element(s)` : n.type === "string" ? t = `String must contain ${n.exact ? "exactly" : n.inclusive ? "at most" : "under"} ${n.maximum} character(s)` : n.type === "number" ? t = `Number must be ${n.exact ? "exactly" : n.inclusive ? "less than or equal to" : "less than"} ${n.maximum}` : n.type === "bigint" ? t = `BigInt must be ${n.exact ? "exactly" : n.inclusive ? "less than or equal to" : "less than"} ${n.maximum}` : n.type === "date" ? t = `Date must be ${n.exact ? "exactly" : n.inclusive ? "smaller than or equal to" : "smaller than"} ${new Date(Number(n.maximum))}` : t = "Invalid input";
      break;
    case l.custom:
      t = "Invalid input";
      break;
    case l.invalid_intersection_types:
      t = "Intersection results could not be merged";
      break;
    case l.not_multiple_of:
      t = `Number must be a multiple of ${n.multipleOf}`;
      break;
    case l.not_finite:
      t = "Number must be finite";
      break;
    default:
      t = e.defaultError, x.assertNever(n);
  }
  return { message: t };
};
let kn = Ne;
function Sn() {
  return kn;
}
const Tn = (n) => {
  const { data: e, path: t, errorMaps: r, issueData: a } = n, s = [...t, ...a.path || []], i = {
    ...a,
    path: s
  };
  if (a.message !== void 0)
    return {
      ...a,
      path: s,
      message: a.message
    };
  let o = "";
  const f = r.filter((u) => !!u).slice().reverse();
  for (const u of f)
    o = u(i, { data: e, defaultError: o }).message;
  return {
    ...a,
    path: s,
    message: o
  };
};
function d(n, e) {
  const t = Sn(), r = Tn({
    issueData: e,
    data: n.data,
    path: n.path,
    errorMaps: [
      n.common.contextualErrorMap,
      // contextual error map is first priority
      n.schemaErrorMap,
      // then schema-bound map if available
      t,
      // then global override map
      t === Ne ? void 0 : Ne
      // then global default map
    ].filter((a) => !!a)
  });
  n.common.issues.push(r);
}
class O {
  constructor() {
    this.value = "valid";
  }
  dirty() {
    this.value === "valid" && (this.value = "dirty");
  }
  abort() {
    this.value !== "aborted" && (this.value = "aborted");
  }
  static mergeArray(e, t) {
    const r = [];
    for (const a of t) {
      if (a.status === "aborted")
        return y;
      a.status === "dirty" && e.dirty(), r.push(a.value);
    }
    return { status: e.value, value: r };
  }
  static async mergeObjectAsync(e, t) {
    const r = [];
    for (const a of t) {
      const s = await a.key, i = await a.value;
      r.push({
        key: s,
        value: i
      });
    }
    return O.mergeObjectSync(e, r);
  }
  static mergeObjectSync(e, t) {
    const r = {};
    for (const a of t) {
      const { key: s, value: i } = a;
      if (s.status === "aborted" || i.status === "aborted")
        return y;
      s.status === "dirty" && e.dirty(), i.status === "dirty" && e.dirty(), s.value !== "__proto__" && (typeof i.value < "u" || a.alwaysSet) && (r[s.value] = i.value);
    }
    return { status: e.value, value: r };
  }
}
const y = Object.freeze({
  status: "aborted"
}), oe = (n) => ({ status: "dirty", value: n }), Z = (n) => ({ status: "valid", value: n }), nt = (n) => n.status === "aborted", rt = (n) => n.status === "dirty", re = (n) => n.status === "valid", de = (n) => typeof Promise < "u" && n instanceof Promise;
var h;
(function(n) {
  n.errToObj = (e) => typeof e == "string" ? { message: e } : e || {}, n.toString = (e) => typeof e == "string" ? e : e?.message;
})(h || (h = {}));
class M {
  constructor(e, t, r, a) {
    this._cachedPath = [], this.parent = e, this.data = t, this._path = r, this._key = a;
  }
  get path() {
    return this._cachedPath.length || (Array.isArray(this._key) ? this._cachedPath.push(...this._path, ...this._key) : this._cachedPath.push(...this._path, this._key)), this._cachedPath;
  }
}
const at = (n, e) => {
  if (re(e))
    return { success: !0, data: e.value };
  if (!n.common.issues.length)
    throw new Error("Validation failed but no issues detected.");
  return {
    success: !1,
    get error() {
      if (this._error)
        return this._error;
      const t = new B(n.common.issues);
      return this._error = t, this._error;
    }
  };
};
function _(n) {
  if (!n)
    return {};
  const { errorMap: e, invalid_type_error: t, required_error: r, description: a } = n;
  if (e && (t || r))
    throw new Error(`Can't use "invalid_type_error" or "required_error" in conjunction with custom error map.`);
  return e ? { errorMap: e, description: a } : { errorMap: (i, o) => {
    const { message: f } = n;
    return i.code === "invalid_enum_value" ? { message: f ?? o.defaultError } : typeof o.data > "u" ? { message: f ?? r ?? o.defaultError } : i.code !== "invalid_type" ? { message: o.defaultError } : { message: f ?? t ?? o.defaultError };
  }, description: a };
}
class b {
  get description() {
    return this._def.description;
  }
  _getType(e) {
    return J(e.data);
  }
  _getOrReturnCtx(e, t) {
    return t || {
      common: e.parent.common,
      data: e.data,
      parsedType: J(e.data),
      schemaErrorMap: this._def.errorMap,
      path: e.path,
      parent: e.parent
    };
  }
  _processInputParams(e) {
    return {
      status: new O(),
      ctx: {
        common: e.parent.common,
        data: e.data,
        parsedType: J(e.data),
        schemaErrorMap: this._def.errorMap,
        path: e.path,
        parent: e.parent
      }
    };
  }
  _parseSync(e) {
    const t = this._parse(e);
    if (de(t))
      throw new Error("Synchronous parse encountered promise.");
    return t;
  }
  _parseAsync(e) {
    const t = this._parse(e);
    return Promise.resolve(t);
  }
  parse(e, t) {
    const r = this.safeParse(e, t);
    if (r.success)
      return r.data;
    throw r.error;
  }
  safeParse(e, t) {
    const r = {
      common: {
        issues: [],
        async: t?.async ?? !1,
        contextualErrorMap: t?.errorMap
      },
      path: t?.path || [],
      schemaErrorMap: this._def.errorMap,
      parent: null,
      data: e,
      parsedType: J(e)
    }, a = this._parseSync({ data: e, path: r.path, parent: r });
    return at(r, a);
  }
  "~validate"(e) {
    const t = {
      common: {
        issues: [],
        async: !!this["~standard"].async
      },
      path: [],
      schemaErrorMap: this._def.errorMap,
      parent: null,
      data: e,
      parsedType: J(e)
    };
    if (!this["~standard"].async)
      try {
        const r = this._parseSync({ data: e, path: [], parent: t });
        return re(r) ? {
          value: r.value
        } : {
          issues: t.common.issues
        };
      } catch (r) {
        r?.message?.toLowerCase()?.includes("encountered") && (this["~standard"].async = !0), t.common = {
          issues: [],
          async: !0
        };
      }
    return this._parseAsync({ data: e, path: [], parent: t }).then((r) => re(r) ? {
      value: r.value
    } : {
      issues: t.common.issues
    });
  }
  async parseAsync(e, t) {
    const r = await this.safeParseAsync(e, t);
    if (r.success)
      return r.data;
    throw r.error;
  }
  async safeParseAsync(e, t) {
    const r = {
      common: {
        issues: [],
        contextualErrorMap: t?.errorMap,
        async: !0
      },
      path: t?.path || [],
      schemaErrorMap: this._def.errorMap,
      parent: null,
      data: e,
      parsedType: J(e)
    }, a = this._parse({ data: e, path: r.path, parent: r }), s = await (de(a) ? a : Promise.resolve(a));
    return at(r, s);
  }
  refine(e, t) {
    const r = (a) => typeof t == "string" || typeof t > "u" ? { message: t } : typeof t == "function" ? t(a) : t;
    return this._refinement((a, s) => {
      const i = e(a), o = () => s.addIssue({
        code: l.custom,
        ...r(a)
      });
      return typeof Promise < "u" && i instanceof Promise ? i.then((f) => f ? !0 : (o(), !1)) : i ? !0 : (o(), !1);
    });
  }
  refinement(e, t) {
    return this._refinement((r, a) => e(r) ? !0 : (a.addIssue(typeof t == "function" ? t(r, a) : t), !1));
  }
  _refinement(e) {
    return new X({
      schema: this,
      typeName: v.ZodEffects,
      effect: { type: "refinement", refinement: e }
    });
  }
  superRefine(e) {
    return this._refinement(e);
  }
  constructor(e) {
    this.spa = this.safeParseAsync, this._def = e, this.parse = this.parse.bind(this), this.safeParse = this.safeParse.bind(this), this.parseAsync = this.parseAsync.bind(this), this.safeParseAsync = this.safeParseAsync.bind(this), this.spa = this.spa.bind(this), this.refine = this.refine.bind(this), this.refinement = this.refinement.bind(this), this.superRefine = this.superRefine.bind(this), this.optional = this.optional.bind(this), this.nullable = this.nullable.bind(this), this.nullish = this.nullish.bind(this), this.array = this.array.bind(this), this.promise = this.promise.bind(this), this.or = this.or.bind(this), this.and = this.and.bind(this), this.transform = this.transform.bind(this), this.brand = this.brand.bind(this), this.default = this.default.bind(this), this.catch = this.catch.bind(this), this.describe = this.describe.bind(this), this.pipe = this.pipe.bind(this), this.readonly = this.readonly.bind(this), this.isNullable = this.isNullable.bind(this), this.isOptional = this.isOptional.bind(this), this["~standard"] = {
      version: 1,
      vendor: "zod",
      validate: (t) => this["~validate"](t)
    };
  }
  optional() {
    return z.create(this, this._def);
  }
  nullable() {
    return ee.create(this, this._def);
  }
  nullish() {
    return this.nullable().optional();
  }
  array() {
    return P.create(this);
  }
  promise() {
    return ye.create(this, this._def);
  }
  or(e) {
    return pe.create([this, e], this._def);
  }
  and(e) {
    return he.create(this, e, this._def);
  }
  transform(e) {
    return new X({
      ..._(this._def),
      schema: this,
      typeName: v.ZodEffects,
      effect: { type: "transform", transform: e }
    });
  }
  default(e) {
    const t = typeof e == "function" ? e : () => e;
    return new ve({
      ..._(this._def),
      innerType: this,
      defaultValue: t,
      typeName: v.ZodDefault
    });
  }
  brand() {
    return new Et({
      typeName: v.ZodBranded,
      type: this,
      ..._(this._def)
    });
  }
  catch(e) {
    const t = typeof e == "function" ? e : () => e;
    return new _e({
      ..._(this._def),
      innerType: this,
      catchValue: t,
      typeName: v.ZodCatch
    });
  }
  describe(e) {
    const t = this.constructor;
    return new t({
      ...this._def,
      description: e
    });
  }
  pipe(e) {
    return ze.create(this, e);
  }
  readonly() {
    return be.create(this);
  }
  isOptional() {
    return this.safeParse(void 0).success;
  }
  isNullable() {
    return this.safeParse(null).success;
  }
}
const jn = /^c[^\s-]{8,}$/i, An = /^[0-9a-z]+$/, Cn = /^[0-9A-HJKMNP-TV-Z]{26}$/i, On = /^[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12}$/i, In = /^[a-z0-9_-]{21}$/i, En = /^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]*$/, Nn = /^[-+]?P(?!$)(?:(?:[-+]?\d+Y)|(?:[-+]?\d+[.,]\d+Y$))?(?:(?:[-+]?\d+M)|(?:[-+]?\d+[.,]\d+M$))?(?:(?:[-+]?\d+W)|(?:[-+]?\d+[.,]\d+W$))?(?:(?:[-+]?\d+D)|(?:[-+]?\d+[.,]\d+D$))?(?:T(?=[\d+-])(?:(?:[-+]?\d+H)|(?:[-+]?\d+[.,]\d+H$))?(?:(?:[-+]?\d+M)|(?:[-+]?\d+[.,]\d+M$))?(?:[-+]?\d+(?:[.,]\d+)?S)?)??$/, Rn = /^(?!\.)(?!.*\.\.)([A-Z0-9_'+\-\.]*)[A-Z0-9_+-]@([A-Z0-9][A-Z0-9\-]*\.)+[A-Z]{2,}$/i, Ln = "^(\\p{Extended_Pictographic}|\\p{Emoji_Component})+$";
let Ce;
const Zn = /^(?:(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])$/, Pn = /^(?:(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\/(3[0-2]|[12]?[0-9])$/, $n = /^(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))$/, Mn = /^(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))\/(12[0-8]|1[01][0-9]|[1-9]?[0-9])$/, Dn = /^([0-9a-zA-Z+/]{4})*(([0-9a-zA-Z+/]{2}==)|([0-9a-zA-Z+/]{3}=))?$/, Un = /^([0-9a-zA-Z-_]{4})*(([0-9a-zA-Z-_]{2}(==)?)|([0-9a-zA-Z-_]{3}(=)?))?$/, Ct = "((\\d\\d[2468][048]|\\d\\d[13579][26]|\\d\\d0[48]|[02468][048]00|[13579][26]00)-02-29|\\d{4}-((0[13578]|1[02])-(0[1-9]|[12]\\d|3[01])|(0[469]|11)-(0[1-9]|[12]\\d|30)|(02)-(0[1-9]|1\\d|2[0-8])))", qn = new RegExp(`^${Ct}$`);
function Ot(n) {
  let e = "[0-5]\\d";
  n.precision ? e = `${e}\\.\\d{${n.precision}}` : n.precision == null && (e = `${e}(\\.\\d+)?`);
  const t = n.precision ? "+" : "?";
  return `([01]\\d|2[0-3]):[0-5]\\d(:${e})${t}`;
}
function Vn(n) {
  return new RegExp(`^${Ot(n)}$`);
}
function Fn(n) {
  let e = `${Ct}T${Ot(n)}`;
  const t = [];
  return t.push(n.local ? "Z?" : "Z"), n.offset && t.push("([+-]\\d{2}:?\\d{2})"), e = `${e}(${t.join("|")})`, new RegExp(`^${e}$`);
}
function zn(n, e) {
  return !!((e === "v4" || !e) && Zn.test(n) || (e === "v6" || !e) && $n.test(n));
}
function Bn(n, e) {
  if (!En.test(n))
    return !1;
  try {
    const [t] = n.split(".");
    if (!t)
      return !1;
    const r = t.replace(/-/g, "+").replace(/_/g, "/").padEnd(t.length + (4 - t.length % 4) % 4, "="), a = JSON.parse(atob(r));
    return !(typeof a != "object" || a === null || "typ" in a && a?.typ !== "JWT" || !a.alg || e && a.alg !== e);
  } catch {
    return !1;
  }
}
function Jn(n, e) {
  return !!((e === "v4" || !e) && Pn.test(n) || (e === "v6" || !e) && Mn.test(n));
}
class F extends b {
  _parse(e) {
    if (this._def.coerce && (e.data = String(e.data)), this._getType(e) !== p.string) {
      const s = this._getOrReturnCtx(e);
      return d(s, {
        code: l.invalid_type,
        expected: p.string,
        received: s.parsedType
      }), y;
    }
    const r = new O();
    let a;
    for (const s of this._def.checks)
      if (s.kind === "min")
        e.data.length < s.value && (a = this._getOrReturnCtx(e, a), d(a, {
          code: l.too_small,
          minimum: s.value,
          type: "string",
          inclusive: !0,
          exact: !1,
          message: s.message
        }), r.dirty());
      else if (s.kind === "max")
        e.data.length > s.value && (a = this._getOrReturnCtx(e, a), d(a, {
          code: l.too_big,
          maximum: s.value,
          type: "string",
          inclusive: !0,
          exact: !1,
          message: s.message
        }), r.dirty());
      else if (s.kind === "length") {
        const i = e.data.length > s.value, o = e.data.length < s.value;
        (i || o) && (a = this._getOrReturnCtx(e, a), i ? d(a, {
          code: l.too_big,
          maximum: s.value,
          type: "string",
          inclusive: !0,
          exact: !0,
          message: s.message
        }) : o && d(a, {
          code: l.too_small,
          minimum: s.value,
          type: "string",
          inclusive: !0,
          exact: !0,
          message: s.message
        }), r.dirty());
      } else if (s.kind === "email")
        Rn.test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
          validation: "email",
          code: l.invalid_string,
          message: s.message
        }), r.dirty());
      else if (s.kind === "emoji")
        Ce || (Ce = new RegExp(Ln, "u")), Ce.test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
          validation: "emoji",
          code: l.invalid_string,
          message: s.message
        }), r.dirty());
      else if (s.kind === "uuid")
        On.test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
          validation: "uuid",
          code: l.invalid_string,
          message: s.message
        }), r.dirty());
      else if (s.kind === "nanoid")
        In.test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
          validation: "nanoid",
          code: l.invalid_string,
          message: s.message
        }), r.dirty());
      else if (s.kind === "cuid")
        jn.test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
          validation: "cuid",
          code: l.invalid_string,
          message: s.message
        }), r.dirty());
      else if (s.kind === "cuid2")
        An.test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
          validation: "cuid2",
          code: l.invalid_string,
          message: s.message
        }), r.dirty());
      else if (s.kind === "ulid")
        Cn.test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
          validation: "ulid",
          code: l.invalid_string,
          message: s.message
        }), r.dirty());
      else if (s.kind === "url")
        try {
          new URL(e.data);
        } catch {
          a = this._getOrReturnCtx(e, a), d(a, {
            validation: "url",
            code: l.invalid_string,
            message: s.message
          }), r.dirty();
        }
      else s.kind === "regex" ? (s.regex.lastIndex = 0, s.regex.test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
        validation: "regex",
        code: l.invalid_string,
        message: s.message
      }), r.dirty())) : s.kind === "trim" ? e.data = e.data.trim() : s.kind === "includes" ? e.data.includes(s.value, s.position) || (a = this._getOrReturnCtx(e, a), d(a, {
        code: l.invalid_string,
        validation: { includes: s.value, position: s.position },
        message: s.message
      }), r.dirty()) : s.kind === "toLowerCase" ? e.data = e.data.toLowerCase() : s.kind === "toUpperCase" ? e.data = e.data.toUpperCase() : s.kind === "startsWith" ? e.data.startsWith(s.value) || (a = this._getOrReturnCtx(e, a), d(a, {
        code: l.invalid_string,
        validation: { startsWith: s.value },
        message: s.message
      }), r.dirty()) : s.kind === "endsWith" ? e.data.endsWith(s.value) || (a = this._getOrReturnCtx(e, a), d(a, {
        code: l.invalid_string,
        validation: { endsWith: s.value },
        message: s.message
      }), r.dirty()) : s.kind === "datetime" ? Fn(s).test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
        code: l.invalid_string,
        validation: "datetime",
        message: s.message
      }), r.dirty()) : s.kind === "date" ? qn.test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
        code: l.invalid_string,
        validation: "date",
        message: s.message
      }), r.dirty()) : s.kind === "time" ? Vn(s).test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
        code: l.invalid_string,
        validation: "time",
        message: s.message
      }), r.dirty()) : s.kind === "duration" ? Nn.test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
        validation: "duration",
        code: l.invalid_string,
        message: s.message
      }), r.dirty()) : s.kind === "ip" ? zn(e.data, s.version) || (a = this._getOrReturnCtx(e, a), d(a, {
        validation: "ip",
        code: l.invalid_string,
        message: s.message
      }), r.dirty()) : s.kind === "jwt" ? Bn(e.data, s.alg) || (a = this._getOrReturnCtx(e, a), d(a, {
        validation: "jwt",
        code: l.invalid_string,
        message: s.message
      }), r.dirty()) : s.kind === "cidr" ? Jn(e.data, s.version) || (a = this._getOrReturnCtx(e, a), d(a, {
        validation: "cidr",
        code: l.invalid_string,
        message: s.message
      }), r.dirty()) : s.kind === "base64" ? Dn.test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
        validation: "base64",
        code: l.invalid_string,
        message: s.message
      }), r.dirty()) : s.kind === "base64url" ? Un.test(e.data) || (a = this._getOrReturnCtx(e, a), d(a, {
        validation: "base64url",
        code: l.invalid_string,
        message: s.message
      }), r.dirty()) : x.assertNever(s);
    return { status: r.value, value: e.data };
  }
  _regex(e, t, r) {
    return this.refinement((a) => e.test(a), {
      validation: t,
      code: l.invalid_string,
      ...h.errToObj(r)
    });
  }
  _addCheck(e) {
    return new F({
      ...this._def,
      checks: [...this._def.checks, e]
    });
  }
  email(e) {
    return this._addCheck({ kind: "email", ...h.errToObj(e) });
  }
  url(e) {
    return this._addCheck({ kind: "url", ...h.errToObj(e) });
  }
  emoji(e) {
    return this._addCheck({ kind: "emoji", ...h.errToObj(e) });
  }
  uuid(e) {
    return this._addCheck({ kind: "uuid", ...h.errToObj(e) });
  }
  nanoid(e) {
    return this._addCheck({ kind: "nanoid", ...h.errToObj(e) });
  }
  cuid(e) {
    return this._addCheck({ kind: "cuid", ...h.errToObj(e) });
  }
  cuid2(e) {
    return this._addCheck({ kind: "cuid2", ...h.errToObj(e) });
  }
  ulid(e) {
    return this._addCheck({ kind: "ulid", ...h.errToObj(e) });
  }
  base64(e) {
    return this._addCheck({ kind: "base64", ...h.errToObj(e) });
  }
  base64url(e) {
    return this._addCheck({
      kind: "base64url",
      ...h.errToObj(e)
    });
  }
  jwt(e) {
    return this._addCheck({ kind: "jwt", ...h.errToObj(e) });
  }
  ip(e) {
    return this._addCheck({ kind: "ip", ...h.errToObj(e) });
  }
  cidr(e) {
    return this._addCheck({ kind: "cidr", ...h.errToObj(e) });
  }
  datetime(e) {
    return typeof e == "string" ? this._addCheck({
      kind: "datetime",
      precision: null,
      offset: !1,
      local: !1,
      message: e
    }) : this._addCheck({
      kind: "datetime",
      precision: typeof e?.precision > "u" ? null : e?.precision,
      offset: e?.offset ?? !1,
      local: e?.local ?? !1,
      ...h.errToObj(e?.message)
    });
  }
  date(e) {
    return this._addCheck({ kind: "date", message: e });
  }
  time(e) {
    return typeof e == "string" ? this._addCheck({
      kind: "time",
      precision: null,
      message: e
    }) : this._addCheck({
      kind: "time",
      precision: typeof e?.precision > "u" ? null : e?.precision,
      ...h.errToObj(e?.message)
    });
  }
  duration(e) {
    return this._addCheck({ kind: "duration", ...h.errToObj(e) });
  }
  regex(e, t) {
    return this._addCheck({
      kind: "regex",
      regex: e,
      ...h.errToObj(t)
    });
  }
  includes(e, t) {
    return this._addCheck({
      kind: "includes",
      value: e,
      position: t?.position,
      ...h.errToObj(t?.message)
    });
  }
  startsWith(e, t) {
    return this._addCheck({
      kind: "startsWith",
      value: e,
      ...h.errToObj(t)
    });
  }
  endsWith(e, t) {
    return this._addCheck({
      kind: "endsWith",
      value: e,
      ...h.errToObj(t)
    });
  }
  min(e, t) {
    return this._addCheck({
      kind: "min",
      value: e,
      ...h.errToObj(t)
    });
  }
  max(e, t) {
    return this._addCheck({
      kind: "max",
      value: e,
      ...h.errToObj(t)
    });
  }
  length(e, t) {
    return this._addCheck({
      kind: "length",
      value: e,
      ...h.errToObj(t)
    });
  }
  /**
   * Equivalent to `.min(1)`
   */
  nonempty(e) {
    return this.min(1, h.errToObj(e));
  }
  trim() {
    return new F({
      ...this._def,
      checks: [...this._def.checks, { kind: "trim" }]
    });
  }
  toLowerCase() {
    return new F({
      ...this._def,
      checks: [...this._def.checks, { kind: "toLowerCase" }]
    });
  }
  toUpperCase() {
    return new F({
      ...this._def,
      checks: [...this._def.checks, { kind: "toUpperCase" }]
    });
  }
  get isDatetime() {
    return !!this._def.checks.find((e) => e.kind === "datetime");
  }
  get isDate() {
    return !!this._def.checks.find((e) => e.kind === "date");
  }
  get isTime() {
    return !!this._def.checks.find((e) => e.kind === "time");
  }
  get isDuration() {
    return !!this._def.checks.find((e) => e.kind === "duration");
  }
  get isEmail() {
    return !!this._def.checks.find((e) => e.kind === "email");
  }
  get isURL() {
    return !!this._def.checks.find((e) => e.kind === "url");
  }
  get isEmoji() {
    return !!this._def.checks.find((e) => e.kind === "emoji");
  }
  get isUUID() {
    return !!this._def.checks.find((e) => e.kind === "uuid");
  }
  get isNANOID() {
    return !!this._def.checks.find((e) => e.kind === "nanoid");
  }
  get isCUID() {
    return !!this._def.checks.find((e) => e.kind === "cuid");
  }
  get isCUID2() {
    return !!this._def.checks.find((e) => e.kind === "cuid2");
  }
  get isULID() {
    return !!this._def.checks.find((e) => e.kind === "ulid");
  }
  get isIP() {
    return !!this._def.checks.find((e) => e.kind === "ip");
  }
  get isCIDR() {
    return !!this._def.checks.find((e) => e.kind === "cidr");
  }
  get isBase64() {
    return !!this._def.checks.find((e) => e.kind === "base64");
  }
  get isBase64url() {
    return !!this._def.checks.find((e) => e.kind === "base64url");
  }
  get minLength() {
    let e = null;
    for (const t of this._def.checks)
      t.kind === "min" && (e === null || t.value > e) && (e = t.value);
    return e;
  }
  get maxLength() {
    let e = null;
    for (const t of this._def.checks)
      t.kind === "max" && (e === null || t.value < e) && (e = t.value);
    return e;
  }
}
F.create = (n) => new F({
  checks: [],
  typeName: v.ZodString,
  coerce: n?.coerce ?? !1,
  ..._(n)
});
function Wn(n, e) {
  const t = (n.toString().split(".")[1] || "").length, r = (e.toString().split(".")[1] || "").length, a = t > r ? t : r, s = Number.parseInt(n.toFixed(a).replace(".", "")), i = Number.parseInt(e.toFixed(a).replace(".", ""));
  return s % i / 10 ** a;
}
class ae extends b {
  constructor() {
    super(...arguments), this.min = this.gte, this.max = this.lte, this.step = this.multipleOf;
  }
  _parse(e) {
    if (this._def.coerce && (e.data = Number(e.data)), this._getType(e) !== p.number) {
      const s = this._getOrReturnCtx(e);
      return d(s, {
        code: l.invalid_type,
        expected: p.number,
        received: s.parsedType
      }), y;
    }
    let r;
    const a = new O();
    for (const s of this._def.checks)
      s.kind === "int" ? x.isInteger(e.data) || (r = this._getOrReturnCtx(e, r), d(r, {
        code: l.invalid_type,
        expected: "integer",
        received: "float",
        message: s.message
      }), a.dirty()) : s.kind === "min" ? (s.inclusive ? e.data < s.value : e.data <= s.value) && (r = this._getOrReturnCtx(e, r), d(r, {
        code: l.too_small,
        minimum: s.value,
        type: "number",
        inclusive: s.inclusive,
        exact: !1,
        message: s.message
      }), a.dirty()) : s.kind === "max" ? (s.inclusive ? e.data > s.value : e.data >= s.value) && (r = this._getOrReturnCtx(e, r), d(r, {
        code: l.too_big,
        maximum: s.value,
        type: "number",
        inclusive: s.inclusive,
        exact: !1,
        message: s.message
      }), a.dirty()) : s.kind === "multipleOf" ? Wn(e.data, s.value) !== 0 && (r = this._getOrReturnCtx(e, r), d(r, {
        code: l.not_multiple_of,
        multipleOf: s.value,
        message: s.message
      }), a.dirty()) : s.kind === "finite" ? Number.isFinite(e.data) || (r = this._getOrReturnCtx(e, r), d(r, {
        code: l.not_finite,
        message: s.message
      }), a.dirty()) : x.assertNever(s);
    return { status: a.value, value: e.data };
  }
  gte(e, t) {
    return this.setLimit("min", e, !0, h.toString(t));
  }
  gt(e, t) {
    return this.setLimit("min", e, !1, h.toString(t));
  }
  lte(e, t) {
    return this.setLimit("max", e, !0, h.toString(t));
  }
  lt(e, t) {
    return this.setLimit("max", e, !1, h.toString(t));
  }
  setLimit(e, t, r, a) {
    return new ae({
      ...this._def,
      checks: [
        ...this._def.checks,
        {
          kind: e,
          value: t,
          inclusive: r,
          message: h.toString(a)
        }
      ]
    });
  }
  _addCheck(e) {
    return new ae({
      ...this._def,
      checks: [...this._def.checks, e]
    });
  }
  int(e) {
    return this._addCheck({
      kind: "int",
      message: h.toString(e)
    });
  }
  positive(e) {
    return this._addCheck({
      kind: "min",
      value: 0,
      inclusive: !1,
      message: h.toString(e)
    });
  }
  negative(e) {
    return this._addCheck({
      kind: "max",
      value: 0,
      inclusive: !1,
      message: h.toString(e)
    });
  }
  nonpositive(e) {
    return this._addCheck({
      kind: "max",
      value: 0,
      inclusive: !0,
      message: h.toString(e)
    });
  }
  nonnegative(e) {
    return this._addCheck({
      kind: "min",
      value: 0,
      inclusive: !0,
      message: h.toString(e)
    });
  }
  multipleOf(e, t) {
    return this._addCheck({
      kind: "multipleOf",
      value: e,
      message: h.toString(t)
    });
  }
  finite(e) {
    return this._addCheck({
      kind: "finite",
      message: h.toString(e)
    });
  }
  safe(e) {
    return this._addCheck({
      kind: "min",
      inclusive: !0,
      value: Number.MIN_SAFE_INTEGER,
      message: h.toString(e)
    })._addCheck({
      kind: "max",
      inclusive: !0,
      value: Number.MAX_SAFE_INTEGER,
      message: h.toString(e)
    });
  }
  get minValue() {
    let e = null;
    for (const t of this._def.checks)
      t.kind === "min" && (e === null || t.value > e) && (e = t.value);
    return e;
  }
  get maxValue() {
    let e = null;
    for (const t of this._def.checks)
      t.kind === "max" && (e === null || t.value < e) && (e = t.value);
    return e;
  }
  get isInt() {
    return !!this._def.checks.find((e) => e.kind === "int" || e.kind === "multipleOf" && x.isInteger(e.value));
  }
  get isFinite() {
    let e = null, t = null;
    for (const r of this._def.checks) {
      if (r.kind === "finite" || r.kind === "int" || r.kind === "multipleOf")
        return !0;
      r.kind === "min" ? (t === null || r.value > t) && (t = r.value) : r.kind === "max" && (e === null || r.value < e) && (e = r.value);
    }
    return Number.isFinite(t) && Number.isFinite(e);
  }
}
ae.create = (n) => new ae({
  checks: [],
  typeName: v.ZodNumber,
  coerce: n?.coerce || !1,
  ..._(n)
});
class ce extends b {
  constructor() {
    super(...arguments), this.min = this.gte, this.max = this.lte;
  }
  _parse(e) {
    if (this._def.coerce)
      try {
        e.data = BigInt(e.data);
      } catch {
        return this._getInvalidInput(e);
      }
    if (this._getType(e) !== p.bigint)
      return this._getInvalidInput(e);
    let r;
    const a = new O();
    for (const s of this._def.checks)
      s.kind === "min" ? (s.inclusive ? e.data < s.value : e.data <= s.value) && (r = this._getOrReturnCtx(e, r), d(r, {
        code: l.too_small,
        type: "bigint",
        minimum: s.value,
        inclusive: s.inclusive,
        message: s.message
      }), a.dirty()) : s.kind === "max" ? (s.inclusive ? e.data > s.value : e.data >= s.value) && (r = this._getOrReturnCtx(e, r), d(r, {
        code: l.too_big,
        type: "bigint",
        maximum: s.value,
        inclusive: s.inclusive,
        message: s.message
      }), a.dirty()) : s.kind === "multipleOf" ? e.data % s.value !== BigInt(0) && (r = this._getOrReturnCtx(e, r), d(r, {
        code: l.not_multiple_of,
        multipleOf: s.value,
        message: s.message
      }), a.dirty()) : x.assertNever(s);
    return { status: a.value, value: e.data };
  }
  _getInvalidInput(e) {
    const t = this._getOrReturnCtx(e);
    return d(t, {
      code: l.invalid_type,
      expected: p.bigint,
      received: t.parsedType
    }), y;
  }
  gte(e, t) {
    return this.setLimit("min", e, !0, h.toString(t));
  }
  gt(e, t) {
    return this.setLimit("min", e, !1, h.toString(t));
  }
  lte(e, t) {
    return this.setLimit("max", e, !0, h.toString(t));
  }
  lt(e, t) {
    return this.setLimit("max", e, !1, h.toString(t));
  }
  setLimit(e, t, r, a) {
    return new ce({
      ...this._def,
      checks: [
        ...this._def.checks,
        {
          kind: e,
          value: t,
          inclusive: r,
          message: h.toString(a)
        }
      ]
    });
  }
  _addCheck(e) {
    return new ce({
      ...this._def,
      checks: [...this._def.checks, e]
    });
  }
  positive(e) {
    return this._addCheck({
      kind: "min",
      value: BigInt(0),
      inclusive: !1,
      message: h.toString(e)
    });
  }
  negative(e) {
    return this._addCheck({
      kind: "max",
      value: BigInt(0),
      inclusive: !1,
      message: h.toString(e)
    });
  }
  nonpositive(e) {
    return this._addCheck({
      kind: "max",
      value: BigInt(0),
      inclusive: !0,
      message: h.toString(e)
    });
  }
  nonnegative(e) {
    return this._addCheck({
      kind: "min",
      value: BigInt(0),
      inclusive: !0,
      message: h.toString(e)
    });
  }
  multipleOf(e, t) {
    return this._addCheck({
      kind: "multipleOf",
      value: e,
      message: h.toString(t)
    });
  }
  get minValue() {
    let e = null;
    for (const t of this._def.checks)
      t.kind === "min" && (e === null || t.value > e) && (e = t.value);
    return e;
  }
  get maxValue() {
    let e = null;
    for (const t of this._def.checks)
      t.kind === "max" && (e === null || t.value < e) && (e = t.value);
    return e;
  }
}
ce.create = (n) => new ce({
  checks: [],
  typeName: v.ZodBigInt,
  coerce: n?.coerce ?? !1,
  ..._(n)
});
class Re extends b {
  _parse(e) {
    if (this._def.coerce && (e.data = !!e.data), this._getType(e) !== p.boolean) {
      const r = this._getOrReturnCtx(e);
      return d(r, {
        code: l.invalid_type,
        expected: p.boolean,
        received: r.parsedType
      }), y;
    }
    return Z(e.data);
  }
}
Re.create = (n) => new Re({
  typeName: v.ZodBoolean,
  coerce: n?.coerce || !1,
  ..._(n)
});
class fe extends b {
  _parse(e) {
    if (this._def.coerce && (e.data = new Date(e.data)), this._getType(e) !== p.date) {
      const s = this._getOrReturnCtx(e);
      return d(s, {
        code: l.invalid_type,
        expected: p.date,
        received: s.parsedType
      }), y;
    }
    if (Number.isNaN(e.data.getTime())) {
      const s = this._getOrReturnCtx(e);
      return d(s, {
        code: l.invalid_date
      }), y;
    }
    const r = new O();
    let a;
    for (const s of this._def.checks)
      s.kind === "min" ? e.data.getTime() < s.value && (a = this._getOrReturnCtx(e, a), d(a, {
        code: l.too_small,
        message: s.message,
        inclusive: !0,
        exact: !1,
        minimum: s.value,
        type: "date"
      }), r.dirty()) : s.kind === "max" ? e.data.getTime() > s.value && (a = this._getOrReturnCtx(e, a), d(a, {
        code: l.too_big,
        message: s.message,
        inclusive: !0,
        exact: !1,
        maximum: s.value,
        type: "date"
      }), r.dirty()) : x.assertNever(s);
    return {
      status: r.value,
      value: new Date(e.data.getTime())
    };
  }
  _addCheck(e) {
    return new fe({
      ...this._def,
      checks: [...this._def.checks, e]
    });
  }
  min(e, t) {
    return this._addCheck({
      kind: "min",
      value: e.getTime(),
      message: h.toString(t)
    });
  }
  max(e, t) {
    return this._addCheck({
      kind: "max",
      value: e.getTime(),
      message: h.toString(t)
    });
  }
  get minDate() {
    let e = null;
    for (const t of this._def.checks)
      t.kind === "min" && (e === null || t.value > e) && (e = t.value);
    return e != null ? new Date(e) : null;
  }
  get maxDate() {
    let e = null;
    for (const t of this._def.checks)
      t.kind === "max" && (e === null || t.value < e) && (e = t.value);
    return e != null ? new Date(e) : null;
  }
}
fe.create = (n) => new fe({
  checks: [],
  coerce: n?.coerce || !1,
  typeName: v.ZodDate,
  ..._(n)
});
class st extends b {
  _parse(e) {
    if (this._getType(e) !== p.symbol) {
      const r = this._getOrReturnCtx(e);
      return d(r, {
        code: l.invalid_type,
        expected: p.symbol,
        received: r.parsedType
      }), y;
    }
    return Z(e.data);
  }
}
st.create = (n) => new st({
  typeName: v.ZodSymbol,
  ..._(n)
});
class Le extends b {
  _parse(e) {
    if (this._getType(e) !== p.undefined) {
      const r = this._getOrReturnCtx(e);
      return d(r, {
        code: l.invalid_type,
        expected: p.undefined,
        received: r.parsedType
      }), y;
    }
    return Z(e.data);
  }
}
Le.create = (n) => new Le({
  typeName: v.ZodUndefined,
  ..._(n)
});
class Ze extends b {
  _parse(e) {
    if (this._getType(e) !== p.null) {
      const r = this._getOrReturnCtx(e);
      return d(r, {
        code: l.invalid_type,
        expected: p.null,
        received: r.parsedType
      }), y;
    }
    return Z(e.data);
  }
}
Ze.create = (n) => new Ze({
  typeName: v.ZodNull,
  ..._(n)
});
class it extends b {
  constructor() {
    super(...arguments), this._any = !0;
  }
  _parse(e) {
    return Z(e.data);
  }
}
it.create = (n) => new it({
  typeName: v.ZodAny,
  ..._(n)
});
class Pe extends b {
  constructor() {
    super(...arguments), this._unknown = !0;
  }
  _parse(e) {
    return Z(e.data);
  }
}
Pe.create = (n) => new Pe({
  typeName: v.ZodUnknown,
  ..._(n)
});
class H extends b {
  _parse(e) {
    const t = this._getOrReturnCtx(e);
    return d(t, {
      code: l.invalid_type,
      expected: p.never,
      received: t.parsedType
    }), y;
  }
}
H.create = (n) => new H({
  typeName: v.ZodNever,
  ..._(n)
});
class ot extends b {
  _parse(e) {
    if (this._getType(e) !== p.undefined) {
      const r = this._getOrReturnCtx(e);
      return d(r, {
        code: l.invalid_type,
        expected: p.void,
        received: r.parsedType
      }), y;
    }
    return Z(e.data);
  }
}
ot.create = (n) => new ot({
  typeName: v.ZodVoid,
  ..._(n)
});
class P extends b {
  _parse(e) {
    const { ctx: t, status: r } = this._processInputParams(e), a = this._def;
    if (t.parsedType !== p.array)
      return d(t, {
        code: l.invalid_type,
        expected: p.array,
        received: t.parsedType
      }), y;
    if (a.exactLength !== null) {
      const i = t.data.length > a.exactLength.value, o = t.data.length < a.exactLength.value;
      (i || o) && (d(t, {
        code: i ? l.too_big : l.too_small,
        minimum: o ? a.exactLength.value : void 0,
        maximum: i ? a.exactLength.value : void 0,
        type: "array",
        inclusive: !0,
        exact: !0,
        message: a.exactLength.message
      }), r.dirty());
    }
    if (a.minLength !== null && t.data.length < a.minLength.value && (d(t, {
      code: l.too_small,
      minimum: a.minLength.value,
      type: "array",
      inclusive: !0,
      exact: !1,
      message: a.minLength.message
    }), r.dirty()), a.maxLength !== null && t.data.length > a.maxLength.value && (d(t, {
      code: l.too_big,
      maximum: a.maxLength.value,
      type: "array",
      inclusive: !0,
      exact: !1,
      message: a.maxLength.message
    }), r.dirty()), t.common.async)
      return Promise.all([...t.data].map((i, o) => a.type._parseAsync(new M(t, i, t.path, o)))).then((i) => O.mergeArray(r, i));
    const s = [...t.data].map((i, o) => a.type._parseSync(new M(t, i, t.path, o)));
    return O.mergeArray(r, s);
  }
  get element() {
    return this._def.type;
  }
  min(e, t) {
    return new P({
      ...this._def,
      minLength: { value: e, message: h.toString(t) }
    });
  }
  max(e, t) {
    return new P({
      ...this._def,
      maxLength: { value: e, message: h.toString(t) }
    });
  }
  length(e, t) {
    return new P({
      ...this._def,
      exactLength: { value: e, message: h.toString(t) }
    });
  }
  nonempty(e) {
    return this.min(1, e);
  }
}
P.create = (n, e) => new P({
  type: n,
  minLength: null,
  maxLength: null,
  exactLength: null,
  typeName: v.ZodArray,
  ..._(e)
});
function ne(n) {
  if (n instanceof T) {
    const e = {};
    for (const t in n.shape) {
      const r = n.shape[t];
      e[t] = z.create(ne(r));
    }
    return new T({
      ...n._def,
      shape: () => e
    });
  } else return n instanceof P ? new P({
    ...n._def,
    type: ne(n.element)
  }) : n instanceof z ? z.create(ne(n.unwrap())) : n instanceof ee ? ee.create(ne(n.unwrap())) : n instanceof K ? K.create(n.items.map((e) => ne(e))) : n;
}
class T extends b {
  constructor() {
    super(...arguments), this._cached = null, this.nonstrict = this.passthrough, this.augment = this.extend;
  }
  _getCached() {
    if (this._cached !== null)
      return this._cached;
    const e = this._def.shape(), t = x.objectKeys(e);
    return this._cached = { shape: e, keys: t }, this._cached;
  }
  _parse(e) {
    if (this._getType(e) !== p.object) {
      const u = this._getOrReturnCtx(e);
      return d(u, {
        code: l.invalid_type,
        expected: p.object,
        received: u.parsedType
      }), y;
    }
    const { status: r, ctx: a } = this._processInputParams(e), { shape: s, keys: i } = this._getCached(), o = [];
    if (!(this._def.catchall instanceof H && this._def.unknownKeys === "strip"))
      for (const u in a.data)
        i.includes(u) || o.push(u);
    const f = [];
    for (const u of i) {
      const m = s[u], A = a.data[u];
      f.push({
        key: { status: "valid", value: u },
        value: m._parse(new M(a, A, a.path, u)),
        alwaysSet: u in a.data
      });
    }
    if (this._def.catchall instanceof H) {
      const u = this._def.unknownKeys;
      if (u === "passthrough")
        for (const m of o)
          f.push({
            key: { status: "valid", value: m },
            value: { status: "valid", value: a.data[m] }
          });
      else if (u === "strict")
        o.length > 0 && (d(a, {
          code: l.unrecognized_keys,
          keys: o
        }), r.dirty());
      else if (u !== "strip") throw new Error("Internal ZodObject error: invalid unknownKeys value.");
    } else {
      const u = this._def.catchall;
      for (const m of o) {
        const A = a.data[m];
        f.push({
          key: { status: "valid", value: m },
          value: u._parse(
            new M(a, A, a.path, m)
            //, ctx.child(key), value, getParsedType(value)
          ),
          alwaysSet: m in a.data
        });
      }
    }
    return a.common.async ? Promise.resolve().then(async () => {
      const u = [];
      for (const m of f) {
        const A = await m.key, S = await m.value;
        u.push({
          key: A,
          value: S,
          alwaysSet: m.alwaysSet
        });
      }
      return u;
    }).then((u) => O.mergeObjectSync(r, u)) : O.mergeObjectSync(r, f);
  }
  get shape() {
    return this._def.shape();
  }
  strict(e) {
    return h.errToObj, new T({
      ...this._def,
      unknownKeys: "strict",
      ...e !== void 0 ? {
        errorMap: (t, r) => {
          const a = this._def.errorMap?.(t, r).message ?? r.defaultError;
          return t.code === "unrecognized_keys" ? {
            message: h.errToObj(e).message ?? a
          } : {
            message: a
          };
        }
      } : {}
    });
  }
  strip() {
    return new T({
      ...this._def,
      unknownKeys: "strip"
    });
  }
  passthrough() {
    return new T({
      ...this._def,
      unknownKeys: "passthrough"
    });
  }
  // const AugmentFactory =
  //   <Def extends ZodObjectDef>(def: Def) =>
  //   <Augmentation extends ZodRawShape>(
  //     augmentation: Augmentation
  //   ): ZodObject<
  //     extendShape<ReturnType<Def["shape"]>, Augmentation>,
  //     Def["unknownKeys"],
  //     Def["catchall"]
  //   > => {
  //     return new ZodObject({
  //       ...def,
  //       shape: () => ({
  //         ...def.shape(),
  //         ...augmentation,
  //       }),
  //     }) as any;
  //   };
  extend(e) {
    return new T({
      ...this._def,
      shape: () => ({
        ...this._def.shape(),
        ...e
      })
    });
  }
  /**
   * Prior to zod@1.0.12 there was a bug in the
   * inferred type of merged objects. Please
   * upgrade if you are experiencing issues.
   */
  merge(e) {
    return new T({
      unknownKeys: e._def.unknownKeys,
      catchall: e._def.catchall,
      shape: () => ({
        ...this._def.shape(),
        ...e._def.shape()
      }),
      typeName: v.ZodObject
    });
  }
  // merge<
  //   Incoming extends AnyZodObject,
  //   Augmentation extends Incoming["shape"],
  //   NewOutput extends {
  //     [k in keyof Augmentation | keyof Output]: k extends keyof Augmentation
  //       ? Augmentation[k]["_output"]
  //       : k extends keyof Output
  //       ? Output[k]
  //       : never;
  //   },
  //   NewInput extends {
  //     [k in keyof Augmentation | keyof Input]: k extends keyof Augmentation
  //       ? Augmentation[k]["_input"]
  //       : k extends keyof Input
  //       ? Input[k]
  //       : never;
  //   }
  // >(
  //   merging: Incoming
  // ): ZodObject<
  //   extendShape<T, ReturnType<Incoming["_def"]["shape"]>>,
  //   Incoming["_def"]["unknownKeys"],
  //   Incoming["_def"]["catchall"],
  //   NewOutput,
  //   NewInput
  // > {
  //   const merged: any = new ZodObject({
  //     unknownKeys: merging._def.unknownKeys,
  //     catchall: merging._def.catchall,
  //     shape: () =>
  //       objectUtil.mergeShapes(this._def.shape(), merging._def.shape()),
  //     typeName: ZodFirstPartyTypeKind.ZodObject,
  //   }) as any;
  //   return merged;
  // }
  setKey(e, t) {
    return this.augment({ [e]: t });
  }
  // merge<Incoming extends AnyZodObject>(
  //   merging: Incoming
  // ): //ZodObject<T & Incoming["_shape"], UnknownKeys, Catchall> = (merging) => {
  // ZodObject<
  //   extendShape<T, ReturnType<Incoming["_def"]["shape"]>>,
  //   Incoming["_def"]["unknownKeys"],
  //   Incoming["_def"]["catchall"]
  // > {
  //   // const mergedShape = objectUtil.mergeShapes(
  //   //   this._def.shape(),
  //   //   merging._def.shape()
  //   // );
  //   const merged: any = new ZodObject({
  //     unknownKeys: merging._def.unknownKeys,
  //     catchall: merging._def.catchall,
  //     shape: () =>
  //       objectUtil.mergeShapes(this._def.shape(), merging._def.shape()),
  //     typeName: ZodFirstPartyTypeKind.ZodObject,
  //   }) as any;
  //   return merged;
  // }
  catchall(e) {
    return new T({
      ...this._def,
      catchall: e
    });
  }
  pick(e) {
    const t = {};
    for (const r of x.objectKeys(e))
      e[r] && this.shape[r] && (t[r] = this.shape[r]);
    return new T({
      ...this._def,
      shape: () => t
    });
  }
  omit(e) {
    const t = {};
    for (const r of x.objectKeys(this.shape))
      e[r] || (t[r] = this.shape[r]);
    return new T({
      ...this._def,
      shape: () => t
    });
  }
  /**
   * @deprecated
   */
  deepPartial() {
    return ne(this);
  }
  partial(e) {
    const t = {};
    for (const r of x.objectKeys(this.shape)) {
      const a = this.shape[r];
      e && !e[r] ? t[r] = a : t[r] = a.optional();
    }
    return new T({
      ...this._def,
      shape: () => t
    });
  }
  required(e) {
    const t = {};
    for (const r of x.objectKeys(this.shape))
      if (e && !e[r])
        t[r] = this.shape[r];
      else {
        let s = this.shape[r];
        for (; s instanceof z; )
          s = s._def.innerType;
        t[r] = s;
      }
    return new T({
      ...this._def,
      shape: () => t
    });
  }
  keyof() {
    return It(x.objectKeys(this.shape));
  }
}
T.create = (n, e) => new T({
  shape: () => n,
  unknownKeys: "strip",
  catchall: H.create(),
  typeName: v.ZodObject,
  ..._(e)
});
T.strictCreate = (n, e) => new T({
  shape: () => n,
  unknownKeys: "strict",
  catchall: H.create(),
  typeName: v.ZodObject,
  ..._(e)
});
T.lazycreate = (n, e) => new T({
  shape: n,
  unknownKeys: "strip",
  catchall: H.create(),
  typeName: v.ZodObject,
  ..._(e)
});
class pe extends b {
  _parse(e) {
    const { ctx: t } = this._processInputParams(e), r = this._def.options;
    function a(s) {
      for (const o of s)
        if (o.result.status === "valid")
          return o.result;
      for (const o of s)
        if (o.result.status === "dirty")
          return t.common.issues.push(...o.ctx.common.issues), o.result;
      const i = s.map((o) => new B(o.ctx.common.issues));
      return d(t, {
        code: l.invalid_union,
        unionErrors: i
      }), y;
    }
    if (t.common.async)
      return Promise.all(r.map(async (s) => {
        const i = {
          ...t,
          common: {
            ...t.common,
            issues: []
          },
          parent: null
        };
        return {
          result: await s._parseAsync({
            data: t.data,
            path: t.path,
            parent: i
          }),
          ctx: i
        };
      })).then(a);
    {
      let s;
      const i = [];
      for (const f of r) {
        const u = {
          ...t,
          common: {
            ...t.common,
            issues: []
          },
          parent: null
        }, m = f._parseSync({
          data: t.data,
          path: t.path,
          parent: u
        });
        if (m.status === "valid")
          return m;
        m.status === "dirty" && !s && (s = { result: m, ctx: u }), u.common.issues.length && i.push(u.common.issues);
      }
      if (s)
        return t.common.issues.push(...s.ctx.common.issues), s.result;
      const o = i.map((f) => new B(f));
      return d(t, {
        code: l.invalid_union,
        unionErrors: o
      }), y;
    }
  }
  get options() {
    return this._def.options;
  }
}
pe.create = (n, e) => new pe({
  options: n,
  typeName: v.ZodUnion,
  ..._(e)
});
const q = (n) => n instanceof Me ? q(n.schema) : n instanceof X ? q(n.innerType()) : n instanceof ge ? [n.value] : n instanceof Y ? n.options : n instanceof De ? x.objectValues(n.enum) : n instanceof ve ? q(n._def.innerType) : n instanceof Le ? [void 0] : n instanceof Ze ? [null] : n instanceof z ? [void 0, ...q(n.unwrap())] : n instanceof ee ? [null, ...q(n.unwrap())] : n instanceof Et || n instanceof be ? q(n.unwrap()) : n instanceof _e ? q(n._def.innerType) : [];
class Fe extends b {
  _parse(e) {
    const { ctx: t } = this._processInputParams(e);
    if (t.parsedType !== p.object)
      return d(t, {
        code: l.invalid_type,
        expected: p.object,
        received: t.parsedType
      }), y;
    const r = this.discriminator, a = t.data[r], s = this.optionsMap.get(a);
    return s ? t.common.async ? s._parseAsync({
      data: t.data,
      path: t.path,
      parent: t
    }) : s._parseSync({
      data: t.data,
      path: t.path,
      parent: t
    }) : (d(t, {
      code: l.invalid_union_discriminator,
      options: Array.from(this.optionsMap.keys()),
      path: [r]
    }), y);
  }
  get discriminator() {
    return this._def.discriminator;
  }
  get options() {
    return this._def.options;
  }
  get optionsMap() {
    return this._def.optionsMap;
  }
  /**
   * The constructor of the discriminated union schema. Its behaviour is very similar to that of the normal z.union() constructor.
   * However, it only allows a union of objects, all of which need to share a discriminator property. This property must
   * have a different value for each object in the union.
   * @param discriminator the name of the discriminator property
   * @param types an array of object schemas
   * @param params
   */
  static create(e, t, r) {
    const a = /* @__PURE__ */ new Map();
    for (const s of t) {
      const i = q(s.shape[e]);
      if (!i.length)
        throw new Error(`A discriminator value for key \`${e}\` could not be extracted from all schema options`);
      for (const o of i) {
        if (a.has(o))
          throw new Error(`Discriminator property ${String(e)} has duplicate value ${String(o)}`);
        a.set(o, s);
      }
    }
    return new Fe({
      typeName: v.ZodDiscriminatedUnion,
      discriminator: e,
      options: t,
      optionsMap: a,
      ..._(r)
    });
  }
}
function $e(n, e) {
  const t = J(n), r = J(e);
  if (n === e)
    return { valid: !0, data: n };
  if (t === p.object && r === p.object) {
    const a = x.objectKeys(e), s = x.objectKeys(n).filter((o) => a.indexOf(o) !== -1), i = { ...n, ...e };
    for (const o of s) {
      const f = $e(n[o], e[o]);
      if (!f.valid)
        return { valid: !1 };
      i[o] = f.data;
    }
    return { valid: !0, data: i };
  } else if (t === p.array && r === p.array) {
    if (n.length !== e.length)
      return { valid: !1 };
    const a = [];
    for (let s = 0; s < n.length; s++) {
      const i = n[s], o = e[s], f = $e(i, o);
      if (!f.valid)
        return { valid: !1 };
      a.push(f.data);
    }
    return { valid: !0, data: a };
  } else return t === p.date && r === p.date && +n == +e ? { valid: !0, data: n } : { valid: !1 };
}
class he extends b {
  _parse(e) {
    const { status: t, ctx: r } = this._processInputParams(e), a = (s, i) => {
      if (nt(s) || nt(i))
        return y;
      const o = $e(s.value, i.value);
      return o.valid ? ((rt(s) || rt(i)) && t.dirty(), { status: t.value, value: o.data }) : (d(r, {
        code: l.invalid_intersection_types
      }), y);
    };
    return r.common.async ? Promise.all([
      this._def.left._parseAsync({
        data: r.data,
        path: r.path,
        parent: r
      }),
      this._def.right._parseAsync({
        data: r.data,
        path: r.path,
        parent: r
      })
    ]).then(([s, i]) => a(s, i)) : a(this._def.left._parseSync({
      data: r.data,
      path: r.path,
      parent: r
    }), this._def.right._parseSync({
      data: r.data,
      path: r.path,
      parent: r
    }));
  }
}
he.create = (n, e, t) => new he({
  left: n,
  right: e,
  typeName: v.ZodIntersection,
  ..._(t)
});
class K extends b {
  _parse(e) {
    const { status: t, ctx: r } = this._processInputParams(e);
    if (r.parsedType !== p.array)
      return d(r, {
        code: l.invalid_type,
        expected: p.array,
        received: r.parsedType
      }), y;
    if (r.data.length < this._def.items.length)
      return d(r, {
        code: l.too_small,
        minimum: this._def.items.length,
        inclusive: !0,
        exact: !1,
        type: "array"
      }), y;
    !this._def.rest && r.data.length > this._def.items.length && (d(r, {
      code: l.too_big,
      maximum: this._def.items.length,
      inclusive: !0,
      exact: !1,
      type: "array"
    }), t.dirty());
    const s = [...r.data].map((i, o) => {
      const f = this._def.items[o] || this._def.rest;
      return f ? f._parse(new M(r, i, r.path, o)) : null;
    }).filter((i) => !!i);
    return r.common.async ? Promise.all(s).then((i) => O.mergeArray(t, i)) : O.mergeArray(t, s);
  }
  get items() {
    return this._def.items;
  }
  rest(e) {
    return new K({
      ...this._def,
      rest: e
    });
  }
}
K.create = (n, e) => {
  if (!Array.isArray(n))
    throw new Error("You must pass an array of schemas to z.tuple([ ... ])");
  return new K({
    items: n,
    typeName: v.ZodTuple,
    rest: null,
    ..._(e)
  });
};
class me extends b {
  get keySchema() {
    return this._def.keyType;
  }
  get valueSchema() {
    return this._def.valueType;
  }
  _parse(e) {
    const { status: t, ctx: r } = this._processInputParams(e);
    if (r.parsedType !== p.object)
      return d(r, {
        code: l.invalid_type,
        expected: p.object,
        received: r.parsedType
      }), y;
    const a = [], s = this._def.keyType, i = this._def.valueType;
    for (const o in r.data)
      a.push({
        key: s._parse(new M(r, o, r.path, o)),
        value: i._parse(new M(r, r.data[o], r.path, o)),
        alwaysSet: o in r.data
      });
    return r.common.async ? O.mergeObjectAsync(t, a) : O.mergeObjectSync(t, a);
  }
  get element() {
    return this._def.valueType;
  }
  static create(e, t, r) {
    return t instanceof b ? new me({
      keyType: e,
      valueType: t,
      typeName: v.ZodRecord,
      ..._(r)
    }) : new me({
      keyType: F.create(),
      valueType: e,
      typeName: v.ZodRecord,
      ..._(t)
    });
  }
}
class ct extends b {
  get keySchema() {
    return this._def.keyType;
  }
  get valueSchema() {
    return this._def.valueType;
  }
  _parse(e) {
    const { status: t, ctx: r } = this._processInputParams(e);
    if (r.parsedType !== p.map)
      return d(r, {
        code: l.invalid_type,
        expected: p.map,
        received: r.parsedType
      }), y;
    const a = this._def.keyType, s = this._def.valueType, i = [...r.data.entries()].map(([o, f], u) => ({
      key: a._parse(new M(r, o, r.path, [u, "key"])),
      value: s._parse(new M(r, f, r.path, [u, "value"]))
    }));
    if (r.common.async) {
      const o = /* @__PURE__ */ new Map();
      return Promise.resolve().then(async () => {
        for (const f of i) {
          const u = await f.key, m = await f.value;
          if (u.status === "aborted" || m.status === "aborted")
            return y;
          (u.status === "dirty" || m.status === "dirty") && t.dirty(), o.set(u.value, m.value);
        }
        return { status: t.value, value: o };
      });
    } else {
      const o = /* @__PURE__ */ new Map();
      for (const f of i) {
        const u = f.key, m = f.value;
        if (u.status === "aborted" || m.status === "aborted")
          return y;
        (u.status === "dirty" || m.status === "dirty") && t.dirty(), o.set(u.value, m.value);
      }
      return { status: t.value, value: o };
    }
  }
}
ct.create = (n, e, t) => new ct({
  valueType: e,
  keyType: n,
  typeName: v.ZodMap,
  ..._(t)
});
class le extends b {
  _parse(e) {
    const { status: t, ctx: r } = this._processInputParams(e);
    if (r.parsedType !== p.set)
      return d(r, {
        code: l.invalid_type,
        expected: p.set,
        received: r.parsedType
      }), y;
    const a = this._def;
    a.minSize !== null && r.data.size < a.minSize.value && (d(r, {
      code: l.too_small,
      minimum: a.minSize.value,
      type: "set",
      inclusive: !0,
      exact: !1,
      message: a.minSize.message
    }), t.dirty()), a.maxSize !== null && r.data.size > a.maxSize.value && (d(r, {
      code: l.too_big,
      maximum: a.maxSize.value,
      type: "set",
      inclusive: !0,
      exact: !1,
      message: a.maxSize.message
    }), t.dirty());
    const s = this._def.valueType;
    function i(f) {
      const u = /* @__PURE__ */ new Set();
      for (const m of f) {
        if (m.status === "aborted")
          return y;
        m.status === "dirty" && t.dirty(), u.add(m.value);
      }
      return { status: t.value, value: u };
    }
    const o = [...r.data.values()].map((f, u) => s._parse(new M(r, f, r.path, u)));
    return r.common.async ? Promise.all(o).then((f) => i(f)) : i(o);
  }
  min(e, t) {
    return new le({
      ...this._def,
      minSize: { value: e, message: h.toString(t) }
    });
  }
  max(e, t) {
    return new le({
      ...this._def,
      maxSize: { value: e, message: h.toString(t) }
    });
  }
  size(e, t) {
    return this.min(e, t).max(e, t);
  }
  nonempty(e) {
    return this.min(1, e);
  }
}
le.create = (n, e) => new le({
  valueType: n,
  minSize: null,
  maxSize: null,
  typeName: v.ZodSet,
  ..._(e)
});
class Me extends b {
  get schema() {
    return this._def.getter();
  }
  _parse(e) {
    const { ctx: t } = this._processInputParams(e);
    return this._def.getter()._parse({ data: t.data, path: t.path, parent: t });
  }
}
Me.create = (n, e) => new Me({
  getter: n,
  typeName: v.ZodLazy,
  ..._(e)
});
class ge extends b {
  _parse(e) {
    if (e.data !== this._def.value) {
      const t = this._getOrReturnCtx(e);
      return d(t, {
        received: t.data,
        code: l.invalid_literal,
        expected: this._def.value
      }), y;
    }
    return { status: "valid", value: e.data };
  }
  get value() {
    return this._def.value;
  }
}
ge.create = (n, e) => new ge({
  value: n,
  typeName: v.ZodLiteral,
  ..._(e)
});
function It(n, e) {
  return new Y({
    values: n,
    typeName: v.ZodEnum,
    ..._(e)
  });
}
class Y extends b {
  _parse(e) {
    if (typeof e.data != "string") {
      const t = this._getOrReturnCtx(e), r = this._def.values;
      return d(t, {
        expected: x.joinValues(r),
        received: t.parsedType,
        code: l.invalid_type
      }), y;
    }
    if (this._cache || (this._cache = new Set(this._def.values)), !this._cache.has(e.data)) {
      const t = this._getOrReturnCtx(e), r = this._def.values;
      return d(t, {
        received: t.data,
        code: l.invalid_enum_value,
        options: r
      }), y;
    }
    return Z(e.data);
  }
  get options() {
    return this._def.values;
  }
  get enum() {
    const e = {};
    for (const t of this._def.values)
      e[t] = t;
    return e;
  }
  get Values() {
    const e = {};
    for (const t of this._def.values)
      e[t] = t;
    return e;
  }
  get Enum() {
    const e = {};
    for (const t of this._def.values)
      e[t] = t;
    return e;
  }
  extract(e, t = this._def) {
    return Y.create(e, {
      ...this._def,
      ...t
    });
  }
  exclude(e, t = this._def) {
    return Y.create(this.options.filter((r) => !e.includes(r)), {
      ...this._def,
      ...t
    });
  }
}
Y.create = It;
class De extends b {
  _parse(e) {
    const t = x.getValidEnumValues(this._def.values), r = this._getOrReturnCtx(e);
    if (r.parsedType !== p.string && r.parsedType !== p.number) {
      const a = x.objectValues(t);
      return d(r, {
        expected: x.joinValues(a),
        received: r.parsedType,
        code: l.invalid_type
      }), y;
    }
    if (this._cache || (this._cache = new Set(x.getValidEnumValues(this._def.values))), !this._cache.has(e.data)) {
      const a = x.objectValues(t);
      return d(r, {
        received: r.data,
        code: l.invalid_enum_value,
        options: a
      }), y;
    }
    return Z(e.data);
  }
  get enum() {
    return this._def.values;
  }
}
De.create = (n, e) => new De({
  values: n,
  typeName: v.ZodNativeEnum,
  ..._(e)
});
class ye extends b {
  unwrap() {
    return this._def.type;
  }
  _parse(e) {
    const { ctx: t } = this._processInputParams(e);
    if (t.parsedType !== p.promise && t.common.async === !1)
      return d(t, {
        code: l.invalid_type,
        expected: p.promise,
        received: t.parsedType
      }), y;
    const r = t.parsedType === p.promise ? t.data : Promise.resolve(t.data);
    return Z(r.then((a) => this._def.type.parseAsync(a, {
      path: t.path,
      errorMap: t.common.contextualErrorMap
    })));
  }
}
ye.create = (n, e) => new ye({
  type: n,
  typeName: v.ZodPromise,
  ..._(e)
});
class X extends b {
  innerType() {
    return this._def.schema;
  }
  sourceType() {
    return this._def.schema._def.typeName === v.ZodEffects ? this._def.schema.sourceType() : this._def.schema;
  }
  _parse(e) {
    const { status: t, ctx: r } = this._processInputParams(e), a = this._def.effect || null, s = {
      addIssue: (i) => {
        d(r, i), i.fatal ? t.abort() : t.dirty();
      },
      get path() {
        return r.path;
      }
    };
    if (s.addIssue = s.addIssue.bind(s), a.type === "preprocess") {
      const i = a.transform(r.data, s);
      if (r.common.async)
        return Promise.resolve(i).then(async (o) => {
          if (t.value === "aborted")
            return y;
          const f = await this._def.schema._parseAsync({
            data: o,
            path: r.path,
            parent: r
          });
          return f.status === "aborted" ? y : f.status === "dirty" || t.value === "dirty" ? oe(f.value) : f;
        });
      {
        if (t.value === "aborted")
          return y;
        const o = this._def.schema._parseSync({
          data: i,
          path: r.path,
          parent: r
        });
        return o.status === "aborted" ? y : o.status === "dirty" || t.value === "dirty" ? oe(o.value) : o;
      }
    }
    if (a.type === "refinement") {
      const i = (o) => {
        const f = a.refinement(o, s);
        if (r.common.async)
          return Promise.resolve(f);
        if (f instanceof Promise)
          throw new Error("Async refinement encountered during synchronous parse operation. Use .parseAsync instead.");
        return o;
      };
      if (r.common.async === !1) {
        const o = this._def.schema._parseSync({
          data: r.data,
          path: r.path,
          parent: r
        });
        return o.status === "aborted" ? y : (o.status === "dirty" && t.dirty(), i(o.value), { status: t.value, value: o.value });
      } else
        return this._def.schema._parseAsync({ data: r.data, path: r.path, parent: r }).then((o) => o.status === "aborted" ? y : (o.status === "dirty" && t.dirty(), i(o.value).then(() => ({ status: t.value, value: o.value }))));
    }
    if (a.type === "transform")
      if (r.common.async === !1) {
        const i = this._def.schema._parseSync({
          data: r.data,
          path: r.path,
          parent: r
        });
        if (!re(i))
          return y;
        const o = a.transform(i.value, s);
        if (o instanceof Promise)
          throw new Error("Asynchronous transform encountered during synchronous parse operation. Use .parseAsync instead.");
        return { status: t.value, value: o };
      } else
        return this._def.schema._parseAsync({ data: r.data, path: r.path, parent: r }).then((i) => re(i) ? Promise.resolve(a.transform(i.value, s)).then((o) => ({
          status: t.value,
          value: o
        })) : y);
    x.assertNever(a);
  }
}
X.create = (n, e, t) => new X({
  schema: n,
  typeName: v.ZodEffects,
  effect: e,
  ..._(t)
});
X.createWithPreprocess = (n, e, t) => new X({
  schema: e,
  effect: { type: "preprocess", transform: n },
  typeName: v.ZodEffects,
  ..._(t)
});
class z extends b {
  _parse(e) {
    return this._getType(e) === p.undefined ? Z(void 0) : this._def.innerType._parse(e);
  }
  unwrap() {
    return this._def.innerType;
  }
}
z.create = (n, e) => new z({
  innerType: n,
  typeName: v.ZodOptional,
  ..._(e)
});
class ee extends b {
  _parse(e) {
    return this._getType(e) === p.null ? Z(null) : this._def.innerType._parse(e);
  }
  unwrap() {
    return this._def.innerType;
  }
}
ee.create = (n, e) => new ee({
  innerType: n,
  typeName: v.ZodNullable,
  ..._(e)
});
class ve extends b {
  _parse(e) {
    const { ctx: t } = this._processInputParams(e);
    let r = t.data;
    return t.parsedType === p.undefined && (r = this._def.defaultValue()), this._def.innerType._parse({
      data: r,
      path: t.path,
      parent: t
    });
  }
  removeDefault() {
    return this._def.innerType;
  }
}
ve.create = (n, e) => new ve({
  innerType: n,
  typeName: v.ZodDefault,
  defaultValue: typeof e.default == "function" ? e.default : () => e.default,
  ..._(e)
});
class _e extends b {
  _parse(e) {
    const { ctx: t } = this._processInputParams(e), r = {
      ...t,
      common: {
        ...t.common,
        issues: []
      }
    }, a = this._def.innerType._parse({
      data: r.data,
      path: r.path,
      parent: {
        ...r
      }
    });
    return de(a) ? a.then((s) => ({
      status: "valid",
      value: s.status === "valid" ? s.value : this._def.catchValue({
        get error() {
          return new B(r.common.issues);
        },
        input: r.data
      })
    })) : {
      status: "valid",
      value: a.status === "valid" ? a.value : this._def.catchValue({
        get error() {
          return new B(r.common.issues);
        },
        input: r.data
      })
    };
  }
  removeCatch() {
    return this._def.innerType;
  }
}
_e.create = (n, e) => new _e({
  innerType: n,
  typeName: v.ZodCatch,
  catchValue: typeof e.catch == "function" ? e.catch : () => e.catch,
  ..._(e)
});
class lt extends b {
  _parse(e) {
    if (this._getType(e) !== p.nan) {
      const r = this._getOrReturnCtx(e);
      return d(r, {
        code: l.invalid_type,
        expected: p.nan,
        received: r.parsedType
      }), y;
    }
    return { status: "valid", value: e.data };
  }
}
lt.create = (n) => new lt({
  typeName: v.ZodNaN,
  ..._(n)
});
class Et extends b {
  _parse(e) {
    const { ctx: t } = this._processInputParams(e), r = t.data;
    return this._def.type._parse({
      data: r,
      path: t.path,
      parent: t
    });
  }
  unwrap() {
    return this._def.type;
  }
}
class ze extends b {
  _parse(e) {
    const { status: t, ctx: r } = this._processInputParams(e);
    if (r.common.async)
      return (async () => {
        const s = await this._def.in._parseAsync({
          data: r.data,
          path: r.path,
          parent: r
        });
        return s.status === "aborted" ? y : s.status === "dirty" ? (t.dirty(), oe(s.value)) : this._def.out._parseAsync({
          data: s.value,
          path: r.path,
          parent: r
        });
      })();
    {
      const a = this._def.in._parseSync({
        data: r.data,
        path: r.path,
        parent: r
      });
      return a.status === "aborted" ? y : a.status === "dirty" ? (t.dirty(), {
        status: "dirty",
        value: a.value
      }) : this._def.out._parseSync({
        data: a.value,
        path: r.path,
        parent: r
      });
    }
  }
  static create(e, t) {
    return new ze({
      in: e,
      out: t,
      typeName: v.ZodPipeline
    });
  }
}
class be extends b {
  _parse(e) {
    const t = this._def.innerType._parse(e), r = (a) => (re(a) && (a.value = Object.freeze(a.value)), a);
    return de(t) ? t.then((a) => r(a)) : r(t);
  }
  unwrap() {
    return this._def.innerType;
  }
}
be.create = (n, e) => new be({
  innerType: n,
  typeName: v.ZodReadonly,
  ..._(e)
});
var v;
(function(n) {
  n.ZodString = "ZodString", n.ZodNumber = "ZodNumber", n.ZodNaN = "ZodNaN", n.ZodBigInt = "ZodBigInt", n.ZodBoolean = "ZodBoolean", n.ZodDate = "ZodDate", n.ZodSymbol = "ZodSymbol", n.ZodUndefined = "ZodUndefined", n.ZodNull = "ZodNull", n.ZodAny = "ZodAny", n.ZodUnknown = "ZodUnknown", n.ZodNever = "ZodNever", n.ZodVoid = "ZodVoid", n.ZodArray = "ZodArray", n.ZodObject = "ZodObject", n.ZodUnion = "ZodUnion", n.ZodDiscriminatedUnion = "ZodDiscriminatedUnion", n.ZodIntersection = "ZodIntersection", n.ZodTuple = "ZodTuple", n.ZodRecord = "ZodRecord", n.ZodMap = "ZodMap", n.ZodSet = "ZodSet", n.ZodFunction = "ZodFunction", n.ZodLazy = "ZodLazy", n.ZodLiteral = "ZodLiteral", n.ZodEnum = "ZodEnum", n.ZodEffects = "ZodEffects", n.ZodNativeEnum = "ZodNativeEnum", n.ZodOptional = "ZodOptional", n.ZodNullable = "ZodNullable", n.ZodDefault = "ZodDefault", n.ZodCatch = "ZodCatch", n.ZodPromise = "ZodPromise", n.ZodBranded = "ZodBranded", n.ZodPipeline = "ZodPipeline", n.ZodReadonly = "ZodReadonly";
})(v || (v = {}));
const c = F.create, w = ae.create, N = Re.create, Be = Pe.create;
H.create;
const j = P.create, g = T.create;
pe.create;
const Hn = Fe.create;
he.create;
K.create;
const Se = me.create, E = ge.create, k = Y.create;
ye.create;
z.create;
ee.create;
const $ = c().datetime({ offset: !0 }).describe("RFC 3339 timestamp in UTC."), C = w().min(0).max(1).describe("Calibrated heuristic score in [0,1]. Not a trained probability."), W = c().url().describe("Absolute http(s) URL."), Je = Se(c(), Be()), Nt = c().min(1).describe("Version identifier of the component that produced a value."), Rt = k([
  "UNKNOWN",
  "JOB_LISTING",
  "JOB_APPLICATION",
  "JOB_LISTING_AND_APPLICATION"
]), Gn = g({
  /** Stable identifier, e.g. "jsonld.jobPosting" or "form.resumeUpload". */
  id: c(),
  /** Whether the signal fired on this page. */
  matched: N(),
  /** Contribution toward the listing score, in logit space. */
  listingWeight: w(),
  /** Contribution toward the application score, in logit space. */
  applicationWeight: w(),
  /** Short debugging detail. Never page content. */
  detail: c().optional()
}), Lt = g({
  pageType: Rt,
  /** Probability mass of the winning label. Equals distribution[pageType]. */
  confidence: C,
  /** Calibrated marginals for the two independent questions. */
  heads: g({
    listing: C,
    application: C
  }),
  /** Full distribution over the four labels. Sums to 1. */
  distribution: g({
    UNKNOWN: C,
    JOB_LISTING: C,
    JOB_APPLICATION: C,
    JOB_LISTING_AND_APPLICATION: C
  }),
  /** Raw pre-calibration logits, retained so the scaler can be refit offline. */
  logits: g({
    listing: w(),
    application: w()
  }),
  signals: j(Gn),
  /** Identifies the weight and calibration generation that produced this. */
  calibrationVersion: c().default("1")
}), Zt = k([
  "structured_data",
  // schema.org JSON-LD, microdata, OpenGraph
  "provider",
  // a versioned ATS-specific adapter
  "semantic_dom",
  // ARIA roles, headings, definition lists, landmarks
  "heuristic",
  // keyword/pattern mining over visible text
  "ai",
  // Phase 4 model-assisted gap fill. Never runs first.
  "user"
  // human correction; always wins
]), Qn = k(["jsonld", "microdata", "meta", "dom", "url", "model"]), Kn = g({
  layer: Zt,
  independenceGroup: Qn,
  /** Extractor id, e.g. "provider:greenhouse" or "generic:structured-data". */
  extractorId: c(),
  extractorVersion: Nt,
  confidence: C
}), Pt = k(["remote", "hybrid", "onsite", "unknown"]), $t = k([
  "full_time",
  "part_time",
  "contract",
  "temporary",
  "internship",
  "volunteer",
  "other"
]), Yn = k(["hour", "day", "week", "month", "year", "unknown"]), Xn = g({
  min: w().nonnegative().optional(),
  max: w().nonnegative().optional(),
  /** ISO-4217 where determinable. */
  currency: c().length(3).optional(),
  period: Yn.optional(),
  /** The literal text the range was parsed from, useful for debugging parses. */
  raw: c().optional()
}), er = g({
  minimumYears: w().min(0).max(60).optional(),
  maximumYears: w().min(0).max(60).optional(),
  raw: c().optional()
}), tr = k([
  "high_school",
  "associate",
  "bachelor",
  "master",
  "doctorate",
  "none_specified"
]), V = k([
  "greenhouse",
  "lever",
  "workday",
  "ashby",
  "linkedin",
  "indeed",
  "smartrecruiters",
  "jobvite",
  "icims",
  "taleo",
  "oracle",
  "adp",
  "bamboohr",
  "workable",
  "rippling",
  "jazzhr",
  "jobright",
  "generic"
]), se = g({
  /** Server-assigned. Absent until persisted. */
  id: c().optional(),
  url: W,
  canonicalUrl: W.optional(),
  /** Registrable domain the posting was observed on. */
  source: c().min(1),
  provider: V.optional(),
  /** Provider-native posting id, e.g. the Greenhouse gh_jid query parameter. */
  providerJobId: c().optional(),
  title: c().optional(),
  company: c().optional(),
  /**
   * Absolute URL of the employer's logo as shown on the posting.
   *
   * A URL, never the image bytes. The board renders it directly from the
   * employer's own host, so nothing is copied, cached or re-served — and a
   * posting that is taken down simply loses its logo rather than leaving us
   * holding someone else's asset.
   */
  companyLogoUrl: W.optional(),
  location: c().optional(),
  employmentType: $t.optional(),
  workplaceType: Pt.default("unknown"),
  salary: Xn.optional(),
  /** Plain text with layout normalised. Always present, may be empty. */
  description: c().default(""),
  /**
   * The smallest text that still fully describes the job, for resume tailoring.
   *
   * Built only by selecting and trimming original text, never paraphrased:
   * boilerplate (EEO statements, benefits lists, company marketing, legal and
   * cookie text) is dropped; responsibilities, requirements, preferred
   * qualifications, tech stack and the basics (title, company, location,
   * salary, work model) are kept. Derived locally; not part of the synced row.
   */
  descriptionCompact: c().optional(),
  responsibilities: j(c()).default([]),
  requiredQualifications: j(c()).default([]),
  preferredQualifications: j(c()).default([]),
  skills: j(c()).default([]),
  experience: er.optional(),
  educationLevel: tr.optional(),
  /** True when the posting explicitly mentions sponsorship availability. */
  sponsorshipAvailable: N().optional(),
  /** True when the posting requires a security clearance. */
  securityClearanceRequired: N().optional(),
  workAuthorizationNote: c().optional(),
  /**
   * Stable content hash used for deduplication across boards.
   * Computed from normalised title, company, location and description.
   */
  fingerprint: c().optional(),
  /** Field name to producer. Keys are JobPosting property names. */
  fieldProvenance: Se(c(), Kn).default({}),
  metadata: Je.default({}),
  detectedAt: $
}), nr = k([
  "text",
  "textarea",
  "number",
  "boolean",
  "radio",
  "select",
  "checkbox",
  "multi_select",
  "date",
  "file",
  "unknown"
]), rr = k([
  "general",
  "work_authorization",
  "sponsorship",
  "salary",
  "experience",
  "education",
  "location",
  "relocation",
  "demographic",
  "contact",
  "custom"
]), ar = g({
  /** Best-effort stable selector for re-location on rescan. */
  selector: c(),
  tagName: c(),
  inputType: c().optional(),
  /** Form control name attribute, used to group radio and checkbox sets. */
  fieldName: c().optional(),
  elementId: c().optional(),
  /** Index of the containing field group, for multi-step forms. */
  groupIndex: w().int().nonnegative().optional(),
  /** Which step of a multi-step application this control belongs to, if known. */
  step: w().int().nonnegative().optional(),
  /** Frame the control lives in. 0 is the top document. */
  frameId: w().int().nonnegative().optional()
}), sr = g({
  label: c(),
  value: c().optional(),
  /** Prompt entries such as "Select an option" are kept but marked. */
  placeholder: N().default(!1)
}), Te = g({
  /** Stable within a page scan: hash of frameId, fieldName and selector. */
  id: c(),
  question: c(),
  type: nr,
  required: N().default(!1),
  options: j(sr).optional(),
  /**
   * The value currently entered by the user.
   *
   * PRIVACY: never populated for `sensitive` questions, and never included in
   * any payload sent off-device unless the user explicitly opts in for that
   * application. See docs/privacy.md.
   */
  currentValue: Be().optional(),
  category: rr.default("general"),
  /**
   * How sensitive this question is, in the sense that matters legally.
   *
   * - `normal`        ordinary application content.
   * - `eeo_voluntary` an OFCCP-style voluntary self-identification block. The
   *                   page itself says answering is optional and unused in
   *                   hiring. Shown to the user in a separate collapsed group.
   * - `protected`     a protected characteristic asked *outside* a voluntary
   *                   self-ID context, or a question under a jurisdictional ban
   *                   (salary history, criminal record). Worth flagging to the
   *                   user precisely because it may not be lawful where they are.
   *
   * The distinction matters: a required race question is a materially different
   * thing from a voluntary self-ID block, and collapsing both into one boolean
   * would lose that.
   */
  sensitivity: k(["normal", "eeo_voluntary", "protected"]).default("normal"),
  /**
   * True for EEO, demographic and protected-characteristic questions.
   *
   * Equivalent to `sensitivity !== 'normal'`, kept as its own field because it
   * is the flag the rest of the platform gates on and it must stay cheap to
   * check in Go, Python and SQL. Always set consistently with `sensitivity`.
   */
  sensitive: N().default(!1),
  /**
   * Whether this question may ever be auto-answered.
   *
   * `never` for everything sensitive. The Phase 4 answer generator filters on
   * this field and nothing else, giving one chokepoint rather than a policy
   * check duplicated at every call site.
   */
  autofillPolicy: k(["allow", "suggest_only", "never"]).default("allow"),
  /** How sure the detector is that this is a real, well-labelled question. */
  confidence: C.default(1),
  element: ar,
  /** Character limit if the control declares one. */
  maxLength: w().int().positive().optional(),
  helpText: c().optional(),
  metadata: Je.default({})
});
function Mt(n) {
  const { currentValue: e, ...t } = n;
  return { ...t, metadata: {} };
}
function Dt(n) {
  return !n.sensitive && n.sensitivity === "normal" && n.category !== "demographic";
}
const Ut = g({
  url: W,
  canonicalUrl: W.optional(),
  domain: c(),
  title: c().default(""),
  /** Provider detected for this document, if any. */
  provider: V.optional(),
  providerJobId: c().optional(),
  /** Which frame produced this, 0 being the top document. */
  frameId: w().int().nonnegative().default(0),
  /** True when the document is not the top-level frame. */
  isFrame: N().default(!1),
  /** Language declared by the document. */
  language: c().optional(),
  capturedAt: $
}), ir = g({
  extractorId: c(),
  extractorVersion: Nt,
  layer: Zt,
  status: k(["ok", "skipped", "empty", "error"]),
  /** Number of field candidates contributed. */
  fieldsProduced: w().int().nonnegative().default(0),
  durationMs: w().nonnegative().default(0),
  /** Error class and message only. Never page content. */
  error: c().optional()
}), or = g({
  layers: j(ir).default([]),
  totalDurationMs: w().nonnegative().default(0),
  /** True when no provider adapter matched and generic extraction carried the page. */
  genericFallbackUsed: N().default(!1),
  /** True when a provider adapter matched but produced nothing usable. */
  providerExtractionFailed: N().default(!1),
  /** Scan sequence number within the current document lifetime. */
  scanIndex: w().int().nonnegative().default(0)
}), cr = g({
  id: c(),
  /** Heading or legend the form sits under, when one is resolvable. */
  label: c().optional(),
  /** Zero-based step index for multi-step flows such as Workday. */
  step: w().int().nonnegative().default(0),
  totalSteps: w().int().positive().optional(),
  questionIds: j(c()).default([]),
  /** True when the form declares a resume or CV upload control. */
  hasResumeUpload: N().default(!1)
}), lr = g({
  /** Deterministic id for this scan: hash of url and scanIndex. */
  id: c(),
  schemaVersion: E(1).default(1),
  page: Ut,
  classification: Lt,
  /** Absent when the page is not a job listing. */
  job: se.optional(),
  questions: j(Te).default([]),
  forms: j(cr).default([]),
  /** Aggregate quality of the job extraction, not of the classification. */
  extractionConfidence: C.default(0),
  diagnostics: or,
  metadata: Je.default({})
}), qt = k([
  "saved",
  "applied",
  "interviewing",
  "offer",
  "rejected",
  "archived"
]), ur = g({
  id: c().uuid(),
  user_id: c().uuid(),
  /** Stable per-posting hash. Re-saving the same job updates rather than duplicates. */
  fingerprint: c().min(1),
  url: W,
  domain: c(),
  provider: V.nullable().default(null),
  provider_job_id: c().nullable().default(null),
  title: c().nullable().default(null),
  company: c().nullable().default(null),
  company_logo_url: c().nullable().default(null),
  location: c().nullable().default(null),
  workplace_type: Pt.nullable().default(null),
  employment_type: $t.nullable().default(null),
  salary_min: w().nullable().default(null),
  salary_max: w().nullable().default(null),
  salary_currency: c().length(3).nullable().default(null),
  salary_period: c().nullable().default(null),
  experience_min_years: w().int().nullable().default(null),
  experience_max_years: w().int().nullable().default(null),
  description: c().nullable().default(null),
  responsibilities: j(c()).default([]),
  required_qualifications: j(c()).default([]),
  preferred_qualifications: j(c()).default([]),
  skills: j(c()).default([]),
  sponsorship_available: N().nullable().default(null),
  security_clearance_required: N().nullable().default(null),
  /** How much the extension trusted this extraction, 0-1. */
  extraction_confidence: w().min(0).max(1).nullable().default(null),
  /** Application questions found on the page, as extracted. */
  questions: Be().nullable().default(null),
  /* ------------------------------------------------ user-owned pipeline */
  status: qt.default("saved"),
  notes: c().nullable().default(null),
  applied_at: $.nullable().default(null),
  saved_at: $,
  updated_at: $
});
ur.omit({
  id: !0,
  user_id: !0,
  saved_at: !0,
  updated_at: !0,
  applied_at: !0
}).partial({ status: !0, notes: !0 });
g({
  status: qt,
  notes: c().max(2e4).nullable()
}).partial();
function dr(n) {
  const e = n.job;
  return e ? {
    fingerprint: e.fingerprint ?? n.page.url,
    url: n.page.url,
    domain: n.page.domain,
    provider: n.page.provider ?? null,
    provider_job_id: n.page.providerJobId ?? null,
    title: e.title ?? null,
    company: e.company ?? null,
    company_logo_url: e.companyLogoUrl ?? null,
    location: e.location ?? null,
    workplace_type: e.workplaceType === "unknown" ? null : e.workplaceType ?? null,
    employment_type: e.employmentType ?? null,
    salary_min: e.salary?.min ?? null,
    salary_max: e.salary?.max ?? null,
    salary_currency: e.salary?.currency ?? null,
    salary_period: e.salary?.period ?? null,
    experience_min_years: e.experience?.minimumYears ?? null,
    experience_max_years: e.experience?.maximumYears ?? null,
    description: e.description ?? null,
    responsibilities: e.responsibilities ?? [],
    required_qualifications: e.requiredQualifications ?? [],
    preferred_qualifications: e.preferredQualifications ?? [],
    skills: e.skills ?? [],
    sponsorship_available: e.sponsorshipAvailable ?? null,
    security_clearance_required: e.securityClearanceRequired ?? null,
    extraction_confidence: n.extractionConfidence ?? null,
    // The saved row is synced off-device, so it gets the same treatment as
    // any other sync payload: sensitive questions dropped, entered values
    // and metadata stripped (redactQuestionForSync is the one chokepoint).
    questions: n.questions ? n.questions.filter(Dt).map(Mt) : null
  } : null;
}
k([
  "page_detected",
  "job_detected",
  "job_extracted",
  "questions_detected",
  "provider_detected",
  "provider_extraction_failed",
  "generic_fallback_used",
  "job_saved",
  "api_request_failed",
  "permission_granted",
  "scan_throttled",
  "extraction_error"
]);
const L = {
  /** Registrable domain only. Never the full URL. */
  domain: c(),
  occurredAt: $,
  /** Rotating anonymous install id. Not tied to a user account. */
  installId: c(),
  extensionVersion: c()
};
Hn("name", [
  g({
    name: E("page_detected"),
    ...L,
    pageType: Rt,
    confidence: C
  }),
  g({
    name: E("provider_detected"),
    ...L,
    provider: V,
    adapterVersion: c()
  }),
  g({
    name: E("job_detected"),
    ...L,
    provider: V.optional()
  }),
  g({
    name: E("job_extracted"),
    ...L,
    provider: V.optional(),
    /** Count of populated fields, not their values. */
    fieldsPopulated: w().int().nonnegative(),
    extractionConfidence: C,
    durationMs: w().nonnegative()
  }),
  g({
    name: E("questions_detected"),
    ...L,
    provider: V.optional(),
    questionCount: w().int().nonnegative(),
    sensitiveCount: w().int().nonnegative(),
    requiredCount: w().int().nonnegative()
  }),
  g({
    name: E("provider_extraction_failed"),
    ...L,
    provider: V,
    adapterVersion: c(),
    /** Error class name only. */
    reason: c()
  }),
  g({
    name: E("generic_fallback_used"),
    ...L,
    /** Provider that was detected but did not carry the page, if any. */
    attemptedProvider: V.optional()
  }),
  g({
    name: E("job_saved"),
    ...L,
    destination: k(["local", "backend"])
  }),
  g({
    name: E("api_request_failed"),
    ...L,
    /** Route template, e.g. "/api/v1/jobs". Never a populated path. */
    route: c(),
    statusCode: w().int().optional(),
    reason: c()
  }),
  g({
    name: E("permission_granted"),
    ...L,
    origin: c()
  }),
  g({
    name: E("scan_throttled"),
    ...L,
    reason: k(["rate_budget", "unchanged_fingerprint", "document_hidden"])
  }),
  g({
    name: E("extraction_error"),
    ...L,
    stage: c(),
    reason: c()
  })
]);
g({
  type: c(),
  title: c(),
  status: w().int(),
  detail: c().optional(),
  /** Correlates a client failure with a server trace. */
  traceId: c().optional(),
  /** Field-level validation failures, keyed by JSON pointer. */
  violations: Se(c(), c()).optional()
});
g({
  page: Ut,
  /** Normalised plain text only. The raw document is never uploaded. */
  descriptionText: c().max(2e5),
  /** What the client already worked out, so the server can fill gaps only. */
  clientJob: se.partial().optional(),
  classification: Lt.optional()
});
g({
  job: se,
  confidence: C
});
g({
  job: se,
  /** Optional provenance of the scan that produced it. */
  extractionId: c().optional()
});
g({
  job: se,
  createdAt: $,
  updatedAt: $,
  /** True when an existing record matched the fingerprint. */
  deduplicated: N().default(!1)
});
const Vt = k([
  "discovered",
  "in_progress",
  "submitted",
  "rejected",
  "interviewing",
  "offer",
  "withdrawn"
]);
g({
  jobUrl: W,
  jobId: c().optional(),
  status: Vt.default("discovered")
});
g({
  id: c(),
  jobId: c().optional(),
  jobUrl: W,
  status: Vt,
  questionCount: w().int().nonnegative().default(0),
  createdAt: $,
  updatedAt: $
});
g({
  questions: j(Te).max(500)
});
g({
  accepted: w().int().nonnegative(),
  /** Count rejected for policy reasons, e.g. flagged sensitive. */
  rejected: w().int().nonnegative()
});
g({
  job: se,
  /** Which analyses to run. Keeps one endpoint from becoming a grab bag. */
  include: j(k(["skills", "requirements", "seniority", "summary"])).default(["skills", "requirements"])
});
g({
  skills: j(g({ name: c(), confidence: C })).default([]),
  requirements: j(
    g({
      text: c(),
      kind: k(["required", "preferred", "responsibility"]),
      confidence: C
    })
  ).default([]),
  seniority: c().optional(),
  summary: c().optional(),
  /** Which implementation answered, so clients can tell rules from a model. */
  engine: c()
});
g({
  questions: j(Te).max(500)
});
g({
  questions: j(Te),
  engine: c()
});
g({
  extraction: lr
});
g({
  status: k(["ok", "degraded", "down"]),
  service: c(),
  version: c(),
  checks: Se(c(), k(["ok", "fail"])).default({})
});
let Ft = () => {
};
function fr(n) {
  Ft = n;
}
async function ut(n, e, t) {
  try {
    if (!(await ke()).telemetryEnabled) return;
    const a = {
      name: n,
      domain: pr(e),
      occurredAt: (/* @__PURE__ */ new Date()).toISOString(),
      installId: await xn(),
      extensionVersion: Xt(),
      ...t
    };
    Ft(a);
  } catch {
  }
}
function pr(n) {
  try {
    return (typeof n == "string" ? new URL(n) : n).hostname.replace(/^www\./iu, "");
  } catch {
    return "unknown";
  }
}
class je {
  baseUrl;
  token;
  constructor(e, t) {
    this.baseUrl = e.replace(/\/+$/u, ""), this.token = t;
  }
  /** Returns null when no backend is configured, i.e. local-only operation. */
  static async create() {
    const e = await ke();
    return !e.apiBaseUrl || !e.apiBaseUrl.startsWith("https://") && !mr(e.apiBaseUrl) ? null : new je(e.apiBaseUrl);
  }
  async saveJob(e) {
    if (!e.job) return null;
    const t = { job: e.job, extractionId: e.id };
    return this.post("/api/v1/jobs", t, {
      // The fingerprint is stable across re-scans and across the same posting
      // appearing on two different URLs, which is exactly what we want the
      // server to deduplicate on.
      "Idempotency-Key": e.job.fingerprint ?? e.id
    });
  }
  async submitQuestions(e, t) {
    const r = hr(t);
    return r.length === 0 ? { accepted: 0, rejected: t.length } : this.post(`/api/v1/applications/${encodeURIComponent(e)}/questions`, {
      questions: r
    });
  }
  async sendTelemetry(e) {
    e.length !== 0 && await this.post("/api/v1/telemetry", { events: e });
  }
  async post(e, t, r = {}) {
    const a = `${this.baseUrl}${e}`;
    try {
      const s = await fetch(a, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...this.token ? { Authorization: `Bearer ${this.token}` } : {},
          ...r
        },
        body: JSON.stringify(t),
        // Never attach cookies: this is a token-authenticated API and sending
        // ambient credentials from an extension is how CSRF-by-accident happens.
        credentials: "omit",
        signal: AbortSignal.timeout(15e3)
      });
      if (!s.ok) {
        const i = await gr(s);
        return await ut("api_request_failed", this.baseUrl, {
          route: e,
          statusCode: s.status,
          reason: i?.title ?? s.statusText
        }), null;
      }
      return await s.json();
    } catch (s) {
      return await ut("api_request_failed", this.baseUrl, {
        route: e,
        reason: s instanceof Error ? s.name : "NetworkError"
      }), null;
    }
  }
}
function hr(n) {
  return n.filter(Dt).map(Mt);
}
function mr(n) {
  try {
    const { hostname: e } = new URL(n);
    return e === "localhost" || e === "127.0.0.1" || e === "[::1]";
  } catch {
    return !1;
  }
}
async function gr(n) {
  try {
    return await n.json();
  } catch {
    return null;
  }
}
const yr = 0xcbf29ce484222325n, vr = 0x100000001b3n, zt = 0xffffffffffffffffn;
function _r(n) {
  let e = yr;
  const t = new TextEncoder().encode(n);
  for (const r of t)
    e ^= BigInt(r), e = e * vr & zt;
  return e;
}
function br(n) {
  return (n & zt).toString(16).padStart(16, "0");
}
function wr(n) {
  return br(_r(n.map((e) => e.trim().toLowerCase()).join("\0")));
}
const xr = /[\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000]/gu, kr = /[\u200B-\u200D\uFEFF]/gu;
function Sr(n) {
  return n.replace(kr, "").replace(xr, " ").replace(/\s+/gu, " ").trim();
}
function Tr(n) {
  return Sr(n).toLowerCase().replace(/[^\p{L}\p{N}\s+#.]/gu, " ").replace(/\s+/gu, " ").trim();
}
const jr = /* @__PURE__ */ new Set([
  "workday",
  "oracle",
  "adp",
  "jobvite",
  "icims",
  "taleo",
  "bamboohr"
]);
function Ar(n, e) {
  return wr(["provider", n, Tr(e)]);
}
function Cr(n) {
  const { provider: e, providerJobId: t } = n;
  return !e || !t || !jr.has(e) ? null : Ar(e, t);
}
function Bt(n) {
  return Cr({
    provider: n.page.provider ?? n.job?.provider,
    providerJobId: n.job?.providerJobId ?? n.page.providerJobId
  });
}
function dt(n, e) {
  return e ? e.fingerprint && n.fingerprint !== e.fingerprint ? "page-changed: the job on the tab is not the one that was checked" : e.url && n.url && ft(n.url) !== ft(e.url) ? "page-changed: the tab moved to another address" : null : null;
}
function ft(n) {
  try {
    const e = new URL(n);
    return e.hash = "", e.toString();
  } catch {
    return n;
  }
}
class ie extends Error {
  constructor(e, t) {
    super(e), this.status = t, this.name = "SupabaseError";
  }
}
async function Ae() {
  const n = await ke(), e = n.supabaseUrl.trim().replace(/\/+$/u, ""), t = n.supabaseAnonKey.trim();
  return !e || !t ? null : { url: e, anonKey: t };
}
async function Jt() {
  const n = await Ae();
  if (!n) throw new ie("No Supabase project configured.");
  return n;
}
async function Wt() {
  return ue(I.supabaseSession, null);
}
async function pt(n) {
  await Ve(I.supabaseSession, n);
}
function Or(n) {
  const e = n.access_token, t = n.refresh_token;
  if (typeof e != "string" || typeof t != "string")
    throw new ie("Sign-in response did not include a session.");
  const r = typeof n.expires_in == "number" ? n.expires_in : 3600, a = n.user ?? {};
  return {
    access_token: e,
    refresh_token: t,
    expires_at: Math.floor(Date.now() / 1e3) + r,
    email: typeof a.email == "string" ? a.email : "",
    user_id: typeof a.id == "string" ? a.id : ""
  };
}
async function Ir(n, e, t) {
  const r = await fetch(`${n.url}${e}`, {
    method: "POST",
    headers: {
      apikey: n.anonKey,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(t)
  }), a = await r.text(), s = a ? JSON.parse(a) : {};
  if (!r.ok)
    throw new ie(Er(s, r.status), r.status);
  return s;
}
function Er(n, e) {
  let t = "";
  for (const r of ["error_description", "msg", "message", "error"]) {
    const a = n[r];
    if (typeof a == "string" && a.length > 0) {
      t = a;
      break;
    }
  }
  return /invalid login credentials/iu.test(t) ? "Wrong email or password. If you have not created an account yet, use Create account." : /already registered/iu.test(t) ? "That email already has an account. Use Sign in instead." : /email not confirmed/iu.test(t) ? 'Supabase is waiting for email confirmation. Turn off "Confirm email" under Authentication → Sign In / Providers → Email.' : /password/iu.test(t) && /least|short|6/iu.test(t) ? "Password is too short. Supabase requires at least six characters." : t || `Request failed (${String(e)}).`;
}
async function We() {
  const n = await Jt(), e = await Wt();
  if (!e) throw new ie("Not signed in.");
  if (e.expires_at - 60 > Math.floor(Date.now() / 1e3)) return e.access_token;
  const t = await Ir(n, "/auth/v1/token?grant_type=refresh_token", {
    refresh_token: e.refresh_token
  }).catch(async (s) => {
    throw await pt(null), s;
  }), r = Or(t), a = {
    ...r,
    email: r.email || e.email,
    user_id: r.user_id || e.user_id
  };
  return await pt(a), a.access_token;
}
async function Ue(n) {
  const e = await Ae();
  if (!e) return null;
  try {
    const t = await We(), r = new URLSearchParams({
      select: "status,saved_at",
      fingerprint: `eq.${n}`,
      limit: "1"
    }), a = await fetch(`${e.url}/rest/v1/saved_jobs?${r.toString()}`, {
      headers: {
        apikey: e.anonKey,
        Authorization: `Bearer ${t}`
      }
    });
    if (!a.ok) return null;
    const i = (await a.json())[0];
    return !i || typeof i.saved_at != "string" ? null : {
      status: typeof i.status == "string" ? i.status : "saved",
      saved_at: i.saved_at
    };
  } catch {
    return null;
  }
}
async function Nr(n) {
  const e = await Ae();
  if (!e) return { state: "unknown", error: "Database not configured." };
  try {
    const t = await We(), r = new URLSearchParams({
      select: "status,saved_at",
      fingerprint: `eq.${n}`,
      limit: "1"
    }), a = await fetch(`${e.url}/rest/v1/saved_jobs?${r.toString()}`, {
      headers: { apikey: e.anonKey, Authorization: `Bearer ${t}` }
    });
    if (!a.ok) return { state: "unknown", error: `lookup answered ${String(a.status)}` };
    const i = (await a.json())[0];
    return i ? { state: "present", status: typeof i.status == "string" ? i.status : "saved" } : { state: "absent" };
  } catch (t) {
    return { state: "unknown", error: t instanceof Error ? t.message : "lookup failed" };
  }
}
async function Rr(n) {
  const e = await Jt(), t = await We(), { status: r, notes: a, ...s } = n, i = await fetch(
    `${e.url}/rest/v1/saved_jobs?on_conflict=user_id,fingerprint`,
    {
      method: "POST",
      headers: {
        apikey: e.anonKey,
        Authorization: `Bearer ${t}`,
        "Content-Type": "application/json",
        // merge-duplicates makes this an upsert; minimal keeps the response
        // empty, which is all we need and avoids sending the row back.
        Prefer: "resolution=merge-duplicates,return=minimal"
      },
      body: JSON.stringify(s)
    }
  );
  if (!i.ok) {
    const o = await i.text();
    throw new ie(Lr(o, i.status), i.status);
  }
}
function Lr(n, e) {
  try {
    const t = JSON.parse(n), r = t.message, a = t.hint;
    if (typeof r == "string")
      return typeof a == "string" && a.length > 0 ? `${r} (${a})` : r;
  } catch {
  }
  return e === 401 ? "Sign-in expired. Sign in again from the extension settings." : e === 404 ? "Table saved_jobs not found. Run the migration in supabase/migrations." : `Sync failed (${String(e)}).`;
}
const ht = {
  /** Below this the extension stays quiet and shows no badge. */
  minActionable: 0.45,
  /** Above this the badge asserts a detection rather than a maybe. */
  confident: 0.75
}, D = new cn();
nn(async (n, e) => {
  switch (n.type) {
    case "frame/report": {
      const t = e.tab?.id;
      if (t === void 0) return Qe("no tab");
      const r = n.payload;
      return D.record(t, e.frameId ?? 0, r), await Ge(t), G(null);
    }
    case "frame/cleared": {
      const t = e.tab?.id;
      return t !== void 0 && D.clearFrame(t, e.frameId ?? 0), G(null);
    }
    case "telemetry/event":
      return await Hr(n.payload), G(null);
    case "ui/get-tab-state": {
      const { tabId: t } = n.payload;
      return G(await Mr(t));
    }
    case "ui/rescan": {
      const { tabId: t } = n.payload;
      return await He(t), G(null);
    }
    case "ui/save-job": {
      const { tabId: t, expect: r } = n.payload;
      return G(await qr(t, r));
    }
    case "ui/confirm-saved": {
      const { fingerprint: t } = n.payload;
      return G(await Nr(t));
    }
    default:
      return Qe(`unhandled: ${n.type}`);
  }
});
const te = R();
te?.tabs?.onUpdated?.addListener((n, e) => {
  e.url && He(n), e.status === "complete" && Ge(n);
});
te?.tabs?.onRemoved?.addListener((n) => {
  D.clearTab(n);
});
te?.tabs?.onActivated?.addListener(({ tabId: n }) => {
  Ge(n);
});
te?.permissions?.onAdded?.addListener((n) => {
  (async () => (await xe(), await jt(n.origins ?? [])))();
});
te?.permissions?.onRemoved?.addListener(() => {
  xe();
});
te?.runtime?.onStartup?.addListener(() => void xe());
te?.runtime?.onInstalled?.addListener(() => {
  (async () => (await xe(), await Zr()))();
});
async function Zr() {
  const n = await Tt();
  await jt([...St, ...n]);
}
async function He(n) {
  if (await mt(n)) return !0;
  const e = R();
  if (!e?.scripting?.executeScript) return !1;
  try {
    await e.scripting.executeScript({
      target: { tabId: n, allFrames: !0 },
      files: we
    });
  } catch {
    return !1;
  }
  return mt(n);
}
async function mt(n) {
  const e = R()?.tabs;
  if (!e?.sendMessage) return !1;
  try {
    return await e.sendMessage(n, {
      v: 1,
      type: "scan/request",
      payload: { reason: "navigation" }
    }), !0;
  } catch {
    return !1;
  }
}
const Pr = 1500, $r = 75;
async function Mr(n) {
  let e = D.aggregate(n), t = !!e?.classification;
  if (!t) {
    const a = await Dr(n);
    e = a.state ?? e, t = a.answered;
  }
  const r = e?.url ?? await Ur(n);
  return {
    tabId: n,
    url: r,
    classification: e?.classification ?? null,
    provider: e?.provider ?? null,
    result: e?.result ?? null,
    needsPermission: r ? !await mn(r) : !1,
    tabResponded: t,
    alreadySaved: await Ht(e?.result ?? null),
    updatedAt: (/* @__PURE__ */ new Date()).toISOString()
  };
}
async function Ht(n) {
  const e = n?.job?.fingerprint;
  if (!e) return null;
  const t = await Ue(e);
  if (t)
    return { where: "remote", savedAt: t.saved_at, status: t.status };
  const r = n ? Bt(n) : null;
  if (r && r !== e) {
    const s = await Ue(r);
    if (s) return { where: "remote", savedAt: s.saved_at, status: s.status };
  }
  const a = (await wn()).find((s) => s.job?.fingerprint === e);
  return a ? { where: "local", savedAt: a.page.capturedAt } : null;
}
async function Dr(n) {
  if (!await He(n))
    return { answered: !1, state: D.aggregate(n) };
  const e = Date.now() + Pr;
  for (; ; ) {
    const t = D.aggregate(n);
    if (t?.classification) return { answered: !0, state: t };
    if (Date.now() >= e) return { answered: !0, state: t };
    await Gt($r);
  }
}
function Gt(n) {
  return new Promise((e) => setTimeout(e, n));
}
async function Ur(n) {
  try {
    return (await vt().tabs.get(n)).url ?? "";
  } catch {
    return "";
  }
}
async function qr(n, e) {
  const t = D.aggregate(n);
  if (t?.result?.job) {
    const m = dt(
      { url: t.url ?? null, fingerprint: t.result.job.fingerprint ?? null },
      e
    );
    if (m) return { saved: !1, synced: !1, existing: null, error: m };
  }
  const r = await zr(n);
  if (!r || !sn(r))
    return {
      saved: !1,
      synced: !1,
      existing: null,
      error: qe(r) ? "not-a-job: the posting is closed or no longer available" : r?.result.job ? "not-a-job: the page has no job description" : "not-a-job: no job posting found on this page"
    };
  const a = r.result;
  if (!t?.result?.job) {
    const m = dt(
      { url: t?.url ?? a.page.url ?? null, fingerprint: a.job?.fingerprint ?? null },
      e
    );
    if (m) return { saved: !1, synced: !1, existing: null, error: m };
  }
  const s = await Ht(a);
  await bn(a);
  const i = await Wr(a);
  if (i.attempted)
    return {
      saved: !0,
      synced: i.ok,
      existing: s,
      fingerprint: i.fingerprint ?? a.job?.fingerprint ?? null,
      ...i.error ? { error: i.error } : {},
      ...i.failure ? { syncFailure: i.failure } : {}
    };
  const o = a.job?.fingerprint ?? null, f = await je.create();
  return f ? { saved: !0, synced: await f.saveJob(a) !== null, existing: s, fingerprint: o } : { saved: !0, synced: !1, existing: s, fingerprint: o };
}
const Vr = 1e4, gt = 600, Fr = 3;
async function zr(n) {
  const e = Date.now() + Vr;
  let t = null, r = "", a = 0;
  const s = /* @__PURE__ */ new Set();
  for (; ; ) {
    const i = await Br(n), o = i.missing.filter((m) => !s.has(m));
    if (o.length > 0) {
      for (const m of o) s.add(m);
      await Jr(n, o);
      continue;
    }
    for (const { frameId: m, report: A } of i.reports) D.record(n, m, A);
    t = xt(D.reports(n)) ?? t;
    const f = kt(t);
    if (f === "complete") return t;
    const u = on(t);
    if (a = u === r ? a + 1 : 0, r = u, f === "partial" && a >= Fr || Date.now() + gt >= e) return t;
    await Gt(gt);
  }
}
async function Br(n) {
  const e = { reports: [], missing: [] }, t = R()?.scripting;
  if (!t?.executeScript) return e;
  try {
    const r = await Qt(
      t.executeScript({
        target: { tabId: n, allFrames: !0 },
        injectImmediately: !0,
        // Self-contained: runs in the page, in the content script's isolated
        // world, where content/index.ts installed the hook.
        func: async () => {
          const s = globalThis[Symbol.for("job-platform.content.extract.v1")];
          return typeof s != "function" ? { missing: !0 } : { missing: !1, report: await s() ?? null };
        }
      }),
      4e3
    );
    if (!r) return e;
    const a = r.map((s) => ({
      frameId: s.frameId ?? 0,
      value: s.result
    }));
    return {
      reports: a.filter((s) => s.value?.report).map((s) => ({ frameId: s.frameId, report: s.value.report })),
      missing: a.filter((s) => s.value?.missing === !0).map((s) => s.frameId)
    };
  } catch {
    return e;
  }
}
async function Jr(n, e) {
  await Promise.all(
    e.map(async (t) => {
      try {
        await Qt(
          Promise.resolve(
            R()?.scripting?.executeScript({
              target: { tabId: n, frameIds: [t] },
              files: we,
              injectImmediately: !0
            })
          ),
          3e3
        );
      } catch {
      }
    })
  );
}
function Qt(n, e) {
  return new Promise((t) => {
    const r = setTimeout(() => t(null), e);
    n.then(
      (a) => {
        clearTimeout(r), t(a);
      },
      () => {
        clearTimeout(r), t(null);
      }
    );
  });
}
async function Wr(n) {
  if (!await Ae()) return { attempted: !1, ok: !1 };
  if (!await Wt()) return { attempted: !0, ok: !1, error: "Not signed in.", failure: "rejected" };
  const r = dr(n);
  if (!r) return { attempted: !0, ok: !1, error: "Nothing extracted to save.", failure: "rejected" };
  const a = Bt(n), s = a && a !== r.fingerprint && await Ue(a) ? { ...r, fingerprint: a } : r;
  try {
    return await Rr(s), { attempted: !0, ok: !0, fingerprint: s.fingerprint };
  } catch (i) {
    return {
      attempted: !0,
      ok: !1,
      fingerprint: s.fingerprint,
      error: i instanceof Error ? i.message : "Sync failed.",
      failure: i instanceof ie ? "rejected" : "unreachable"
    };
  }
}
async function Ge(n) {
  const e = await ke();
  if (!R()?.action?.setBadgeText) return;
  const r = D.aggregate(n), a = r?.classification;
  if (!e.showBadge || !a) {
    await Oe(n, "", "");
    return;
  }
  if (a.confidence < ht.minActionable) {
    await Oe(n, "", "");
    return;
  }
  const s = r?.result?.questions.length ?? 0, i = a.confidence >= ht.confident, o = s > 0 ? String(s) : i ? "✓" : "?";
  await Oe(n, o, i ? "#1e40af" : "#6b7280");
}
async function Oe(n, e, t) {
  const r = R()?.action;
  if (r)
    try {
      await r.setBadgeText({ tabId: n, text: e }), t && await r.setBadgeBackgroundColor({ tabId: n, color: t });
    } catch {
    }
}
const Q = [], Kt = 50;
fr((n) => {
  Q.push(n), Q.length >= Kt && Yt();
});
async function Hr(n) {
  Q.push(n), Q.length >= Kt && await Yt();
}
async function Yt() {
  if (Q.length === 0) return;
  const n = Q.splice(0, Q.length), e = await je.create();
  e && await e.sendTelemetry(n);
}

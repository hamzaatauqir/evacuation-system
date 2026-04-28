import { type ReactNode, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { PageFooter } from "../components/PageFooter";
import { Btn } from "../components/Btn";
import { StatusBadge } from "../components/StatusBadge";
import { api } from "../lib/api";
import { addLocalPortalRequest, clearNursePortal, getLocalPortalRequests, getNursePortal } from "../lib/nursePortal";

export function NursesPortalPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [ctx] = useState(() => getNursePortal());
  const requests = useMemo(() => getLocalPortalRequests(), []);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const [facilityReq, setFacilityReq] = useState({
    category: "",
    urgency: "Normal",
    subject: "",
    details: "",
    preferred_contact_method: "WhatsApp",
  });
  const [stay, setStay] = useState(() => ({
    confirmation_option: "",
    current_facility_name: ctx?.facilityRoster?.facility_name || "",
    area: ctx?.facilityRoster?.facility_area || ctx?.facilityRoster?.area || "",
    room_number: ctx?.facilityRoster?.room_number || "",
    bed_number: ctx?.facilityRoster?.bed_number || "",
    current_phone: ctx?.mobile || "",
    preferred_contact_method: "WhatsApp",
    remarks: "",
  }));
  const [complaint, setComplaint] = useState({ complaint_category: "", priority: "Normal", subject: "", description: "" });
  const [leaving, setLeaving] = useState({
    current_facility: ctx?.facilityRoster?.facility_name || "",
    date_shifted_to_facility: ctx?.facilityRoster?.date_shifted_to_facility || "",
    intended_leaving_date: "",
    reason_category: "",
    new_stay_arrangement: "",
    new_area: "",
    assistance_required: "No",
    remarks: "",
  });
  const [curPwd, setCurPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmNew, setConfirmNew] = useState("");
  const [showPw, setShowPw] = useState(false);

  if (!ctx) {
    navigate("/nurses/login", { replace: true });
    return null;
  }

  const tab = params.get("tab") || "overview";
  const tabs = ["overview", "stay", "complaint", "leaving", "requests", "password"];
  const activeTab = tabs.includes(tab) ? tab : "overview";

  const statusType = (ctx.registrationStatus || "").toLowerCase().includes("resolved")
    ? "resolved"
    : (ctx.registrationStatus || "").toLowerCase().includes("progress")
    ? "processing"
    : "pending";
  const isDoctor = (ctx.professionalCategory || "").toLowerCase() === "doctor";
  const vendorName = ctx.facilityRoster?.vendor_name?.trim() || "";
  const approvedVendorLabel = ctx.facilityRoster?.approved_vendor_label || (vendorName ? `Approved Vendor: ${vendorName}` : "Approved Vendor: To be confirmed");
  const hasEmbassyArrangement = !isDoctor && !!ctx.facilityRoster && (ctx.facilityRoster.current_arrangement || "Embassy Contracted / Arranged") === "Embassy Contracted / Arranged";
  const stayArrangementText = `Your current stay arrangement is recorded as Embassy Contracted / Arranged with ${approvedVendorLabel}.`;

  async function submitFacilityRequest() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post("/api/nurses/facility-assistance", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        category: facilityReq.category,
        urgency: facilityReq.urgency,
        subject: facilityReq.subject || facilityReq.category,
        details: facilityReq.details,
        preferred_contact_method: facilityReq.preferred_contact_method,
      });
      addLocalPortalRequest({ type: "Facility Assistance", summary: `Category: ${facilityReq.category || "N/A"}` });
      setMsg("Facility assistance request submitted for Community Welfare Wing review.");
      setFacilityReq({ category: "", urgency: "Normal", subject: "", details: "", preferred_contact_method: "WhatsApp" });
      setParams({ tab: "requests" });
    } catch (e) {
      setErr((e as Error).message || "Could not submit facility assistance request.");
    } finally {
      setBusy(false);
    }
  }

  async function submitStayConfirmation() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post("/api/nurses/stay-confirmation", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        ...stay,
      });
      addLocalPortalRequest({ type: "Stay Confirmation", summary: "Stay arrangement update submitted." });
      setMsg("Stay arrangement confirmation submitted for Community Welfare Wing review.");
      setParams({ tab: "requests" });
    } catch (e) {
      setErr((e as Error).message || "Could not submit stay arrangement confirmation.");
    } finally {
      setBusy(false);
    }
  }

  async function submitComplaint() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post("/api/nurses/complaint", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        complaint_category: complaint.complaint_category,
        priority: complaint.priority,
        subject: complaint.subject,
        description: complaint.description,
        preferred_contact_method: "WhatsApp",
        consent: true,
      });
      addLocalPortalRequest({ type: "Complaint", summary: `Subject: ${complaint.subject || "N/A"}` });
      setMsg("Complaint submitted. Marked as pending official review.");
      setComplaint({ complaint_category: "", priority: "Normal", subject: "", description: "" });
      setParams({ tab: "requests" });
    } catch (e) {
      setErr((e as Error).message || "Could not submit complaint.");
    } finally {
      setBusy(false);
    }
  }

  async function submitLeavingNotice() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post("/api/nurses/leave-notice", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        current_facility: leaving.current_facility,
        date_shifted_to_facility: leaving.date_shifted_to_facility,
        intended_leaving_date: leaving.intended_leaving_date,
        reason_category: leaving.reason_category,
        new_stay_arrangement: leaving.new_stay_arrangement,
        new_area: leaving.new_area,
        assistance_required: leaving.assistance_required,
        reason: leaving.remarks,
      });
      addLocalPortalRequest({ type: "Leaving Notice", summary: `Move out date: ${leaving.intended_leaving_date || "N/A"}` });
      setMsg("Leaving notice submitted for Community Welfare Wing review.");
      setLeaving({ current_facility: ctx.facilityRoster?.facility_name || "", date_shifted_to_facility: ctx.facilityRoster?.date_shifted_to_facility || "", intended_leaving_date: "", reason_category: "", new_stay_arrangement: "", new_area: "", assistance_required: "No", remarks: "" });
      setParams({ tab: "requests" });
    } catch (e) {
      setErr((e as Error).message || "Could not submit leaving notice.");
    } finally {
      setBusy(false);
    }
  }

  async function submitChangePassword() {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await api.post("/api/nurses/change-password", {
        nurse_reference_id: ctx.referenceId,
        current_password: curPwd,
        new_password: newPwd,
        confirm_password: confirmNew,
      });
      setMsg("Password updated.");
      setCurPwd("");
      setNewPwd("");
      setConfirmNew("");
    } catch (e) {
      setErr((e as Error).message || "Could not change password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />
      <main style={{ flex: 1, maxWidth: 1120, margin: "0 auto", width: "100%", padding: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, gap: 10, flexWrap: "wrap" }}>
          <h1 style={{ fontSize: 28, color: "#2D4A6B" }}>Welcome, {ctx.fullName || "Nurse"}</h1>
          <Btn
            variant="light"
            onClick={() => {
              clearNursePortal();
              navigate("/nurses/login");
            }}
          >
            Logout / Clear Portal Session
          </Btn>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
          {tabs.map((t) => (
            <Btn key={t} variant={activeTab === t ? "navy" : "light"} onClick={() => setParams({ tab: t })}>
              {t === "overview"
                ? "Overview"
                : t === "stay"
                  ? "Stay Arrangement"
                  : t === "complaint"
                    ? "Complaint"
                    : t === "leaving"
                      ? "Leaving Notice"
                      : t === "requests"
                        ? "My Requests"
                        : "Change password"}
            </Btn>
          ))}
        </div>

        {(msg || err) ? (
          <div style={{ marginBottom: 14, background: err ? "#fff4f4" : "#f3fff4", color: err ? "#991b1b" : "#166534", border: `1px solid ${err ? "#fecaca" : "#bbf7d0"}`, borderRadius: 10, padding: 10 }}>
            {err || msg}
          </div>
        ) : null}

        {activeTab === "overview" ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 14, marginBottom: 14 }}>
              <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: 16 }}>
                <h3 style={{ marginBottom: 10, color: "#2D4A6B" }}>Nurse Profile Summary</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <Field label="Reference ID" value={ctx.referenceId || "-"} />
                  <Field label="Name" value={ctx.fullName || "-"} />
                  <Field label="Email" value={ctx.email || "-"} />
                  <Field label="Passport" value={ctx.passportMasked || "-"} />
                  <Field label="Civil ID (if any)" value={ctx.civilIdMasked || "—"} />
                  <Field label="Status" value={ctx.registrationStatus || "-"} />
                  <Field label="Last Updated" value={ctx.lastUpdated || "-"} />
                  <Field label="Current Stay Arrangement" value={ctx.facilityRoster?.current_status || "Not linked to a facility record"} />
                  {hasEmbassyArrangement ? <Field label="Approved Vendor" value={approvedVendorLabel.replace("Approved Vendor: ", "")} /> : null}
                  <Field label="Facility" value={ctx.facilityRoster?.facility_name || "—"} />
                  <Field label="Area" value={ctx.facilityRoster?.facility_area || ctx.facilityRoster?.area || "—"} />
                </div>
              </div>
              <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: 16 }}>
                <h3 style={{ marginBottom: 10, color: "#2D4A6B" }}>Tracking / Status</h3>
                <div style={{ marginBottom: 8 }}><StatusBadge type={statusType as any} label={ctx.registrationStatus || "Pending"} /></div>
                <p style={{ color: "#5B6773", fontSize: 13, marginTop: 8 }}><strong>Embassy remarks:</strong> {ctx.remarks || "No remarks yet."}</p>
                <p style={{ color: "#5B6773", fontSize: 13, marginTop: 8 }}><strong>What you should do now:</strong> Keep tracking this portal for review updates and follow any Embassy remarks.</p>
              </div>
            </div>
            <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: 16 }}>
              <h3 style={{ marginBottom: 8, color: "#2D4A6B" }}>Embassy Messages</h3>
              <p style={{ color: "#5B6773" }}>{ctx.remarks || "Embassy messages and remarks will appear here after review."}</p>
            </div>
          </>
        ) : null}

        {activeTab === "stay" ? (
          <div style={{ display: "grid", gap: 14 }}>
            {ctx.facilityRoster && !isDoctor ? (
              <FormCard title="Stay Arrangement Confirmation">
                <p style={{ color: "#5B6773", fontSize: 13, lineHeight: 1.6 }}>
                  {hasEmbassyArrangement ? stayArrangementText : "Our records show that you may be linked to an Embassy-facilitated stay arrangement through an approved service provider."}
                  {" "}Please confirm your current stay details so the Community Welfare Wing can maintain accurate welfare records and provide
                  timely support where required.
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10 }}>
                  <Field label="Roster Reference" value={ctx.facilityRoster.roster_reference || "-"} />
                  <Field label="Facility / Building" value={ctx.facilityRoster.facility_name || "-"} />
                  {hasEmbassyArrangement ? <Field label="Approved Vendor" value={approvedVendorLabel.replace("Approved Vendor: ", "")} /> : null}
                  <Field label="Notice Period Start" value={ctx.facilityRoster.notice_period_start_date || "-"} />
                </div>
                <label>
                  Confirmation option
                  <select className="f-input" value={stay.confirmation_option} onChange={(e) => setStay({ ...stay, confirmation_option: e.target.value })}>
                    <option value="">Select</option>
                    <option value="currently_staying">I am currently staying at this facility</option>
                    <option value="shifted_from_facility">I have shifted from this facility</option>
                    <option value="intends_to_leave">I intend to leave/change my stay arrangement</option>
                    <option value="details_correction">My facility details require correction</option>
                    <option value="assistance_requested">I need welfare assistance/follow-up</option>
                  </select>
                </label>
                <label>Current facility name<input className="f-input" value={stay.current_facility_name} onChange={(e) => setStay({ ...stay, current_facility_name: e.target.value })} /></label>
                <label>Area<input className="f-input" value={stay.area} onChange={(e) => setStay({ ...stay, area: e.target.value })} /></label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <label>Room<input className="f-input" value={stay.room_number} onChange={(e) => setStay({ ...stay, room_number: e.target.value })} /></label>
                  <label>Bed<input className="f-input" value={stay.bed_number} onChange={(e) => setStay({ ...stay, bed_number: e.target.value })} /></label>
                </div>
                <label>Current phone / WhatsApp<input className="f-input" value={stay.current_phone} onChange={(e) => setStay({ ...stay, current_phone: e.target.value })} /></label>
                <label>
                  Preferred contact method
                  <select className="f-input" value={stay.preferred_contact_method} onChange={(e) => setStay({ ...stay, preferred_contact_method: e.target.value })}>
                    <option>WhatsApp</option>
                    <option>Phone Call</option>
                    <option>Email</option>
                  </select>
                </label>
                <label>Remarks<textarea className="f-input" value={stay.remarks} onChange={(e) => setStay({ ...stay, remarks: e.target.value })} /></label>
                <Btn variant="primary" disabled={busy || !stay.confirmation_option} onClick={submitStayConfirmation}>{busy ? "Submitting..." : "Submit Stay Confirmation"}</Btn>
              </FormCard>
            ) : (
              <FormCard title="Stay Arrangement Confirmation">
                <p style={{ color: "#5B6773", fontSize: 13, lineHeight: 1.6 }}>
                  No Embassy-facilitated facility record is currently linked to your profile.
                  You may still submit a facility assistance request if you need Community Welfare Wing follow-up.
                </p>
              </FormCard>
            )}
            <FormCard title="Facility Assistance Request">
              <p style={{ color: "#5B6773", fontSize: 13, lineHeight: 1.6 }}>
                Please share any welfare-related service difficulty or request for assistance regarding your current stay arrangement.
                The Community Welfare Wing will review the request and may contact you for follow-up.
              </p>
              <label>
                Category
                <select className="f-input" value={facilityReq.category} onChange={(e) => setFacilityReq({ ...facilityReq, category: e.target.value })}>
                  <option value="">Select</option>
                  <option>General welfare assistance</option>
                  <option>Basic services concern</option>
                  <option>Facility maintenance concern</option>
                  <option>Shared space concern</option>
                  <option>Safety or security concern</option>
                  <option>Cleanliness / hygiene concern</option>
                  <option>Communication / coordination concern</option>
                  <option>Transport-related concern</option>
                  <option>Request for meeting or callback</option>
                  <option>Request to change stay arrangement</option>
                  <option>Other</option>
                </select>
              </label>
              <label>
                Urgency
                <select className="f-input" value={facilityReq.urgency} onChange={(e) => setFacilityReq({ ...facilityReq, urgency: e.target.value })}>
                  <option>Normal</option>
                  <option>Priority</option>
                  <option>Urgent</option>
                </select>
              </label>
              <label>Subject<input className="f-input" value={facilityReq.subject} onChange={(e) => setFacilityReq({ ...facilityReq, subject: e.target.value })} /></label>
              <label>Details<textarea className="f-input" value={facilityReq.details} onChange={(e) => setFacilityReq({ ...facilityReq, details: e.target.value })} /></label>
              <label>
                Preferred contact method
                <select className="f-input" value={facilityReq.preferred_contact_method} onChange={(e) => setFacilityReq({ ...facilityReq, preferred_contact_method: e.target.value })}>
                  <option>WhatsApp</option>
                  <option>Phone Call</option>
                  <option>Email</option>
                </select>
              </label>
              <Btn variant="primary" disabled={busy || !facilityReq.category || !facilityReq.details} onClick={submitFacilityRequest}>{busy ? "Submitting..." : "Submit Facility Assistance Request"}</Btn>
            </FormCard>
          </div>
        ) : null}

        {activeTab === "complaint" ? (
          <FormCard title="Complaint / Welfare Issue">
            <label>Category<input className="f-input" value={complaint.complaint_category} onChange={(e) => setComplaint({ ...complaint, complaint_category: e.target.value })} /></label>
            <label>Priority<select className="f-input" value={complaint.priority} onChange={(e) => setComplaint({ ...complaint, priority: e.target.value })}><option>Normal</option><option>Important</option><option>Urgent</option></select></label>
            <label>Subject<input className="f-input" value={complaint.subject} onChange={(e) => setComplaint({ ...complaint, subject: e.target.value })} /></label>
            <label>Details<textarea className="f-input" value={complaint.description} onChange={(e) => setComplaint({ ...complaint, description: e.target.value })} /></label>
            <Btn variant="primary" disabled={busy} onClick={submitComplaint}>{busy ? "Submitting..." : "Submit Complaint"}</Btn>
          </FormCard>
        ) : null}

        {activeTab === "leaving" ? (
          <FormCard title="Leaving Notice / Change of Stay Arrangement">
            <p style={{ color: "#5B6773", fontSize: 13, lineHeight: 1.6 }}>
              If you intend to leave or change your current stay arrangement, please submit a Leaving Notice through this portal so that your record can be reviewed and updated in time.
            </p>
            {ctx.facilityRoster?.notice_period_start_date ? (
              <p style={{ color: "#2D4A6B", fontSize: 13, lineHeight: 1.6, background: "#F7FAFC", border: "1px solid #E3EBF0", borderRadius: 10, padding: 10 }}>
                Based on the dates recorded, your notice period start date is {ctx.facilityRoster.notice_period_start_date}. If you intend to leave or change your stay arrangement, please submit your notice before the applicable deadline where possible.
              </p>
            ) : null}
            <label>Current Facility / Building<input className="f-input" value={leaving.current_facility} onChange={(e) => setLeaving({ ...leaving, current_facility: e.target.value })} /></label>
            <label>Date shifted to facility<input className="f-input" type="date" value={leaving.date_shifted_to_facility} onChange={(e) => setLeaving({ ...leaving, date_shifted_to_facility: e.target.value })} /></label>
            <label>Intended leaving date<input className="f-input" type="date" value={leaving.intended_leaving_date} onChange={(e) => setLeaving({ ...leaving, intended_leaving_date: e.target.value })} /></label>
            <label>
              Reason / category
              <select className="f-input" value={leaving.reason_category} onChange={(e) => setLeaving({ ...leaving, reason_category: e.target.value })}>
                <option value="">Select</option>
                <option>Change of stay arrangement</option>
                <option>Shifted to private option</option>
                <option>Shifted to family / relative</option>
                <option>Workplace-arranged option</option>
                <option>Facility details require correction</option>
                <option>Other</option>
              </select>
            </label>
            <label>New stay arrangement if known<input className="f-input" value={leaving.new_stay_arrangement} onChange={(e) => setLeaving({ ...leaving, new_stay_arrangement: e.target.value })} /></label>
            <label>New area if known<input className="f-input" value={leaving.new_area} onChange={(e) => setLeaving({ ...leaving, new_area: e.target.value })} /></label>
            <label>
              Do you require assistance in identifying alternative options?
              <select className="f-input" value={leaving.assistance_required} onChange={(e) => setLeaving({ ...leaving, assistance_required: e.target.value })}>
                <option>No</option>
                <option>Yes</option>
              </select>
            </label>
            <label>Remarks<textarea className="f-input" value={leaving.remarks} onChange={(e) => setLeaving({ ...leaving, remarks: e.target.value })} /></label>
            <Btn variant="primary" disabled={busy} onClick={submitLeavingNotice}>{busy ? "Submitting..." : "Submit Leaving Notice"}</Btn>
          </FormCard>
        ) : null}

        {activeTab === "password" ? (
          <FormCard title="Change password">
            <label>
              Current password
              <input
                className="f-input"
                type={showPw ? "text" : "password"}
                value={curPwd}
                onChange={(e) => setCurPwd(e.target.value)}
                autoComplete="current-password"
              />
            </label>
            <label>
              New password
              <input
                className="f-input"
                type={showPw ? "text" : "password"}
                value={newPwd}
                onChange={(e) => setNewPwd(e.target.value)}
                autoComplete="new-password"
              />
            </label>
            <label>
              Confirm new password
              <input
                className="f-input"
                type={showPw ? "text" : "password"}
                value={confirmNew}
                onChange={(e) => setConfirmNew(e.target.value)}
                autoComplete="new-password"
              />
            </label>
            <button
              type="button"
              className="f-input"
              style={{ width: "auto", cursor: "pointer", maxWidth: 120 }}
              onClick={() => setShowPw((s) => !s)}
            >
              {showPw ? "Hide passwords" : "Show passwords"}
            </button>
            <Btn variant="primary" disabled={busy} onClick={submitChangePassword}>
              {busy ? "Updating…" : "Update password"}
            </Btn>
          </FormCard>
        ) : null}

        {activeTab === "requests" ? (
          <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: 16, marginBottom: 14 }}>
            <h3 style={{ marginBottom: 12, color: "#2D4A6B" }}>My Requests / History</h3>
            {ctx.complaints?.length ? (
              <div style={{ display: "grid", gap: 8, marginBottom: 10 }}>
                {ctx.complaints.slice(0, 10).map((c, idx) => (
                  <div key={c.complaint_id || idx} style={{ border: "1px solid #E3EBF0", borderRadius: 10, padding: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                      <strong>{c.subject || "Complaint"}</strong>
                      <StatusBadge type={(c.status || "").toLowerCase().includes("resolved") ? "resolved" : "processing"} label={c.status || "In Review"} />
                    </div>
                    <p style={{ fontSize: 12, color: "#5B6773" }}>Type: {c.category || "-"} | Submitted: {c.submitted_date || "-"}</p>
                  </div>
                ))}
              </div>
            ) : null}
            {requests.length ? (
              <div style={{ display: "grid", gap: 8 }}>
                {requests.map((r) => (
                  <div key={r.id} style={{ border: "1px dashed #D8E0E7", borderRadius: 10, padding: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                      <strong>{r.type}</strong>
                      <StatusBadge type="pending" label={`${r.status} (pending official review)`} />
                    </div>
                    <p style={{ fontSize: 12, color: "#5B6773" }}>{r.summary}</p>
                    <p style={{ fontSize: 11, color: "#7A8A96" }}>{r.submittedAt}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: "#5B6773" }}>Submitted requests will appear here once processed by the Embassy.</p>
            )}
          </div>
        ) : null}
      </main>
      <PageFooter />
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return <div><div style={{ fontSize: 11, color: '#7A8A96', marginBottom: 2 }}>{label}</div><div style={{ fontSize: 13, fontWeight: 600 }}>{value}</div></div>;
}

function FormCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: 16, display: "grid", gap: 10 }}>
      <h3 style={{ color: "#2D4A6B" }}>{title}</h3>
      {children}
    </div>
  );
}

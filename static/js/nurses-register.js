(function () {
  const stepsBox = document.getElementById('steps');
  const form = document.getElementById('regForm');
  if (!form || !stepsBox) return;

  const STEPS = [
    ['step_grading_data_submitted_oec','Grading Letter Data Submitted to OEC'],
    ['step_mofa_kuwait_attestation','Attestation by MOFA Kuwait'],
    ['step_grading_letter_collected_embassy','Grading Letter Collected from Embassy'],
    ['step_documents_submitted_sdu_moh','Submission of Documents in Staff Development Unit (MOH)'],
    ['step_fingerprint_scanning','Fingerprint Scanning'],
    ['step_civil_id_number_generation','Civil ID Number Generation'],
    ['step_medical_report_issuance','Medical Report Issuance'],
    ['step_first_salary_cheque_locum','First Salary Cheque (Locum)'],
    ['step_iqama_application_filed','Iqama Application Filed'],
    ['step_civil_id_application_submitted','Civil ID Application Submitted After Above Steps'],
    ['step_second_salary_cheque_locum_received','2nd Salary Cheque (Locum Received)'],
    ['step_medical_license_application_filed','Medical License Application Filed'],
    ['step_committee_paper_received','Committee Paper Received'],
    ['step_barateen_paper_submission','Barateen Paper Submission'],
    ['step_salary_regular_disbursement','Salary Regular Disbursement']
  ];

  stepsBox.innerHTML = STEPS.map(([key, label]) =>
    '<div class="step-item"><strong>' + label + '</strong><div>' +
    '<label><input type="radio" name="' + key + '" value="0" checked> Not Completed</label> ' +
    '<label style="margin-left:12px"><input type="radio" name="' + key + '" value="1"> Completed</label>' +
    '</div></div>'
  ).join('');

  function stepVal(key) {
    const el = document.querySelector('input[name="' + key + '"]:checked');
    return el ? el.value : '0';
  }

  let currentStep = 1;
  const panes = Array.from(document.querySelectorAll('.nurses-pane'));
  const stepNodes = Array.from(document.querySelectorAll('.nurses-step'));
  const backBtn = document.getElementById('btn_back');
  const nextBtn = document.getElementById('btn_next');
  const stepError = document.getElementById('step_error');
  const msg = document.getElementById('msg');

  function showStep(n) {
    currentStep = n;
    panes.forEach((p) => p.classList.toggle('active', Number(p.dataset.pane) === n));
    stepNodes.forEach((s) => s.classList.toggle('active', Number(s.dataset.step) === n));
    backBtn.style.display = n === 1 ? 'none' : 'inline-block';
    nextBtn.style.display = n === 4 ? 'none' : 'inline-block';
    stepError.style.display = 'none';
  }

  function validateStep(n) {
    const pane = document.querySelector('.nurses-pane[data-pane="' + n + '"]');
    const required = Array.from(pane.querySelectorAll('input[required],select[required],textarea[required]'));
    for (const field of required) {
      if (!field.value) {
        stepError.textContent = 'Please fill all required fields in this step.';
        stepError.style.display = 'block';
        field.focus();
        return false;
      }
    }
    stepError.style.display = 'none';
    return true;
  }

  nextBtn.addEventListener('click', function () {
    if (validateStep(currentStep)) showStep(Math.min(4, currentStep + 1));
  });
  backBtn.addEventListener('click', function () {
    showStep(Math.max(1, currentStep - 1));
  });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    if (!validateStep(4)) return false;
    const p = {
      full_name: document.getElementById('full_name').value,
      passport_number: document.getElementById('passport_number').value,
      cnic: document.getElementById('cnic').value,
      civil_id: document.getElementById('civil_id').value,
      mobile: document.getElementById('mobile').value,
      email: document.getElementById('email').value,
      arrival_date: document.getElementById('arrival_date').value,
      batch_number: document.getElementById('batch_number').value,
      hospital: document.getElementById('hospital').value,
      designation: document.getElementById('designation').value,
      degree_type: document.getElementById('degree_type').value,
      moh_offer_salary_kwd: document.getElementById('moh_offer_salary_kwd').value,
      grading_letter_issued: document.getElementById('grading_letter_issued').value,
      current_accommodation: document.getElementById('current_accommodation').value,
      applying_for_accommodation: document.getElementById('applying_for_accommodation').value,
      remarks: document.getElementById('remarks').value,
      issue_notice: document.getElementById('issue_notice').value
    };
    for (const [key] of STEPS) p[key] = stepVal(key);
    const r = await fetch('/api/nurses/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(p)
    });
    const d = await r.json();
    if (d.success) {
      const q = '?ref=' + encodeURIComponent(d.reference_id) +
        '&name=' + encodeURIComponent(p.full_name) +
        '&passport=' + encodeURIComponent(p.passport_number);
      window.location = '/nurses/register/success' + q;
    } else {
      msg.textContent = d.error || 'Submission failed';
    }
    return false;
  });
})();

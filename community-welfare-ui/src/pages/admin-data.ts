// Mock data — mirrors the design's portal-admin.jsx fixtures.
// In a real deployment these would be loaded from server.py via api.ts.

export interface Nurse {
  id: string;
  name: string;
  passport: string;
  civil: string;
  hospital: string;
  dept: string;
  type: "Registration" | "Accommodation" | "Complaint" | "Leaving Notice";
  priority: "low" | "medium" | "high" | "urgent";
  status: "pending" | "processing" | "assigned" | "resolved";
  assigned: string;
  updated: string;
  phone: string;
  address: string;
}

export const NURSES: Nurse[] = [
  { id: "CWR-2025-001", name: "Fatima Malik", passport: "AK1234567", civil: "285-123-4567", hospital: "Al Sabah Hospital", dept: "Cardiology", type: "Registration", priority: "medium", status: "pending", assigned: "Officer Khalid", updated: "26 Apr 2025", phone: "+965 9123 4567", address: "Salmiya Block 10" },
  { id: "CWR-2025-002", name: "Sana Rehman", passport: "BK9876543", civil: "290-456-7890", hospital: "Mubarak Al-Kabeer Hospital", dept: "Pediatrics", type: "Accommodation", priority: "high", status: "processing", assigned: "Officer Ayesha", updated: "25 Apr 2025", phone: "+965 9234 5678", address: "Hawalli Block 4" },
  { id: "CWR-2025-003", name: "Nadia Qureshi", passport: "CK5551234", civil: "282-789-0123", hospital: "Al Farwaniya Hospital", dept: "ICU", type: "Complaint", priority: "urgent", status: "assigned", assigned: "Officer Khalid", updated: "25 Apr 2025", phone: "+965 9345 6789", address: "Farwaniya Block 2" },
  { id: "CWR-2025-004", name: "Rabia Siddiqui", passport: "DK1112223", civil: "295-234-5678", hospital: "Al Adan Hospital", dept: "Surgery", type: "Registration", priority: "low", status: "resolved", assigned: "Officer Hira", updated: "24 Apr 2025", phone: "+965 9456 7890", address: "Fahaheel Block 7" },
  { id: "CWR-2025-005", name: "Zara Ahmed", passport: "EK4445556", civil: "284-567-8901", hospital: "Kuwait Cancer Control Center", dept: "Oncology", type: "Leaving Notice", priority: "medium", status: "pending", assigned: "Unassigned", updated: "24 Apr 2025", phone: "+965 9567 8901", address: "Rumaithiya" },
  { id: "CWR-2025-006", name: "Hina Butt", passport: "FK7778889", civil: "291-890-1234", hospital: "Al Razi Hospital", dept: "Orthopaedics", type: "Accommodation", priority: "high", status: "processing", assigned: "Officer Ayesha", updated: "23 Apr 2025", phone: "+965 9678 9012", address: "Salmiya Block 3" },
  { id: "CWR-2025-007", name: "Samra Iqbal", passport: "GK2223334", civil: "287-123-4560", hospital: "Ibn Sina Hospital", dept: "Neurology", type: "Complaint", priority: "high", status: "pending", assigned: "Unassigned", updated: "23 Apr 2025", phone: "+965 9789 0123", address: "Sulaibiyya" },
  { id: "CWR-2025-008", name: "Madiha Chaudhry", passport: "HK5556667", civil: "293-456-7891", hospital: "Dar Al Shifa Hospital", dept: "Gynaecology", type: "Registration", priority: "low", status: "resolved", assigned: "Officer Hira", updated: "22 Apr 2025", phone: "+965 9890 1234", address: "Nugra Block 1" },
  { id: "CWR-2025-009", name: "Amna Tariq", passport: "IK8889990", civil: "286-789-0124", hospital: "Kuwait Oil Company Hospital", dept: "Emergency", type: "Accommodation", priority: "urgent", status: "assigned", assigned: "Officer Khalid", updated: "22 Apr 2025", phone: "+965 9901 2345", address: "Ahmadi Block 11" },
  { id: "CWR-2025-010", name: "Shazia Perveen", passport: "JK1112224", civil: "298-012-3456", hospital: "American Mission Hospital", dept: "ENT", type: "Registration", priority: "medium", status: "pending", assigned: "Unassigned", updated: "21 Apr 2025", phone: "+965 9012 3456", address: "Rumaithiya" },
  { id: "CWR-2025-011", name: "Bushra Nawaz", passport: "KK4445557", civil: "283-345-6789", hospital: "Royale Hayat Hospital", dept: "Dermatology", type: "Leaving Notice", priority: "low", status: "resolved", assigned: "Officer Ayesha", updated: "20 Apr 2025", phone: "+965 9123 4568", address: "Salmiya Block 8" },
  { id: "CWR-2025-012", name: "Asma Kausar", passport: "LK7778890", civil: "296-678-9012", hospital: "Gulf International Hospital", dept: "Psychiatry", type: "Complaint", priority: "high", status: "processing", assigned: "Officer Khalid", updated: "20 Apr 2025", phone: "+965 9234 5679", address: "Hawalli Block 2" },
];

export interface LegalCase {
  id: string;
  name: string;
  type: string;
  status: "pending" | "processing" | "assigned" | "resolved";
  priority: "low" | "medium" | "high" | "urgent";
  assigned: string;
  updated: string;
}

export const LEGAL_CASES: LegalCase[] = [
  { id: "LGL-2025-001", name: "Muhammad Iqbal", type: "Labour Complaint", status: "processing", priority: "high", assigned: "Officer Raza", updated: "26 Apr 2025" },
  { id: "LGL-2025-002", name: "Ali Hassan", type: "OPF Card Guidance", status: "pending", priority: "medium", assigned: "Unassigned", updated: "25 Apr 2025" },
  { id: "LGL-2025-003", name: "Tariq Mahmood", type: "Legal Assistance", status: "assigned", priority: "urgent", assigned: "Officer Khalid", updated: "24 Apr 2025" },
  { id: "LGL-2025-004", name: "Khalid Mehmood", type: "Welfare Support", status: "resolved", priority: "low", assigned: "Officer Hira", updated: "22 Apr 2025" },
  { id: "LGL-2025-005", name: "Shahid Anwar", type: "Labour Complaint", status: "pending", priority: "high", assigned: "Unassigned", updated: "21 Apr 2025" },
];

export interface DeathCase {
  id: string;
  name: string;
  contact: string;
  status: "pending" | "processing" | "assigned" | "resolved";
  docStatus: "Not Started" | "In Progress" | "Incomplete" | "Complete";
  priority: "low" | "medium" | "high" | "urgent";
  assigned: string;
  updated: string;
}

export const DEATH_CASES: DeathCase[] = [
  { id: "DTH-2025-001", name: "Muhammad Nawaz", contact: "Fatima Nawaz (Spouse)", status: "processing", docStatus: "Incomplete", priority: "urgent", assigned: "Officer Khalid", updated: "26 Apr 2025" },
  { id: "DTH-2025-002", name: "Javed Iqbal", contact: "Rashid Iqbal (Brother)", status: "pending", docStatus: "Not Started", priority: "high", assigned: "Unassigned", updated: "24 Apr 2025" },
  { id: "DTH-2025-003", name: "Yasmin Bibi", contact: "Akram Khan (Employer)", status: "assigned", docStatus: "In Progress", priority: "urgent", assigned: "Officer Raza", updated: "22 Apr 2025" },
  { id: "DTH-2025-004", name: "Arshad Mehmood", contact: "Rukhsana (Spouse)", status: "resolved", docStatus: "Complete", priority: "medium", assigned: "Officer Hira", updated: "18 Apr 2025" },
];

export function cap(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

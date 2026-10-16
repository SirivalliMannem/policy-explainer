import { TheRecord } from '../components/dashboard/TheRecord';

/** The Audit Log: every recorded policy answer from the Evidence Ledger, on its own page. */
export function AuditLogPage() {
  return (
    <div className="max-w-7xl mx-auto font-sans pb-10">
      <TheRecord />
    </div>
  );
}

export default AuditLogPage;

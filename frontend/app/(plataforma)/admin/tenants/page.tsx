import { PlataformaGate } from "@/components/admin/PlataformaGate";
import { TenantsAdmin } from "@/components/admin/TenantsAdmin";

export default function AdminTenantsPage() {
  return (
    <PlataformaGate>
      <TenantsAdmin />
    </PlataformaGate>
  );
}

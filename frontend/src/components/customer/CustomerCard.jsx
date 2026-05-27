import { useNavigate } from "react-router-dom";
import { Eye, Phone, MapPin } from "lucide-react";
import ChurnScoreBadge from "./ChurnScoreBadge";
import RiskLevelBadge from "./RiskLevelBadge";
import { formatRelativeTime, getInitials, maskPhone } from "../../lib/utils";

function CustomerCard({ customer }) {
  const navigate = useNavigate();

  return (
    <div
      className="bg-white p-4 rounded-lg shadow hover:shadow-md transition cursor-pointer"
      onClick={() => navigate(`/customers/${customer.customer_id}`)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary-100 to-primary-200 flex items-center justify-center border border-primary-50">
            <span className="text-primary-700 font-bold">
              {getInitials(customer.name)}
            </span>
          </div>
          <div>
            <h3 className="font-semibold text-primary-900">{customer.name}</h3>
            <div className="flex items-center gap-2 text-sm text-stone-500">
              <Phone className="h-3 w-3" />
              <span>{maskPhone(customer.phone_display || customer.phone)}</span>
            </div>
          </div>
        </div>
        <RiskLevelBadge score={customer.risk_score} level={customer.risk_label} />
      </div>

      <div className="mb-3">
        <div className="flex items-center justify-between text-sm text-stone-500 mb-1">
          <span>Risk Score</span>
          <span className="font-medium">
            {(customer.risk_score * 100).toFixed(0)}%
          </span>
        </div>
        <ChurnScoreBadge score={customer.risk_score} showLabel={false} />
      </div>

      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-1 text-stone-500">
          <MapPin className="h-3 w-3" />
          <span>{customer.city || "-"}</span>
        </div>
        <span className="text-stone-500">
          Kunjungan: {formatRelativeTime(customer.last_visit)}
        </span>
      </div>

      <div className="mt-3 pt-3 border-t flex justify-end">
        <button
          className="flex items-center gap-1 text-primary-600 hover:text-primary-700 text-sm font-medium"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/customers/${customer.customer_id}`);
          }}
        >
          <Eye className="h-4 w-4" />
          Lihat Detail
        </button>
      </div>
    </div>
  );
}

export default CustomerCard;

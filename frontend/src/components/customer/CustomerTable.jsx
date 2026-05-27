import { useNavigate } from "react-router-dom";
import { Eye } from "lucide-react";
import Table from "../common/Table";
import ChurnScoreBadge from "./ChurnScoreBadge";
import RiskLevelBadge from "./RiskLevelBadge";
import { formatRelativeTime, getInitials } from "../../lib/utils";

function CustomerTable({ customers }) {
  const navigate = useNavigate();

  return (
    <Table>
      <Table.Header>
        <Table.Row>
          <Table.Head>Customer</Table.Head>
          <Table.Head>Kota</Table.Head>
          <Table.Head>Kunjungan Terakhir</Table.Head>
          <Table.Head>Risk Score</Table.Head>
          <Table.Head>Status</Table.Head>
          <Table.Head className="text-right">Aksi</Table.Head>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {customers.map((customer) => (
          <Table.Row
            key={customer.customer_id}
            onClick={() => navigate(`/customers/${customer.customer_id}`)}
            className="hover:bg-primary-50 transition-colors cursor-pointer"
          >
            <Table.Cell>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary-100 to-primary-200 flex items-center justify-center flex-shrink-0 border border-primary-50">
                  <span className="text-primary-700 font-bold text-sm">
                    {getInitials(customer.name)}
                  </span>
                </div>
                <div>
                  <div className="font-semibold text-primary-800">
                    {customer.name}
                  </div>
                  <div className="text-stone-500 text-xs font-medium">
                    {customer.email || "-"}
                  </div>
                </div>
              </div>
            </Table.Cell>
            <Table.Cell className="text-stone-500 font-medium">
              {customer.city || "-"}
            </Table.Cell>
            <Table.Cell className="text-stone-500 font-medium">
              {formatRelativeTime(customer.last_visit)}
            </Table.Cell>
            <Table.Cell>
              <div className="w-32">
                <ChurnScoreBadge score={customer.risk_score} size="sm" />
              </div>
            </Table.Cell>
            <Table.Cell>
              <RiskLevelBadge
                score={customer.risk_score}
                level={customer.risk_label}
              />
            </Table.Cell>
            <Table.Cell className="text-right">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/customers/${customer.customer_id}`);
                }}
                className="text-primary-600 hover:text-primary-800 p-2 hover:bg-primary-50 rounded-lg transition-colors"
              >
                <Eye className="h-5 w-5" />
              </button>
            </Table.Cell>
          </Table.Row>
        ))}
      </Table.Body>
    </Table>
  );
}

export default CustomerTable;

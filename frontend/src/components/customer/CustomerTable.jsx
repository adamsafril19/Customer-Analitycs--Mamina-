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
          <Table.Head>Churn Score</Table.Head>
          <Table.Head>Status</Table.Head>
          <Table.Head className="text-right">Aksi</Table.Head>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {customers.map((customer) => (
          <Table.Row
            key={customer.customer_id}
            onClick={() => navigate(`/customers/${customer.customer_id}`)}
            className="hover:bg-gray-50"
          >
            <Table.Cell>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                  <span className="text-blue-600 font-medium text-sm">
                    {getInitials(customer.name)}
                  </span>
                </div>
                <div>
                  <div className="font-medium text-gray-900">
                    {customer.name}
                  </div>
                  <div className="text-gray-500 text-xs">
                    {customer.email || "-"}
                  </div>
                </div>
              </div>
            </Table.Cell>
            <Table.Cell className="text-gray-500">
              {customer.city || "-"}
            </Table.Cell>
            <Table.Cell className="text-gray-500">
              {formatRelativeTime(customer.last_visit)}
            </Table.Cell>
            <Table.Cell>
              <div className="w-32">
                <ChurnScoreBadge score={customer.churn_score} size="sm" />
              </div>
            </Table.Cell>
            <Table.Cell>
              <RiskLevelBadge score={customer.churn_score} />
            </Table.Cell>
            <Table.Cell className="text-right">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/customers/${customer.customer_id}`);
                }}
                className="text-blue-600 hover:text-blue-800 p-1"
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

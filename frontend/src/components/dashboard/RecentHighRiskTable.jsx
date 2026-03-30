import { useNavigate } from "react-router-dom";
import { Eye } from "lucide-react";
import Table from "../common/Table";
import RiskLevelBadge from "../customer/RiskLevelBadge";
import { formatRelativeTime } from "../../lib/utils";

function RecentHighRiskTable({ customers }) {
  const navigate = useNavigate();

  if (!customers || customers.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Customer Berisiko Tinggi Terbaru
        </h3>
        <div className="text-center py-8 text-gray-500">
          Tidak ada customer berisiko tinggi
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Customer Berisiko Tinggi Terbaru
      </h3>
      <Table>
        <Table.Header>
          <Table.Row>
            <Table.Head>Nama</Table.Head>
            <Table.Head>Kunjungan Terakhir</Table.Head>
            <Table.Head>Skor</Table.Head>
            <Table.Head>Status</Table.Head>
            <Table.Head className="text-right">Aksi</Table.Head>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {customers.map((customer) => (
            <Table.Row
              key={customer.customer_id}
              onClick={() => navigate(`/customers/${customer.customer_id}`)}
            >
              <Table.Cell className="font-medium text-gray-900">
                {customer.name}
              </Table.Cell>
              <Table.Cell className="text-gray-500">
                {formatRelativeTime(
                  customer.last_visit || customer.last_seen_at
                )}
              </Table.Cell>
              <Table.Cell className="font-semibold text-red-600">
                {customer.churn_score != null
                  ? `${(customer.churn_score * 100).toFixed(0)}%`
                  : "-"}
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
    </div>
  );
}

export default RecentHighRiskTable;

// src/components/dashboard/RecentHighRiskTable.jsx
import { useNavigate } from "react-router-dom";
import { Eye, Baby } from "lucide-react";
import Table from "../common/Table";
import RiskLevelBadge from "../customer/RiskLevelBadge";
import { formatRelativeTime } from "../../lib/utils";

function RecentHighRiskTable({ customers }) {
  const navigate = useNavigate();

  if (!customers || customers.length === 0) {
    return (
      <div className="bg-white/70 backdrop-blur-sm rounded-2xl border border-pink-100 shadow-md p-6">
        <h3 className="text-lg font-bold bg-gradient-to-r from-rose-500 to-pink-500 bg-clip-text text-transparent mb-4 flex items-center gap-2">
          <Baby className="h-5 w-5 text-pink-400" />
          Customer Berisiko Tinggi Terbaru
        </h3>
        <div className="text-center py-8 text-stone-400 font-medium">
          Tidak ada customer berisiko tinggi ✨
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white/70 backdrop-blur-sm rounded-2xl border border-rose-100 shadow-md p-6 transition-all hover:shadow-lg">
      <h3 className="text-lg font-bold bg-gradient-to-r from-rose-500 to-pink-500 bg-clip-text text-transparent mb-4 flex items-center gap-2">
        <Baby className="h-5 w-5 text-pink-400" />
        Customer Berisiko Tinggi Terbaru
      </h3>
      <Table>
        <Table.Header>
          <Table.Row className="bg-pink-50/50 rounded-xl">
            <Table.Head className="text-pink-600 font-semibold">Nama</Table.Head>
            <Table.Head className="text-pink-600 font-semibold">Kunjungan Terakhir</Table.Head>
            <Table.Head className="text-pink-600 font-semibold">Skor</Table.Head>
            <Table.Head className="text-pink-600 font-semibold">Status</Table.Head>
            <Table.Head className="text-right text-pink-600 font-semibold">Aksi</Table.Head>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {customers.map((customer) => (
            <Table.Row
              key={customer.customer_id}
              onClick={() => navigate(`/customers/${customer.customer_id}`)}
              className="cursor-pointer hover:bg-pink-50/30 transition-colors"
            >
              <Table.Cell className="font-medium text-stone-700">
                {customer.name}
              </Table.Cell>
              <Table.Cell className="text-stone-500">
                {formatRelativeTime(
                  customer.last_visit || customer.last_seen_at
                )}
              </Table.Cell>
              <Table.Cell className="font-bold text-rose-500">
                {customer.risk_score != null
                  ? `${(customer.risk_score * 100).toFixed(0)}%`
                  : "-"}
              </Table.Cell>
              <Table.Cell>
                <RiskLevelBadge score={customer.risk_score} />
              </Table.Cell>
              <Table.Cell className="text-right">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/customers/${customer.customer_id}`);
                  }}
                  className="text-pink-400 hover:text-pink-600 p-2 hover:bg-pink-100 rounded-full transition-colors"
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
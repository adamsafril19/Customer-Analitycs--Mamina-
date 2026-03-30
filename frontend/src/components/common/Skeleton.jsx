import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";

export function CardSkeleton() {
  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <Skeleton height={20} width="40%" className="mb-2" />
      <Skeleton height={36} width="60%" />
    </div>
  );
}

export function TableRowSkeleton({ columns = 5 }) {
  return (
    <tr>
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-6 py-4">
          <Skeleton height={20} />
        </td>
      ))}
    </tr>
  );
}

export function CustomerCardSkeleton() {
  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <div className="flex items-center gap-4 mb-4">
        <Skeleton circle height={48} width={48} />
        <div className="flex-1">
          <Skeleton height={24} width="60%" className="mb-2" />
          <Skeleton height={16} width="40%" />
        </div>
      </div>
      <Skeleton count={3} className="mb-1" />
    </div>
  );
}

export function ChartSkeleton({ height = 300 }) {
  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <Skeleton height={24} width="40%" className="mb-4" />
      <Skeleton height={height} />
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex items-center gap-4 mb-6">
          <Skeleton circle height={80} width={80} />
          <div className="flex-1">
            <Skeleton height={32} width="50%" className="mb-2" />
            <Skeleton height={20} width="30%" />
          </div>
        </div>
        <Skeleton height={100} />
      </div>
      <div className="bg-white p-6 rounded-lg shadow">
        <Skeleton height={24} width="40%" className="mb-4" />
        <Skeleton count={5} className="mb-2" />
      </div>
    </div>
  );
}

export default Skeleton;

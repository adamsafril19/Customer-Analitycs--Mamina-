import Modal from "../common/Modal";
import Badge from "../common/Badge";
import {
  formatDate,
  formatRelativeTime,
  ACTION_TYPE_LABELS,
  ACTION_STATUS_LABELS,
  PRIORITY_LABELS,
  getStatusColors,
  getPriorityColors,
} from "../../lib/utils";

function ActionHistoryModal({ isOpen, onClose, actions }) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Riwayat Action"
      description="Daftar tindakan yang sudah dibuat"
      size="lg"
    >
      <div className="max-h-[500px] overflow-y-auto">
        {actions.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            Belum ada action untuk customer ini
          </div>
        ) : (
          <div className="space-y-3">
            {actions.map((action) => (
              <div
                key={action.action_id}
                className="p-4 border rounded-lg hover:bg-gray-50"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className={`badge ${getStatusColors(action.status)}`}>
                      {ACTION_STATUS_LABELS[action.status] || action.status}
                    </span>
                    <Badge
                      color={
                        action.priority === "high"
                          ? "red"
                          : action.priority === "medium"
                          ? "yellow"
                          : "gray"
                      }
                    >
                      {PRIORITY_LABELS[action.priority] || action.priority}
                    </Badge>
                  </div>
                  <span className="text-xs text-gray-500">
                    {formatRelativeTime(action.created_at)}
                  </span>
                </div>

                <div className="mb-2">
                  <span className="font-medium text-gray-900">
                    {ACTION_TYPE_LABELS[action.action_type] ||
                      action.action_type}
                  </span>
                </div>

                {action.notes && (
                  <p className="text-sm text-gray-600 mb-2">{action.notes}</p>
                )}

                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span>Deadline: {formatDate(action.due_date)}</span>
                  {action.assigned_to && (
                    <span>Assigned: {action.assigned_to}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 pt-4 border-t">
        <button onClick={onClose} className="w-full btn-secondary">
          Tutup
        </button>
      </div>
    </Modal>
  );
}

export default ActionHistoryModal;

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Modal from "../common/Modal";
import Button from "../common/Button";
import { useCreateAction } from "../../hooks/useActions";
import { ACTION_TYPE_LABELS, PRIORITY_LABELS } from "../../lib/utils";

const actionSchema = z.object({
  action_type: z.string().min(1, "Tipe aksi wajib dipilih"),
  priority: z.string().min(1, "Prioritas wajib dipilih"),
  due_date: z.string().min(1, "Tanggal deadline wajib diisi"),
  notes: z.string().optional(),
});

function CreateActionModal({ isOpen, onClose, customerId, customerName }) {
  const createAction = useCreateAction();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(actionSchema),
    defaultValues: {
      action_type: "call",
      priority: "high",
      due_date: new Date().toISOString().split("T")[0],
      notes: "",
    },
  });

  const onSubmit = async (data) => {
    try {
      await createAction.mutateAsync({
        customer_id: customerId,
        ...data,
      });
      reset();
      onClose();
    } catch (error) {
      // Error handled by mutation
    }
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Buat Action Baru"
      description={`Tindak lanjut untuk ${customerName}`}
      size="md"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {/* Action Type */}
        <div>
          <label htmlFor="action_type" className="label">
            Tipe Aksi
          </label>
          <select
            id="action_type"
            {...register("action_type")}
            className={`input ${errors.action_type ? "border-red-500" : ""}`}
          >
            {Object.entries(ACTION_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          {errors.action_type && (
            <p className="mt-1 text-sm text-red-600">
              {errors.action_type.message}
            </p>
          )}
        </div>

        {/* Priority */}
        <div>
          <label htmlFor="priority" className="label">
            Prioritas
          </label>
          <select
            id="priority"
            {...register("priority")}
            className={`input ${errors.priority ? "border-red-500" : ""}`}
          >
            {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          {errors.priority && (
            <p className="mt-1 text-sm text-red-600">
              {errors.priority.message}
            </p>
          )}
        </div>

        {/* Due Date */}
        <div>
          <label htmlFor="due_date" className="label">
            Deadline
          </label>
          <input
            type="date"
            id="due_date"
            {...register("due_date")}
            className={`input ${errors.due_date ? "border-red-500" : ""}`}
          />
          {errors.due_date && (
            <p className="mt-1 text-sm text-red-600">
              {errors.due_date.message}
            </p>
          )}
        </div>

        {/* Notes */}
        <div>
          <label htmlFor="notes" className="label">
            Catatan (opsional)
          </label>
          <textarea
            id="notes"
            {...register("notes")}
            rows={3}
            className="input"
            placeholder="Tambahkan catatan..."
          />
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4">
          <Button
            type="button"
            variant="secondary"
            onClick={handleClose}
            className="flex-1"
          >
            Batal
          </Button>
          <Button
            type="submit"
            loading={isSubmitting || createAction.isPending}
            className="flex-1"
          >
            Simpan
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default CreateActionModal;

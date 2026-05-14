import { useState, useCallback } from "react";
import { Upload, FileSpreadsheet, Users, CreditCard, MessageSquare, CheckCircle2, XCircle, AlertTriangle, ArrowRight, Loader2 } from "lucide-react";
import toast from "react-hot-toast";
import { usePreviewCSV, useImportCSV } from "../hooks/useImport";

// ─── Tab definitions ─────────────────────────────────────────
const TABS = [
  { key: "customers", label: "Customers", icon: Users, color: "primary", description: "Import data pelanggan (customer_master.csv)", requiredCols: ["customer_id", "customer_name", "phone_number", "join_date"] },
  { key: "transactions", label: "Transactions", icon: CreditCard, color: "emerald", description: "Import data transaksi (transactions.csv)", requiredCols: ["transaction_id", "customer_id", "transaction_date", "transaction_amount", "service_type", "transaction_status"] },
  { key: "messages", label: "WhatsApp", icon: MessageSquare, color: "purple", description: "Import pesan WhatsApp (whatsapp_messages.csv)", requiredCols: ["message_id", "customer_id", "message_timestamp", "sender_type", "message_text"] },
];

// ─── Main Page ───────────────────────────────────────────────
export default function DataImport() {
  const [activeTab, setActiveTab] = useState("customers");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-primary-900">Import Data</h1>
        <p className="mt-1 text-sm text-stone-500">
          Upload file CSV untuk memasukkan data ke sistem. Ikuti urutan: Customers → Transactions → Messages.
        </p>
      </div>

      {/* Dependency indicator */}
      <div className="flex items-center gap-2 text-xs text-primary-400 bg-primary-50 rounded-lg px-4 py-2">
        <span className="font-medium text-stone-600">Urutan import:</span>
        <span className="text-primary-600 font-semibold">Customers</span>
        <ArrowRight className="w-3 h-3" />
        <span className="text-emerald-600 font-semibold">Transactions</span>
        <ArrowRight className="w-3 h-3" />
        <span className="text-purple-600 font-semibold">WhatsApp Messages</span>
      </div>

      {/* Tabs */}
      <div className="border-b border-primary-200">
        <nav className="-mb-px flex space-x-8">
          {TABS.map((tab) => (
            <button key={tab.key} onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? `border-${tab.color}-500 text-${tab.color}-600`
                  : "border-transparent text-stone-500 hover:text-primary-800 hover:border-primary-300"
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Active tab content */}
      {TABS.map((tab) => activeTab === tab.key && <ImportSection key={tab.key} tab={tab} />)}
    </div>
  );
}

// ─── Import Section (one per tab) ────────────────────────────
function ImportSection({ tab }) {
  const [file, setFile] = useState(null);
  const [step, setStep] = useState("upload"); // upload → preview → done
  const [previewData, setPreviewData] = useState(null);
  const [importResult, setImportResult] = useState(null);

  const previewMutation = usePreviewCSV(tab.key);
  const importMutation = useImportCSV(tab.key);

  const handleFileSelect = useCallback((e) => {
    const selected = e.target.files?.[0];
    if (selected) {
      if (!selected.name.toLowerCase().endsWith(".csv")) {
        toast.error("Hanya file .csv yang diterima");
        return;
      }
      setFile(selected);
      setStep("upload");
      setPreviewData(null);
      setImportResult(null);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) {
      if (!dropped.name.toLowerCase().endsWith(".csv")) {
        toast.error("Hanya file .csv yang diterima");
        return;
      }
      setFile(dropped);
      setStep("upload");
      setPreviewData(null);
      setImportResult(null);
    }
  }, []);

  const handlePreview = useCallback(() => {
    if (!file) return;
    previewMutation.mutate(file, {
      onSuccess: (data) => { setPreviewData(data); setStep("preview"); },
      onError: (err) => toast.error(err.response?.data?.error || "Preview gagal"),
    });
  }, [file, previewMutation]);

  const handleImport = useCallback(() => {
    if (!file) return;
    importMutation.mutate(file, {
      onSuccess: (data) => {
        setImportResult(data);
        setStep("done");
        if (data.success) toast.success(`${data.imported} baris berhasil diimport!`);
        else toast.error("Import gagal — lihat detail error");
      },
      onError: (err) => toast.error(err.response?.data?.error || "Import gagal"),
    });
  }, [file, importMutation]);

  const handleReset = () => {
    setFile(null); setStep("upload"); setPreviewData(null); setImportResult(null);
  };

  return (
    <div className="space-y-6">
      {/* Info card */}
      <div className="bg-white rounded-xl border border-primary-200 p-5">
        <div className="flex items-start gap-3">
          <div className={`p-2 rounded-lg bg-${tab.color}-50`}>
            <FileSpreadsheet className={`w-5 h-5 text-${tab.color}-600`} />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-primary-900">{tab.description}</h3>
            <p className="mt-1 text-xs text-stone-500">
              Kolom wajib: <code className="bg-primary-100 px-1 rounded">{tab.requiredCols.join(", ")}</code>
            </p>
          </div>
        </div>
      </div>

      {/* Step 1: Upload */}
      <div className="bg-white rounded-xl border border-primary-200 p-6">
        <div
          onDrop={handleDrop} onDragOver={(e) => e.preventDefault()}
          className="border-2 border-dashed border-primary-300 rounded-xl p-8 text-center hover:border-primary-400 transition-colors cursor-pointer"
          onClick={() => document.getElementById(`file-${tab.key}`).click()}
        >
          <Upload className="w-10 h-10 text-primary-400 mx-auto mb-3" />
          <p className="text-sm text-stone-600">
            {file ? (
              <span className="font-medium text-primary-900">{file.name} <span className="text-primary-400">({(file.size / 1024).toFixed(1)} KB)</span></span>
            ) : (
              <>Drag & drop file CSV di sini, atau <span className="text-primary-600 font-medium">pilih file</span></>
            )}
          </p>
          <input id={`file-${tab.key}`} type="file" accept=".csv" className="hidden" onChange={handleFileSelect} />
        </div>

        {file && step === "upload" && (
          <div className="mt-4 flex gap-3">
            <button onClick={handlePreview} disabled={previewMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-primary-500 to-primary-600 text-white text-sm font-medium rounded-lg hover:shadow-lg disabled:opacity-50 transition-all">
              {previewMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4" />}
              Preview & Validate
            </button>
            <button onClick={handleReset} className="px-4 py-2 text-sm text-stone-600 hover:text-primary-800">Reset</button>
          </div>
        )}
      </div>

      {/* Step 2: Preview + Validation */}
      {step === "preview" && previewData && (
        <PreviewPanel data={previewData} tab={tab} onImport={handleImport} onReset={handleReset} isImporting={importMutation.isPending} />
      )}

      {/* Step 3: Result */}
      {step === "done" && importResult && (
        <ResultPanel result={importResult} onReset={handleReset} />
      )}
    </div>
  );
}

// ─── Preview Panel ───────────────────────────────────────────
function PreviewPanel({ data, tab, onImport, onReset, isImporting }) {
  const { preview, validation } = data;
  const hasErrors = validation?.errors?.length > 0;
  const canImport = validation?.valid_rows > 0;

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Total Baris" value={preview?.total_rows ?? 0} color="primary" />
        <StatCard label="Valid" value={validation?.valid_rows ?? 0} color="green" />
        <StatCard label="Invalid" value={validation?.invalid_rows ?? 0} color={validation?.invalid_rows > 0 ? "red" : "gray"} />
        <StatCard label="Duplikat" value={preview?.summary?.duplicates ?? 0} color={preview?.summary?.duplicates > 0 ? "yellow" : "gray"} />
      </div>

      {/* FK errors */}
      {preview?.summary?.invalid_fk > 0 && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span><strong>{preview.summary.invalid_fk}</strong> baris memiliki customer_id yang tidak ditemukan di database. Import customers terlebih dahulu.</span>
        </div>
      )}

      {/* Preview table */}
      {preview?.rows?.length > 0 && (
        <div className="bg-white rounded-xl border border-primary-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-primary-100 bg-primary-50">
            <h4 className="text-sm font-medium text-primary-800">Preview ({Math.min(preview.rows.length, 20)} dari {preview.total_rows} baris)</h4>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead className="bg-primary-50">
                <tr>
                  {preview.columns.map((col) => (
                    <th key={col} className="px-3 py-2 text-left font-medium text-stone-500 uppercase tracking-wider whitespace-nowrap">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {preview.rows.map((row, i) => {
                  const rowErrors = (validation?.errors || []).filter((e) => e.row === i + 2);
                  const errorCols = new Set(rowErrors.map((e) => e.column));
                  return (
                    <tr key={i} className={rowErrors.length > 0 ? "bg-red-50" : "hover:bg-primary-50"}>
                      {preview.columns.map((col) => (
                        <td key={col} className={`px-3 py-2 whitespace-nowrap max-w-[200px] truncate ${errorCols.has(col) ? "text-red-600 font-medium" : "text-primary-800"}`}>
                          {String(row[col] ?? "")}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Validation errors */}
      {hasErrors && (
        <div className="bg-white rounded-xl border border-red-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-red-100 bg-red-50">
            <h4 className="text-sm font-medium text-red-700 flex items-center gap-2">
              <XCircle className="w-4 h-4" /> Validation Errors ({validation.errors.length})
            </h4>
          </div>
          <div className="max-h-60 overflow-y-auto">
            <table className="min-w-full text-xs">
              <thead className="bg-primary-50 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-stone-500">Baris</th>
                  <th className="px-3 py-2 text-left font-medium text-stone-500">Kolom</th>
                  <th className="px-3 py-2 text-left font-medium text-stone-500">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {validation.errors.slice(0, 50).map((err, i) => (
                  <tr key={i} className="hover:bg-red-50">
                    <td className="px-3 py-1.5 text-stone-600">{err.row}</td>
                    <td className="px-3 py-1.5 font-mono text-primary-800">{err.column}</td>
                    <td className="px-3 py-1.5 text-red-600">{err.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-3">
        <button onClick={onImport} disabled={!canImport || isImporting}
          className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
          {isImporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
          Import {validation?.valid_rows ?? 0} Baris Valid
        </button>
        <button onClick={onReset} className="px-4 py-2 text-sm text-stone-600 hover:text-primary-800">Batal</button>
      </div>
    </div>
  );
}

// ─── Result Panel ────────────────────────────────────────────
function ResultPanel({ result, onReset }) {
  return (
    <div className={`rounded-xl border p-6 ${result.success ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`}>
      <div className="flex items-start gap-3">
        {result.success ? <CheckCircle2 className="w-6 h-6 text-emerald-600 mt-0.5" /> : <XCircle className="w-6 h-6 text-red-600 mt-0.5" />}
        <div className="flex-1">
          <h3 className={`font-semibold ${result.success ? "text-emerald-800" : "text-red-800"}`}>
            {result.success ? "Import Berhasil!" : "Import Gagal"}
          </h3>
          <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
            <div><span className="text-stone-500">Diimport:</span> <strong className="text-emerald-700">{result.imported}</strong></div>
            <div><span className="text-stone-500">Dilewati:</span> <strong className="text-yellow-700">{result.skipped}</strong></div>
            <div><span className="text-stone-500">Duplikat:</span> <strong className="text-stone-600">{result.duplicates_ignored}</strong></div>
          </div>
          {result.errors?.length > 0 && (
            <div className="mt-3 max-h-40 overflow-y-auto text-xs bg-white/50 rounded-lg p-3 space-y-1">
              {result.errors.slice(0, 20).map((err, i) => (
                <div key={i} className="text-red-600">Baris {err.row}: [{err.column}] {err.message}</div>
              ))}
            </div>
          )}
          <button onClick={onReset} className="mt-4 px-4 py-2 bg-white border border-primary-300 text-sm text-primary-800 rounded-lg hover:bg-primary-50 transition-colors">
            Import File Lain
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Stat Card ───────────────────────────────────────────────
function StatCard({ label, value, color }) {
  const colors = {
    primary: "bg-primary-50 text-primary-700", green: "bg-emerald-50 text-emerald-700",
    red: "bg-rose-50 text-rose-700", yellow: "bg-amber-50 text-amber-700", gray: "bg-primary-50 text-stone-500",
  };
  return (
    <div className={`rounded-lg px-4 py-3 ${colors[color] || colors.gray}`}>
      <p className="text-xs font-medium opacity-75">{label}</p>
      <p className="text-xl font-bold">{value.toLocaleString("id-ID")}</p>
    </div>
  );
}

import { useState } from "react";
import {
  Settings as SettingsIcon,
  Save,
  User,
  Sliders,
  Clock,
  Shield,
  Lock,
  Mail,
  CheckCircle2,
  AlertTriangle,
  Info,
  SlidersHorizontal,
  Sparkles,
  BarChart3,
  BadgeCheck,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import Button from "../components/common/Button";
import Card from "../components/common/Card";
import toast from "react-hot-toast";

function Settings() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState("threshold");
  const [isSaving, setIsSaving] = useState(false);

  // Threshold settings
  const [thresholds, setThresholds] = useState({
    low: 0.4,
    high: 0.7,
  });

  // Time window settings
  const [timeWindow, setTimeWindow] = useState("90");

  // Profile settings
  const [profile, setProfile] = useState({
    name: user?.name || "Admin Mamina",
    email: user?.email || "admin@mamina.id",
    role: user?.role || "Administrator",
  });

  // Password fields
  const [passwords, setPasswords] = useState({
    current: "",
    newPass: "",
    confirm: "",
  });

  const handleSaveThresholds = async () => {
    setIsSaving(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 800));
      toast.success("Konfigurasi threshold & time window berhasil disimpan!");
    } catch (error) {
      toast.error("Gagal menyimpan pengaturan threshold.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveProfile = async () => {
    setIsSaving(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 800));
      toast.success("Profil dan kredensial pengguna berhasil diperbarui!");
      setPasswords({ current: "", newPass: "", confirm: "" });
    } catch (error) {
      toast.error("Gagal memperbarui profil pengguna.");
    } finally {
      setIsSaving(false);
    }
  };

  const tabs = [
    {
      id: "threshold",
      label: "Ambisi & Threshold Risiko",
      description: "Batas skor & time window",
      icon: SlidersHorizontal,
    },
    {
      id: "profile",
      label: "Profil & Keamanan Akun",
      description: "Data diri & kredensial",
      icon: User,
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      {/* Header Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-primary-900 via-primary-800 to-rose-900 p-6 sm:p-8 text-white shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 -mr-16 -mt-16 w-64 h-64 rounded-full bg-white/5 blur-2xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-xs font-semibold text-pink-200 backdrop-blur-md mb-3 border border-white/10">
              <Sparkles className="h-3.5 w-3.5" />
              <span>System Configuration</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight flex items-center gap-3">
              Pengaturan Sistem
            </h1>
            <p className="mt-1 text-sm text-primary-100/80 max-w-2xl">
              Kelola batas ambang skor risiko disengagement (*Risk Threshold*), kurun waktu pengamatan transaksi (*Time Window*), dan kredensial akun pengguna.
            </p>
          </div>
          <div className="flex items-center gap-3 bg-white/10 backdrop-blur-md px-4 py-3 rounded-xl border border-white/10">
            <div className="h-10 w-10 rounded-full bg-pink-500/30 flex items-center justify-center font-bold text-lg text-white border border-pink-300/30">
              {profile.name.charAt(0)}
            </div>
            <div>
              <p className="text-sm font-semibold leading-tight">{profile.name}</p>
              <p className="text-xs text-primary-200 capitalize">{profile.role}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Navigation Sidebar */}
        <div className="lg:col-span-1 space-y-4">
          <Card className="p-2 border-stone-200/80 shadow-sm">
            <nav className="space-y-1">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`w-full flex items-center gap-3.5 px-4 py-3.5 rounded-xl text-left transition-all duration-200 ${
                      isActive
                        ? "bg-primary-50 text-primary-900 font-semibold shadow-sm border border-primary-200/60"
                        : "text-stone-600 hover:bg-stone-50 hover:text-stone-900 font-medium"
                    }`}
                  >
                    <div
                      className={`p-2 rounded-lg ${
                        isActive
                          ? "bg-primary-600 text-white"
                          : "bg-stone-100 text-stone-500 group-hover:bg-stone-200"
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <span className="block text-sm leading-tight">{tab.label}</span>
                      <span className="block text-[11px] text-stone-400 font-normal mt-0.5">
                        {tab.description}
                      </span>
                    </div>
                  </button>
                );
              })}
            </nav>
          </Card>

          {/* Quick Info Box */}
          <div className="rounded-xl border border-blue-100 bg-blue-50/70 p-4 text-xs text-blue-900 space-y-2">
            <div className="flex items-center gap-2 font-semibold text-blue-800">
              <Info className="h-4 w-4 text-blue-600 shrink-0" />
              <span>Info Parameter Engine</span>
            </div>
            <p className="text-stone-600 leading-relaxed">
              Model prediksi saat ini menggunakan parameter aktif **FeatureConfig v3.0.0** (Threshold High = 0.70, Jendela Observasi = 90 Hari).
            </p>
          </div>
        </div>

        {/* Tab Content Panels */}
        <div className="lg:col-span-3">
          {/* TAB 1: THRESHOLD & TIME WINDOW */}
          {activeTab === "threshold" && (
            <div className="space-y-6">
              <Card className="border-stone-200/80 shadow-md overflow-hidden">
                <Card.Header className="bg-stone-50/50 border-b border-stone-100 pb-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 bg-primary-100 text-primary-700 rounded-xl">
                        <Sliders className="h-5 w-5" />
                      </div>
                      <div>
                        <Card.Title className="text-lg font-bold text-stone-900">
                          Batas Ambang Risiko (Disengagement Risk Threshold)
                        </Card.Title>
                        <Card.Description className="text-xs text-stone-500">
                          Atur toleransi rentang skor untuk mengkategorikan tingkat risiko pelanggan.
                        </Card.Description>
                      </div>
                    </div>
                    <span className="px-2.5 py-1 text-xs font-semibold bg-purple-100 text-purple-700 rounded-full border border-purple-200 flex items-center gap-1.5">
                      <Sparkles className="h-3 w-3" />
                      <span>Prototype Interface</span>
                    </span>
                  </div>
                </Card.Header>

                <Card.Content className="p-6 space-y-8">
                  {/* Alert Prototype Note */}
                  <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50/80 p-4 text-xs text-amber-900">
                    <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold block text-amber-950 text-sm">
                        Simulasi Konfigurasi Antarmuka
                      </span>
                      <p className="mt-0.5 text-amber-800 leading-relaxed">
                        Pengaturan slider di bawah ini disajikan sebagai sarana demonstrasi antarmuka dinamis bagi manajemen untuk menguji tingkat sensitivitas kategorisasi *Low*, *Medium*, dan *High Risk*.
                      </p>
                    </div>
                  </div>

                  {/* Visual Risk Band Progress */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs font-semibold text-stone-700">
                      <span>Spektrum Pengelompokan Risiko Pelanggan</span>
                      <span className="font-mono text-primary-700">100% (1.00)</span>
                    </div>
                    <div className="h-4 w-full rounded-full bg-stone-100 flex overflow-hidden p-0.5 border border-stone-200 shadow-inner">
                      <div
                        style={{ width: `${thresholds.low * 100}%` }}
                        className="bg-emerald-500 text-[10px] text-white flex items-center justify-center font-bold transition-all duration-300 rounded-l-full"
                      >
                        Low
                      </div>
                      <div
                        style={{
                          width: `${(thresholds.high - thresholds.low) * 100}%`,
                        }}
                        className="bg-amber-400 text-[10px] text-amber-950 flex items-center justify-center font-bold transition-all duration-300"
                      >
                        Medium
                      </div>
                      <div
                        style={{ width: `${(1 - thresholds.high) * 100}%` }}
                        className="bg-rose-500 text-[10px] text-white flex items-center justify-center font-bold transition-all duration-300 rounded-r-full"
                      >
                        High
                      </div>
                    </div>
                    <div className="flex justify-between text-[11px] text-stone-400 pt-1 font-mono">
                      <span>0.00</span>
                      <span>{(thresholds.low).toFixed(2)}</span>
                      <span>{(thresholds.high).toFixed(2)}</span>
                      <span>1.00</span>
                    </div>
                  </div>

                  {/* Sliders Controls Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                    {/* Low Threshold Slider */}
                    <div className="rounded-xl border border-stone-200 p-5 bg-white space-y-3 hover:border-emerald-300 transition-colors shadow-sm">
                      <div className="flex items-center justify-between">
                        <label className="text-sm font-bold text-stone-800 flex items-center gap-2">
                          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                          Batas Risiko Rendah (Low Risk)
                        </label>
                        <span className="font-mono font-bold text-sm bg-emerald-50 text-emerald-700 px-3 py-1 rounded-lg border border-emerald-200">
                          &lt; {(thresholds.low * 100).toFixed(0)}%
                        </span>
                      </div>
                      <input
                        type="range"
                        min="10"
                        max="50"
                        step="5"
                        value={thresholds.low * 100}
                        onChange={(e) =>
                          setThresholds({
                            ...thresholds,
                            low: e.target.value / 100,
                          })
                        }
                        className="w-full accent-emerald-600 h-2 bg-stone-100 rounded-lg cursor-pointer"
                      />
                      <p className="text-xs text-stone-500 leading-relaxed">
                        Pelanggan dengan skor risiko di bawah nilai ini dianggap aktif & memiliki kestabilan kunjungan yang aman.
                      </p>
                    </div>

                    {/* High Threshold Slider */}
                    <div className="rounded-xl border border-stone-200 p-5 bg-white space-y-3 hover:border-rose-300 transition-colors shadow-sm">
                      <div className="flex items-center justify-between">
                        <label className="text-sm font-bold text-stone-800 flex items-center gap-2">
                          <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                          Batas Risiko Tinggi (High Risk)
                        </label>
                        <span className="font-mono font-bold text-sm bg-rose-50 text-rose-700 px-3 py-1 rounded-lg border border-rose-200">
                          &gt; {(thresholds.high * 100).toFixed(0)}%
                        </span>
                      </div>
                      <input
                        type="range"
                        min="55"
                        max="90"
                        step="5"
                        value={thresholds.high * 100}
                        onChange={(e) =>
                          setThresholds({
                            ...thresholds,
                            high: e.target.value / 100,
                          })
                        }
                        className="w-full accent-rose-600 h-2 bg-stone-100 rounded-lg cursor-pointer"
                      />
                      <p className="text-xs text-stone-500 leading-relaxed">
                        Pelanggan dengan skor risiko di atas nilai ini membutuhkan intervensi retensi atau kontak langsung secepatnya.
                      </p>
                    </div>
                  </div>

                  {/* Calculated Medium Risk Box */}
                  <div className="rounded-xl bg-amber-50/70 border border-amber-200/80 p-4 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-amber-100 text-amber-800">
                        <BarChart3 className="h-5 w-5" />
                      </div>
                      <div>
                        <span className="text-xs font-semibold uppercase text-amber-700">
                          Kategori Otomatis
                        </span>
                        <p className="text-sm font-bold text-amber-950">
                          Risiko Sedang (Medium Risk): {(thresholds.low * 100).toFixed(0)}% – {(thresholds.high * 100).toFixed(0)}%
                        </p>
                      </div>
                    </div>
                    <span className="text-xs font-medium text-amber-800 bg-amber-100/80 px-3 py-1 rounded-full border border-amber-200 hidden sm:inline-block">
                      Dihitung Otomatis
                    </span>
                  </div>

                  {/* Analysis Time Window Selection */}
                  <div className="pt-6 border-t border-stone-200 space-y-4">
                    <div>
                      <h4 className="text-sm font-bold text-stone-900 flex items-center gap-2">
                        <Clock className="h-4 w-4 text-primary-700" />
                        Jendela Observasi Analisis (Analysis Time Window)
                      </h4>
                      <p className="text-xs text-stone-500 mt-0.5">
                        Pilih jangka waktu historis transaksi yang dijadikan acuan perhitungan fitur perilaku pelanggan.
                      </p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      {[
                        {
                          value: "30",
                          title: "30 Hari Terakhir",
                          desc: "Monitoring tren jangka sangat pendek.",
                        },
                        {
                          value: "90",
                          title: "90 Hari (Standar v3)",
                          desc: "Rekomendasi resmi model ML v3.0.0.",
                          recommended: true,
                        },
                        {
                          value: "180",
                          title: "180 Hari (6 Bulan)",
                          desc: "Evaluasi siklus berkala jangka panjang.",
                        },
                      ].map((option) => {
                        const isSelected = timeWindow === option.value;
                        return (
                          <div
                            key={option.value}
                            onClick={() => setTimeWindow(option.value)}
                            className={`cursor-pointer rounded-xl border p-4 transition-all duration-200 relative ${
                              isSelected
                                ? "border-primary-600 bg-primary-50/60 ring-2 ring-primary-500/20 shadow-sm"
                                : "border-stone-200 bg-white hover:border-stone-300 hover:bg-stone-50/50"
                            }`}
                          >
                            {option.recommended && (
                              <span className="absolute -top-2.5 right-3 px-2 py-0.5 text-[10px] font-extrabold bg-primary-600 text-white rounded-full uppercase tracking-wider shadow-sm">
                                Recommended
                              </span>
                            )}
                            <div className="flex items-start justify-between">
                              <div>
                                <p className={`text-sm font-bold ${isSelected ? "text-primary-900" : "text-stone-800"}`}>
                                  {option.title}
                                </p>
                                <p className="text-xs text-stone-500 mt-1 leading-normal">
                                  {option.desc}
                                </p>
                              </div>
                              <div
                                className={`h-4 w-4 rounded-full border flex items-center justify-center mt-0.5 ${
                                  isSelected
                                    ? "border-primary-600 bg-primary-600 text-white"
                                    : "border-stone-300 bg-white"
                                }`}
                              >
                                {isSelected && <CheckCircle2 className="h-3 w-3" />}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </Card.Content>

                <Card.Footer className="bg-stone-50/50 border-t border-stone-100 p-4 flex justify-end">
                  <Button
                    onClick={handleSaveThresholds}
                    loading={isSaving}
                    icon={<Save className="h-4 w-4" />}
                    className="shadow-md"
                  >
                    Simpan Konfigurasi Threshold
                  </Button>
                </Card.Footer>
              </Card>
            </div>
          )}

          {/* TAB 2: USER PROFILE & SECURITY */}
          {activeTab === "profile" && (
            <div className="space-y-6">
              <Card className="border-stone-200/80 shadow-md overflow-hidden">
                <Card.Header className="bg-stone-50/50 border-b border-stone-100 pb-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-primary-100 text-primary-700 rounded-xl">
                      <User className="h-5 w-5" />
                    </div>
                    <div>
                      <Card.Title className="text-lg font-bold text-stone-900">
                        Profil & Informasi Pengguna
                      </Card.Title>
                      <Card.Description className="text-xs text-stone-500">
                        Kelola data identitas dan kredensial akun pengguna sistem.
                      </Card.Description>
                    </div>
                  </div>
                </Card.Header>

                <Card.Content className="p-6 space-y-6">
                  {/* Account Summary Banner */}
                  <div className="flex items-center gap-4 p-4 rounded-xl bg-stone-50 border border-stone-200/80">
                    <div className="h-14 w-14 rounded-full bg-gradient-to-br from-primary-600 to-rose-700 text-white font-bold text-xl flex items-center justify-center shadow-md">
                      {profile.name.charAt(0)}
                    </div>
                    <div>
                      <h3 className="font-bold text-stone-900 text-base flex items-center gap-2">
                        {profile.name}
                        <BadgeCheck className="h-4 w-4 text-pink-600" />
                      </h3>
                      <p className="text-xs text-stone-500">{profile.email}</p>
                      <span className="inline-block mt-1 px-2.5 py-0.5 text-[11px] font-semibold bg-primary-100 text-primary-800 rounded-full border border-primary-200">
                        Hak Akses: {profile.role}
                      </span>
                    </div>
                  </div>

                  {/* Form Inputs */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div>
                      <label htmlFor="name" className="label font-semibold text-stone-700 flex items-center gap-1.5 mb-1.5">
                        <User className="h-3.5 w-3.5 text-stone-500" />
                        Nama Lengkap
                      </label>
                      <input
                        type="text"
                        id="name"
                        value={profile.name}
                        onChange={(e) =>
                          setProfile({ ...profile, name: e.target.value })
                        }
                        className="input rounded-xl border-stone-300 focus:ring-primary-500 focus:border-primary-500"
                        placeholder="Nama Pengguna"
                      />
                    </div>

                    <div>
                      <label htmlFor="email" className="label font-semibold text-stone-700 flex items-center gap-1.5 mb-1.5">
                        <Mail className="h-3.5 w-3.5 text-stone-500" />
                        Alamat Email
                      </label>
                      <input
                        type="email"
                        id="email"
                        value={profile.email}
                        onChange={(e) =>
                          setProfile({ ...profile, email: e.target.value })
                        }
                        className="input rounded-xl border-stone-300 focus:ring-primary-500 focus:border-primary-500"
                        placeholder="email@mamina.id"
                      />
                    </div>
                  </div>

                  {/* Security Section */}
                  <div className="pt-6 border-t border-stone-200 space-y-4">
                    <div className="flex items-center gap-2">
                      <Lock className="h-4 w-4 text-primary-700" />
                      <h4 className="text-sm font-bold text-stone-900">
                        Pembaruan Password & Keamanan
                      </h4>
                    </div>

                    <div className="space-y-4 max-w-xl">
                      <div>
                        <label htmlFor="currentPassword" className="label text-xs font-semibold text-stone-600 mb-1">
                          Password Saat Ini
                        </label>
                        <input
                          type="password"
                          id="currentPassword"
                          value={passwords.current}
                          onChange={(e) => setPasswords({ ...passwords, current: e.target.value })}
                          className="input rounded-xl border-stone-300 text-sm"
                          placeholder="••••••••"
                        />
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label htmlFor="newPassword" className="label text-xs font-semibold text-stone-600 mb-1">
                            Password Baru
                          </label>
                          <input
                            type="password"
                            id="newPassword"
                            value={passwords.newPass}
                            onChange={(e) => setPasswords({ ...passwords, newPass: e.target.value })}
                            className="input rounded-xl border-stone-300 text-sm"
                            placeholder="••••••••"
                          />
                        </div>
                        <div>
                          <label htmlFor="confirmPassword" className="label text-xs font-semibold text-stone-600 mb-1">
                            Konfirmasi Password Baru
                          </label>
                          <input
                            type="password"
                            id="confirmPassword"
                            value={passwords.confirm}
                            onChange={(e) => setPasswords({ ...passwords, confirm: e.target.value })}
                            className="input rounded-xl border-stone-300 text-sm"
                            placeholder="••••••••"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </Card.Content>

                <Card.Footer className="bg-stone-50/50 border-t border-stone-100 p-4 flex justify-end">
                  <Button
                    onClick={handleSaveProfile}
                    loading={isSaving}
                    icon={<Save className="h-4 w-4" />}
                    className="shadow-md"
                  >
                    Simpan Perubahan Profil
                  </Button>
                </Card.Footer>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Settings;

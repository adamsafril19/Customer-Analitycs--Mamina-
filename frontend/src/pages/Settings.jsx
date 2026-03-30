import { useState } from "react";
import {
  Settings as SettingsIcon,
  Save,
  User,
  Bell,
  Sliders,
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
    name: user?.name || "",
    email: user?.email || "",
  });

  const handleSaveThresholds = async () => {
    setIsSaving(true);
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 1000));
      toast.success("Pengaturan threshold berhasil disimpan");
    } catch (error) {
      toast.error("Gagal menyimpan pengaturan");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveTimeWindow = async () => {
    setIsSaving(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      toast.success("Pengaturan time window berhasil disimpan");
    } catch (error) {
      toast.error("Gagal menyimpan pengaturan");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveProfile = async () => {
    setIsSaving(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      toast.success("Profil berhasil diperbarui");
    } catch (error) {
      toast.error("Gagal memperbarui profil");
    } finally {
      setIsSaving(false);
    }
  };

  const tabs = [
    { id: "threshold", label: "Churn Threshold", icon: Sliders },
    { id: "profile", label: "Profil", icon: User },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <SettingsIcon className="h-6 w-6 text-gray-600" />
          Settings
        </h1>
        <p className="text-gray-500 mt-1">Konfigurasi aplikasi</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar */}
        <div className="lg:col-span-1">
          <nav className="bg-white rounded-lg shadow-md p-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-md text-left transition ${
                  activeTab === tab.id
                    ? "bg-blue-50 text-blue-600"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                <tab.icon className="h-5 w-5" />
                <span className="font-medium">{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="lg:col-span-3">
          {activeTab === "threshold" && (
            <Card>
              <Card.Header>
                <Card.Title>Churn Risk Threshold</Card.Title>
                <Card.Description>
                  Atur batas skor untuk kategori risiko churn
                </Card.Description>
              </Card.Header>
              <Card.Content>
                <div className="space-y-6">
                  {/* Low Threshold */}
                  <div>
                    <label className="label">Batas Risiko Rendah (Low)</label>
                    <div className="flex items-center gap-4">
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={thresholds.low * 100}
                        onChange={(e) =>
                          setThresholds({
                            ...thresholds,
                            low: e.target.value / 100,
                          })
                        }
                        className="flex-1"
                      />
                      <span className="w-20 text-center font-mono bg-gray-100 px-3 py-2 rounded">
                        &lt; {(thresholds.low * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      Customer dengan skor di bawah ini dianggap risiko rendah
                    </p>
                  </div>

                  {/* Medium (automatic) */}
                  <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                    <p className="text-sm font-medium text-yellow-800">
                      Risiko Sedang (Medium):{" "}
                      {(thresholds.low * 100).toFixed(0)}% -{" "}
                      {(thresholds.high * 100).toFixed(0)}%
                    </p>
                    <p className="text-xs text-yellow-600 mt-1">
                      Dihitung otomatis berdasarkan threshold low dan high
                    </p>
                  </div>

                  {/* High Threshold */}
                  <div>
                    <label className="label">Batas Risiko Tinggi (High)</label>
                    <div className="flex items-center gap-4">
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={thresholds.high * 100}
                        onChange={(e) =>
                          setThresholds({
                            ...thresholds,
                            high: e.target.value / 100,
                          })
                        }
                        className="flex-1"
                      />
                      <span className="w-20 text-center font-mono bg-gray-100 px-3 py-2 rounded">
                        &gt; {(thresholds.high * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      Customer dengan skor di atas ini dianggap risiko tinggi
                    </p>
                  </div>

                  {/* Time Window */}
                  <div className="pt-6 border-t">
                    <label className="label">Analysis Time Window</label>
                    <div className="flex flex-col gap-2">
                      {[
                        { value: "30", label: "30 hari terakhir" },
                        { value: "90", label: "90 hari terakhir" },
                        { value: "180", label: "6 bulan terakhir" },
                      ].map((option) => (
                        <label
                          key={option.value}
                          className="flex items-center gap-2 cursor-pointer"
                        >
                          <input
                            type="radio"
                            name="timeWindow"
                            value={option.value}
                            checked={timeWindow === option.value}
                            onChange={(e) => setTimeWindow(e.target.value)}
                            className="w-4 h-4 text-blue-600"
                          />
                          <span className="text-gray-700">{option.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
              </Card.Content>
              <Card.Footer>
                <Button
                  onClick={handleSaveThresholds}
                  loading={isSaving}
                  icon={<Save className="h-4 w-4" />}
                >
                  Simpan Pengaturan
                </Button>
              </Card.Footer>
            </Card>
          )}

          {activeTab === "profile" && (
            <Card>
              <Card.Header>
                <Card.Title>Profil Pengguna</Card.Title>
                <Card.Description>
                  Kelola informasi profil Anda
                </Card.Description>
              </Card.Header>
              <Card.Content>
                <div className="space-y-4">
                  <div>
                    <label htmlFor="name" className="label">
                      Nama
                    </label>
                    <input
                      type="text"
                      id="name"
                      value={profile.name}
                      onChange={(e) =>
                        setProfile({ ...profile, name: e.target.value })
                      }
                      className="input"
                    />
                  </div>

                  <div>
                    <label htmlFor="email" className="label">
                      Email
                    </label>
                    <input
                      type="email"
                      id="email"
                      value={profile.email}
                      onChange={(e) =>
                        setProfile({ ...profile, email: e.target.value })
                      }
                      className="input"
                    />
                  </div>

                  <div className="pt-4 border-t">
                    <h4 className="font-medium text-gray-900 mb-3">
                      Ubah Password
                    </h4>
                    <div className="space-y-3">
                      <div>
                        <label htmlFor="currentPassword" className="label">
                          Password Saat Ini
                        </label>
                        <input
                          type="password"
                          id="currentPassword"
                          className="input"
                          placeholder="••••••••"
                        />
                      </div>
                      <div>
                        <label htmlFor="newPassword" className="label">
                          Password Baru
                        </label>
                        <input
                          type="password"
                          id="newPassword"
                          className="input"
                          placeholder="••••••••"
                        />
                      </div>
                      <div>
                        <label htmlFor="confirmPassword" className="label">
                          Konfirmasi Password
                        </label>
                        <input
                          type="password"
                          id="confirmPassword"
                          className="input"
                          placeholder="••••••••"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </Card.Content>
              <Card.Footer>
                <Button
                  onClick={handleSaveProfile}
                  loading={isSaving}
                  icon={<Save className="h-4 w-4" />}
                >
                  Simpan Profil
                </Button>
              </Card.Footer>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

export default Settings;

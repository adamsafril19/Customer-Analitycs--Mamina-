# Customer Churn Prediction Dashboard

Frontend aplikasi prediksi churn untuk **Mamina Baby Spa & Pijat Laktasi**.

![React](https://img.shields.io/badge/React-18.2-blue)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-3.3-blue)
![Vite](https://img.shields.io/badge/Vite-5.0-purple)

## 🎯 Deskripsi

Dashboard ini dirancang untuk membantu owner/admin Mamina Baby Spa dalam:

- ✅ **Melihat** siapa yang berisiko churn dengan cepat
- ✅ **Memahami** kenapa mereka berisiko (explainability)
- ✅ **Menentukan** aksi tindak lanjut yang tepat
- ✅ **Melacak** hasil intervensi sederhana

## ✨ Fitur Utama

### 1. Dashboard Overview

- KPI Cards: Total Customers, At Risk, Avg Score, New Predictions
- Churn Risk Trend Chart (30 hari terakhir)
- Top Churn Drivers Chart
- Recent High-Risk Customers Table

### 2. Customer Management

- Daftar semua customer dengan filter dan pencarian
- View mode: Table dan Grid
- Color-coded risk level (Merah/Kuning/Hijau)

### 3. Customer Detail Page (⭐ Halaman Terpenting)

- Customer Summary dengan Churn Score
- **Why At Risk?** - Explainability dalam bahasa Indonesia
- Interaction Timeline (Transaksi & WhatsApp)
- Suggested Actions

### 4. Churn Risk Management

- Focus view untuk high-risk customers
- Filter berdasarkan risk level
- Quick action creation

### 5. Action Tracking

- Daftar semua follow-up actions
- Status tracking: Pending → In Progress → Completed
- Priority management

### 6. Settings

- Churn threshold configuration
- Time window settings
- User profile management

## 🛠️ Tech Stack

- **Framework**: React 18 + Vite
- **Styling**: Tailwind CSS 3
- **State Management**: React Query (TanStack Query)
- **Routing**: React Router v6
- **Forms**: React Hook Form + Zod
- **Charts**: Recharts
- **UI Components**: Headless UI
- **Icons**: Lucide React
- **HTTP Client**: Axios
- **Date Handling**: date-fns
- **Notifications**: React Hot Toast

## 📦 Instalasi

### Prerequisites

- Node.js 18+
- npm atau yarn

### Setup

```bash
# Clone repository (jika belum)
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Edit .env sesuai kebutuhan
# VITE_API_URL=http://localhost:5000/api

# Jalankan development server
npm run dev
```

Aplikasi akan berjalan di `http://localhost:3000`

### Build Production

```bash
npm run build
npm run preview
```

## 📁 Struktur Folder

```
frontend/
├── public/                 # Static assets
├── src/
│   ├── components/        # Reusable components
│   │   ├── common/        # Badge, Button, Card, Modal, Table, etc.
│   │   ├── customer/      # ChurnScoreBadge, RiskLevelBadge, etc.
│   │   ├── dashboard/     # KPICard, Charts
│   │   ├── actions/       # CreateActionModal, ActionHistoryModal
│   │   └── layout/        # Layout, Navbar, Sidebar
│   ├── contexts/          # React Context (Auth)
│   ├── hooks/             # Custom hooks (useCustomers, useActions, etc.)
│   ├── lib/               # API client, utilities
│   ├── pages/             # Page components
│   │   ├── Login.jsx
│   │   ├── Dashboard.jsx
│   │   ├── CustomerList.jsx
│   │   ├── CustomerDetail.jsx
│   │   ├── ChurnRisk.jsx
│   │   ├── Actions.jsx
│   │   └── Settings.jsx
│   ├── test/              # Unit tests
│   ├── App.jsx            # Main app component
│   ├── main.jsx           # Entry point
│   └── index.css          # Global styles
├── .env.example           # Environment variables template
├── package.json
├── tailwind.config.js
├── vite.config.js
└── README.md
```

## 🔌 API Integration

Frontend ini terintegrasi dengan backend Flask. Berikut endpoint yang digunakan:

### Authentication

- `POST /api/auth/login` - Login
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Get current user

### Dashboard

- `GET /api/dashboard/stats` - KPI statistics
- `GET /api/dashboard/trend` - Churn trend data
- `GET /api/dashboard/top-drivers` - Top churn drivers

### Customers

- `GET /api/customers` - List customers
- `GET /api/customers/:id/360` - Customer 360 view
- `GET /api/customers/:id/timeline` - Customer timeline

### Predictions

- `GET /api/predictions` - List predictions
- `POST /api/predictions` - Create prediction

### Actions

- `GET /api/actions` - List actions
- `POST /api/actions` - Create action
- `PATCH /api/actions/:id` - Update action

## 🧪 Testing

```bash
# Run tests
npm run test

# Run tests with UI
npm run test:ui
```

### Test Coverage

- `ChurnScoreBadge` - Score display & color coding
- `RiskLevelBadge` - Risk level labels & styling
- `Badge` - Color variants
- `Button` - Variants, loading, disabled states
- `utils` - Utility functions

## 🎨 Color Coding

| Risk Level | Score Range | Color     |
| ---------- | ----------- | --------- |
| Low        | < 0.4       | 🟢 Green  |
| Medium     | 0.4 - 0.7   | 🟡 Yellow |
| High       | > 0.7       | 🔴 Red    |

## 📱 Responsive Design

Aplikasi mendukung:

- **Desktop** (>1024px): Full sidebar, multi-column layouts
- **Tablet** (768px - 1024px): Collapsible sidebar
- **Mobile** (<768px): Hamburger menu, card views

## 🎓 Academic Value (untuk Sidang Skripsi)

### 1. Explainability Focus

Sistem tidak hanya prediksi, tapi menjelaskan **KENAPA** customer berisiko churn menggunakan SHAP values yang diterjemahkan ke bahasa bisnis.

### 2. Actionable Insights

Frontend dirancang untuk **decision support**, bukan data exploration. Setiap insight mengarah ke aksi konkret.

### 3. Closed-Loop System

Ada tracking follow-up yang membuktikan sistem tidak berhenti di prediksi, tapi mendorong **intervensi aktual**.

### 4. User-Centric Design

Interface dirancang untuk owner baby spa (bukan data scientist), dengan bahasa dan visualisasi yang mudah dipahami.

### 5. Multimodal Integration

Frontend menggabungkan insights dari data transaksional DAN tekstual WhatsApp dalam satu tampilan terpadu.

## 📝 License

MIT License - © 2025 Mamina Baby Spa

## 👤 Author

Dibuat untuk keperluan Skripsi - Customer Churn Prediction System

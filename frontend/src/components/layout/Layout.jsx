// src/components/layout/Layout.jsx
import { Outlet } from "react-router-dom";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import { Cloud, Sparkles, Heart, Flower2, Baby } from "lucide-react";
import { useState } from "react";

function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#FFF5F9] via-[#FFF0F5] to-[#F0F9FF] relative overflow-hidden">
      {/* Decorative floating elements global */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute top-20 left-10 animate-float">
          <Cloud className="h-24 w-24 text-pink-100/50" />
        </div>
        <div className="absolute bottom-40 right-20 animate-float-delayed">
          <Cloud className="h-32 w-32 text-blue-100/40" />
        </div>
        <div className="absolute top-1/3 right-1/4 animate-spin-slow">
          <Sparkles className="h-8 w-8 text-yellow-200/60" />
        </div>
        <div className="absolute bottom-1/4 left-1/4 animate-pulse">
          <Heart className="h-6 w-6 text-pink-200/60" />
        </div>
        <div className="absolute top-2/3 left-10 animate-bounce-slow">
          <Flower2 className="h-7 w-7 text-purple-100/50" />
        </div>
        <div className="absolute bottom-10 left-1/3 animate-float">
          <Baby className="h-8 w-8 text-pink-200/30 rotate-12" />
        </div>
      </div>

      <div className="relative z-10 flex flex-col min-h-screen">
        <Navbar onMenuClick={() => setSidebarOpen(true)} />
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        <div className="lg:pl-64 flex-1">
          <main className="py-6 px-4 sm:px-6 lg:px-8">
            <Outlet />
          </main>
        </div>
      </div>

      {/* Custom animations - bisa dipindah ke global CSS */}
      <style jsx>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px) translateX(0px); }
          50% { transform: translateY(-20px) translateX(10px); }
        }
        @keyframes float-delayed {
          0%, 100% { transform: translateY(0px) translateX(0px); }
          50% { transform: translateY(20px) translateX(-10px); }
        }
        @keyframes spin-slow {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes bounce-slow {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-15px); }
        }
        @keyframes ping-slow {
          0% { transform: scale(1); opacity: 1; }
          75%, 100% { transform: scale(1.5); opacity: 0; }
        }
        .animate-float { animation: float 6s ease-in-out infinite; }
        .animate-float-delayed { animation: float-delayed 7s ease-in-out infinite; }
        .animate-spin-slow { animation: spin-slow 12s linear infinite; }
        .animate-bounce-slow { animation: bounce-slow 4s ease-in-out infinite; }
        .animate-ping-slow { animation: ping-slow 2s cubic-bezier(0, 0, 0.2, 1) infinite; }
      `}</style>
    </div>
  );
}

export default Layout;
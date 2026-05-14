// src/components/layout/Navbar.jsx
import { Menu, Bell, User, LogOut, Settings, Baby, Sparkles, Heart } from "lucide-react";
import { Fragment } from "react";
import { Menu as HeadlessMenu, Transition } from "@headlessui/react";
import { useAuth } from "../../contexts/AuthContext";
import { cn } from "../../lib/utils";

function Navbar({ onMenuClick }) {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-40 bg-white/60 backdrop-blur-md shadow-sm border-b border-pink-100 lg:pl-64">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 text-pink-500 hover:bg-pink-100 rounded-xl transition-colors"
          >
            <Menu className="h-6 w-6" />
          </button>
          <div className="lg:hidden flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-pink-300 to-purple-300 rounded-xl flex items-center justify-center shadow-sm">
              <Baby className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-pink-500 to-purple-500 bg-clip-text text-transparent">
              Mamina
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Notifications */}
          <button className="relative p-2 text-pink-400 hover:text-pink-600 hover:bg-pink-50 rounded-full transition-colors">
            <Bell className="h-5 w-5" />
            <span className="absolute top-1.5 right-1.5 w-2.5 h-2.5 bg-rose-400 border-2 border-white rounded-full animate-pulse"></span>
          </button>

          {/* User dropdown */}
          <HeadlessMenu as="div" className="relative">
            <HeadlessMenu.Button className="flex items-center gap-2 p-1.5 hover:bg-pink-50 rounded-2xl transition-all border border-transparent hover:border-pink-200">
              <div className="w-8 h-8 bg-gradient-to-br from-pink-400 via-pink-500 to-purple-400 rounded-xl flex items-center justify-center shadow-sm shadow-pink-300/50">
                <User className="h-4 w-4 text-white" />
              </div>
              <span className="hidden md:block text-sm font-semibold text-stone-700 pr-2">
                {user?.name || "User"}
              </span>
              <Sparkles className="hidden md:block h-3 w-3 text-yellow-400" />
            </HeadlessMenu.Button>

            <Transition
              as={Fragment}
              enter="transition ease-out duration-100"
              enterFrom="transform opacity-0 scale-95"
              enterTo="transform opacity-100 scale-100"
              leave="transition ease-in duration-75"
              leaveFrom="transform opacity-100 scale-100"
              leaveTo="transform opacity-0 scale-95"
            >
              <HeadlessMenu.Items className="absolute right-0 mt-2 w-48 origin-top-right rounded-2xl bg-white/90 backdrop-blur-sm py-1 shadow-lg ring-1 ring-pink-100 focus:outline-none">
                <HeadlessMenu.Item>
                  {({ active }) => (
                    <a
                      href="/settings"
                      className={cn(
                        "flex items-center gap-2 px-4 py-2 text-sm text-stone-700",
                        active && "bg-pink-50 text-pink-600"
                      )}
                    >
                      <Settings className="h-4 w-4" />
                      Settings
                    </a>
                  )}
                </HeadlessMenu.Item>
                <HeadlessMenu.Item>
                  {({ active }) => (
                    <button
                      onClick={logout}
                      className={cn(
                        "flex items-center gap-2 px-4 py-2 text-sm text-stone-700 w-full",
                        active && "bg-pink-50 text-pink-600"
                      )}
                    >
                      <LogOut className="h-4 w-4" />
                      Logout
                    </button>
                  )}
                </HeadlessMenu.Item>
              </HeadlessMenu.Items>
            </Transition>
          </HeadlessMenu>
        </div>
      </div>
    </header>
  );
}

export default Navbar;
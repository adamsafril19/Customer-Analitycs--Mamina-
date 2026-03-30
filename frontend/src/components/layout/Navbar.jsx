import { Menu, Bell, User, LogOut, Settings } from "lucide-react";
import { Fragment } from "react";
import { Menu as HeadlessMenu, Transition } from "@headlessui/react";
import { useAuth } from "../../contexts/AuthContext";
import { cn } from "../../lib/utils";

function Navbar({ onMenuClick }) {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-40 bg-white shadow-sm lg:pl-64">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 text-gray-600 hover:bg-gray-100 rounded-md"
          >
            <Menu className="h-6 w-6" />
          </button>
          <div className="lg:hidden flex items-center gap-2">
            <span className="text-xl font-bold text-blue-600">Mamina</span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Notifications */}
          <button className="p-2 text-gray-600 hover:bg-gray-100 rounded-full relative">
            <Bell className="h-5 w-5" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
          </button>

          {/* User dropdown */}
          <HeadlessMenu as="div" className="relative">
            <HeadlessMenu.Button className="flex items-center gap-2 p-2 hover:bg-gray-100 rounded-lg">
              <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                <User className="h-5 w-5 text-blue-600" />
              </div>
              <span className="hidden md:block text-sm font-medium text-gray-700">
                {user?.name || "User"}
              </span>
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
              <HeadlessMenu.Items className="absolute right-0 mt-2 w-48 origin-top-right rounded-md bg-white py-1 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                <HeadlessMenu.Item>
                  {({ active }) => (
                    <a
                      href="/settings"
                      className={cn(
                        "flex items-center gap-2 px-4 py-2 text-sm text-gray-700",
                        active && "bg-gray-100"
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
                        "flex items-center gap-2 px-4 py-2 text-sm text-gray-700 w-full",
                        active && "bg-gray-100"
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

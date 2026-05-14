// src/components/layout/Sidebar.jsx
import { Fragment } from "react";
import { NavLink } from "react-router-dom";
import { Dialog, Transition } from "@headlessui/react";
import {
  X,
  LayoutDashboard,
  Users,
  AlertTriangle,
  ClipboardList,
  Settings,
  Upload,
  Baby,
  Sparkles,
  Heart,
  Flower2,
} from "lucide-react";
import { cn } from "../../lib/utils";

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Customers", href: "/customers", icon: Users },
  { name: "Risk Analysis", href: "/risk", icon: AlertTriangle },
  { name: "Actions", href: "/actions", icon: ClipboardList },
  { name: "Import Data", href: "/import", icon: Upload },
  { name: "Settings", href: "/settings", icon: Settings },
];

function Sidebar({ open, onClose }) {
  return (
    <>
      {/* Mobile sidebar */}
      <Transition.Root show={open} as={Fragment}>
        <Dialog as="div" className="relative z-50 lg:hidden" onClose={onClose}>
          <Transition.Child
            as={Fragment}
            enter="transition-opacity ease-linear duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="transition-opacity ease-linear duration-300"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-pink-900/40 backdrop-blur-sm" />
          </Transition.Child>

          <div className="fixed inset-0 flex">
            <Transition.Child
              as={Fragment}
              enter="transition ease-in-out duration-300 transform"
              enterFrom="-translate-x-full"
              enterTo="translate-x-0"
              leave="transition ease-in-out duration-300 transform"
              leaveFrom="translate-x-0"
              leaveTo="-translate-x-full"
            >
              <Dialog.Panel className="relative mr-16 flex w-full max-w-xs flex-1">
                <Transition.Child
                  as={Fragment}
                  enter="ease-in-out duration-300"
                  enterFrom="opacity-0"
                  enterTo="opacity-100"
                  leave="ease-in-out duration-300"
                  leaveFrom="opacity-100"
                  leaveTo="opacity-0"
                >
                  <div className="absolute left-full top-0 flex w-16 justify-center pt-5">
                    <button
                      type="button"
                      className="-m-2.5 p-2.5 text-white hover:text-pink-200"
                      onClick={onClose}
                    >
                      <X className="h-6 w-6" />
                    </button>
                  </div>
                </Transition.Child>

                <SidebarContent />
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </Dialog>
      </Transition.Root>

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:z-50 lg:flex lg:w-64 lg:flex-col">
        <SidebarContent />
      </div>
    </>
  );
}

function SidebarContent() {
  return (
    <div className="flex grow flex-col gap-y-5 overflow-y-auto bg-white/70 backdrop-blur-md border-r border-pink-100 px-6 pb-4 shadow-[4px_0_24px_rgba(236,72,153,0.08)]">
      <div className="flex h-16 shrink-0 items-center">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="absolute -top-1 -right-1 animate-ping-slow">
              <Sparkles className="h-3 w-3 text-yellow-400" />
            </div>
            <div className="w-10 h-10 bg-gradient-to-br from-pink-300 via-pink-400 to-purple-300 rounded-2xl flex items-center justify-center shadow-md shadow-pink-300/40">
              <Baby className="h-6 w-6 text-white" strokeWidth={1.5} />
            </div>
          </div>
          <div>
            <span className="text-xl font-bold bg-gradient-to-r from-pink-500 to-purple-500 bg-clip-text text-transparent">
              Mamina
            </span>
            <p className="text-[11px] text-stone-500 font-medium tracking-wide flex items-center gap-1">
              Risk Scoring <Heart className="h-2.5 w-2.5 text-pink-400 fill-pink-200" />
            </p>
          </div>
        </div>
      </div>

      <nav className="flex flex-1 flex-col">
        <ul className="flex flex-1 flex-col gap-y-1">
          {navigation.map((item) => (
            <li key={item.name}>
              <NavLink
                to={item.href}
                className={({ isActive }) =>
                  cn(
                    "group flex items-center gap-x-3 p-3 text-sm font-semibold transition-all duration-300 rounded-2xl",
                    isActive
                      ? "bg-gradient-to-r from-pink-50 to-purple-50 text-pink-700 shadow-sm border border-pink-100/50"
                      : "text-stone-500 hover:text-pink-600 hover:bg-pink-50/50 rounded-xl"
                  )
                }
              >
                <item.icon className="h-5 w-5 shrink-0" />
                {item.name}
                {item.name === "Dashboard" && (
                  <Sparkles className="ml-auto h-3 w-3 text-yellow-400" />
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="mt-auto">
        <div className="rounded-2xl bg-gradient-to-br from-pink-50/80 to-purple-50/80 backdrop-blur-sm p-4 border border-pink-100 text-center shadow-inner">
          <div className="flex justify-center gap-1 mb-1">
            <Flower2 className="h-3 w-3 text-pink-300" />
            <Heart className="h-3 w-3 text-pink-400" />
            <Baby className="h-3 w-3 text-purple-300" />
          </div>
          <p className="text-xs font-semibold text-stone-600 flex justify-center items-center gap-1">
            <Sparkles className="h-3 w-3 text-yellow-400" />
            Version 1.0.0
          </p>
          <p className="text-[10px] text-stone-400 mt-1">© 2026 Mamina Baby Spa</p>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
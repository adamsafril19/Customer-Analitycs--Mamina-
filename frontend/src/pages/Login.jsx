import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Eye,
  EyeOff,
  Loader2,
  Baby,
  Heart,
  Sparkles,
  Cloud,
  Flower2
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

const loginSchema = z.object({
  username: z.string().min(1, "Username wajib diisi"),
  password: z.string().min(1, "Password wajib diisi"),
  remember: z.boolean().optional(),
});

function Login() {
  const { isAuthenticated, login, loading: authLoading } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: "",
      password: "",
      remember: false,
    },
  });

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-pink-50 via-purple-50 to-blue-50">
        <Loader2 className="h-8 w-8 animate-spin text-pink-400" />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const onSubmit = async (data) => {
    setIsLoading(true);
    try {
      await login({
        username: data.username,
        password: data.password,
      });
    } catch (error) {
      // Error handled in AuthContext
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-gradient-to-br from-[#FFF5F9] via-[#FFF0F5] to-[#F0F9FF] px-4 overflow-hidden">
      {/* Decorative floating elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-10 left-10 animate-float">
          <Cloud className="h-16 w-16 text-pink-100 opacity-60" />
        </div>
        <div className="absolute bottom-20 right-10 animate-float-delayed">
          <Cloud className="h-20 w-20 text-blue-100 opacity-50" />
        </div>
        <div className="absolute top-1/4 right-20 animate-spin-slow">
          <Sparkles className="h-6 w-6 text-yellow-200 opacity-70" />
        </div>
        <div className="absolute bottom-1/3 left-5 animate-pulse">
          <Heart className="h-5 w-5 text-pink-200 opacity-60" />
        </div>
        <div className="absolute top-1/2 left-1/4 animate-bounce-slow">
          <Flower2 className="h-8 w-8 text-purple-100 opacity-50" />
        </div>
        {/* Baby footprints pattern */}
        <div className="absolute bottom-5 left-5 opacity-20">
          <Baby className="h-8 w-8 text-pink-300" />
        </div>
        <div className="absolute top-5 right-5 opacity-20 transform scale-x-[-1]">
          <Baby className="h-8 w-8 text-blue-300" />
        </div>
      </div>

      <div className="w-full max-w-md relative z-10">
        <div className="bg-white/80 backdrop-blur-sm rounded-3xl shadow-2xl shadow-pink-200/50 border border-pink-100 p-8 transition-all duration-300 hover:shadow-pink-300/30">
          {/* Logo & Header */}
          <div className="text-center mb-8">
            <div className="relative inline-block">
              <div className="absolute -top-2 -right-2 animate-ping-slow">
                <Sparkles className="h-5 w-5 text-yellow-400" />
              </div>
              <div className="w-20 h-20 bg-gradient-to-br from-pink-300 via-pink-400 to-purple-300 shadow-lg shadow-pink-300/40 rounded-3xl mx-auto mb-4 flex items-center justify-center transform transition-transform hover:scale-105 duration-300">
                <Baby className="h-10 w-10 text-white" strokeWidth={1.5} />
              </div>
            </div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-pink-500 via-purple-500 to-blue-500 bg-clip-text text-transparent">
              Mamina Baby Spa
            </h1>
            <p className="text-stone-500 mt-2 font-medium flex items-center justify-center gap-1">
              <Heart className="h-4 w-4 text-pink-400 fill-pink-200" />
              Behavioral Risk Scoring Dashboard
              <Heart className="h-4 w-4 text-pink-400 fill-pink-200" />
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div>
              <label htmlFor="username" className="flex items-center gap-2 text-sm font-semibold text-stone-700 mb-1.5">
                <Baby className="h-4 w-4 text-pink-400" />
                Username / Email
              </label>
              <input
                id="username"
                type="text"
                {...register("username")}
                className={`w-full px-5 py-3 rounded-2xl border-2 bg-white/90 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-pink-300 focus:border-transparent placeholder:text-stone-400 ${errors.username
                    ? "border-red-300 focus:ring-red-300 bg-red-50/50"
                    : "border-pink-100 hover:border-pink-200"
                  }`}
                placeholder="Masukkan username atau email"
                disabled={isLoading}
              />
              {errors.username && (
                <p className="mt-1.5 text-sm text-red-500 flex items-center gap-1">
                  <Heart className="h-3 w-3 fill-red-200" />
                  {errors.username.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="flex items-center gap-2 text-sm font-semibold text-stone-700 mb-1.5">
                <Sparkles className="h-4 w-4 text-purple-400" />
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  {...register("password")}
                  className={`w-full px-5 py-3 rounded-2xl border-2 bg-white/90 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-pink-300 focus:border-transparent placeholder:text-stone-400 pr-12 ${errors.password
                      ? "border-red-300 focus:ring-red-300 bg-red-50/50"
                      : "border-pink-100 hover:border-pink-200"
                    }`}
                  placeholder="Masukkan password"
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-pink-300 hover:text-pink-500 transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="h-5 w-5" />
                  ) : (
                    <Eye className="h-5 w-5" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1.5 text-sm text-red-500 flex items-center gap-1">
                  <Heart className="h-3 w-3 fill-red-200" />
                  {errors.password.message}
                </p>
              )}
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer group">
                <input
                  type="checkbox"
                  {...register("remember")}
                  className="w-4 h-4 rounded border-pink-300 text-pink-500 focus:ring-pink-300 focus:ring-offset-0 accent-pink-500"
                />
                <span className="text-sm text-stone-600 font-medium group-hover:text-pink-500 transition-colors">
                  Ingat saya
                </span>
              </label>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-gradient-to-r from-pink-400 via-pink-500 to-purple-400 text-white font-bold py-3.5 rounded-2xl transition-all duration-300 transform hover:scale-[1.02] hover:shadow-lg hover:shadow-pink-400/30 active:scale-95 disabled:opacity-70 disabled:hover:scale-100 flex items-center justify-center gap-2 text-base"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <span>Memproses...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-5 w-5" />
                  <span>Masuk ke Dashboard</span>
                </>
              )}
            </button>
          </form>

          {/* Demo credentials hint */}
          <div className="mt-8 p-4 bg-gradient-to-r from-pink-50 via-purple-50 to-blue-50 rounded-2xl border border-pink-100 shadow-inner">
            <p className="text-sm text-stone-600 text-center flex items-center justify-center gap-2 flex-wrap">
              <Baby className="h-4 w-4 text-pink-400" />
              <strong className="text-pink-600">Demo:</strong>
              <span className="font-mono bg-white/70 px-2 py-0.5 rounded-full text-xs">admin</span>
              <span className="text-stone-400">/</span>
              <span className="font-mono bg-white/70 px-2 py-0.5 rounded-full text-xs">mamina2024</span>
              <Sparkles className="h-3 w-3 text-purple-400" />
            </p>
          </div>
        </div>

        <p className="text-center text-sm font-medium text-stone-400 mt-6 flex items-center justify-center gap-1">
          <Heart className="h-3 w-3 text-pink-300" />
          © 2026 Mamina Baby Spa. All rights reserved.
          <Heart className="h-3 w-3 text-pink-300" />
        </p>
      </div>


    </div>
  );
}

export default Login;
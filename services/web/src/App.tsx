import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, errorMessage, hasToken, setToken, setUnauthorizedHandler } from "./api/client";
import { Layout } from "./components/Layout";
import { ErrorState, Spinner } from "./components/States";
import { detectedLang, setLang, tr } from "./lib/i18n";
import { useMe } from "./lib/queries";
import { webApp } from "./lib/telegram";
import { AddMeal } from "./pages/AddMeal";
import { Analytics } from "./pages/Analytics";
import { Catalog } from "./pages/Catalog";
import { ExerciseInfo } from "./pages/ExerciseInfo";
import { ExerciseProgress } from "./pages/ExerciseProgress";
import { LanguagePicker } from "./pages/LanguagePicker";
import { Login } from "./pages/Login";
import { Paywall } from "./pages/Paywall";
import { Profile } from "./pages/Profile";
import { TemplateEdit } from "./pages/TemplateEdit";
import { Today } from "./pages/Today";
import { Weight } from "./pages/Weight";
import { WorkoutSession } from "./pages/WorkoutSession";
import { Workouts } from "./pages/Workouts";
import { AdminLayout } from "./pages/admin/AdminLayout";
import { Broadcasts } from "./pages/admin/Broadcasts";
import { Dashboard } from "./pages/admin/Dashboard";
import { Log } from "./pages/admin/Log";
import { Promos } from "./pages/admin/Promos";
import { Referrals } from "./pages/admin/Referrals";
import { Settings } from "./pages/admin/Settings";
import { UserDetail } from "./pages/admin/UserDetail";
import { Users } from "./pages/admin/Users";

type AuthState = "checking" | "anonymous" | "authenticated" | "failed";

export function App() {
  const queryClient = useQueryClient();
  const [auth, setAuth] = useState<AuthState>(() =>
    webApp ? "checking" : hasToken() ? "authenticated" : "anonymous",
  );

  const signIn = useCallback((token: string) => {
    setToken(token);
    setAuth("authenticated");
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      queryClient.clear();
      setAuth(webApp ? "failed" : "anonymous");
    });
    if (!webApp) return;
    webApp.ready();
    webApp.expand();
    api.authWebApp(webApp.initData).then(
      ({ token }) => signIn(token),
      () => setAuth("failed"),
    );
  }, [queryClient, signIn]);

  switch (auth) {
    case "checking":
      return <Spinner />;
    case "failed":
      return (
        <ErrorState
          message={tr(
            "Не удалось войти. Закрой и снова открой приложение.",
            "Couldn't sign in. Close the app and open it again.",
          )}
        />
      );
    case "anonymous":
      return <Login onToken={signIn} />;
    case "authenticated":
      return <AuthenticatedApp />;
  }
}

function AuthenticatedApp() {
  const { data: me, isPending, error, refetch } = useMe();
  const inAdmin = useLocation().pathname.startsWith("/admin");
  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  const lang = inAdmin ? "ru" : (me.language ?? detectedLang);
  setLang(lang);
  if (!me.language && !inAdmin) return <LanguagePicker />;

  if (!me.profile_complete && !me.is_admin) {
    return (
      <Routes key={lang}>
        <Route path="*" element={<Profile me={me} onboarding />} />
      </Routes>
    );
  }

  const paid = (page: ReactNode) => {
    if (!me.profile_complete) return <Profile me={me} onboarding />;
    return me.has_access ? page : <Paywall />;
  };
  return (
    <Routes key={lang}>
      <Route element={<Layout />}>
        <Route index element={paid(<Today />)} />
        <Route path="add" element={paid(<AddMeal />)} />
        <Route path="workouts" element={paid(<Workouts />)} />
        <Route path="workouts/:id" element={paid(<WorkoutSession />)} />
        <Route path="catalog" element={paid(<Catalog />)} />
        <Route path="catalog/:id" element={paid(<ExerciseInfo />)} />
        <Route path="exercises/:id" element={paid(<ExerciseProgress />)} />
        <Route path="analytics" element={paid(<Analytics />)} />
        <Route path="templates/new" element={paid(<TemplateEdit />)} />
        <Route path="templates/:id" element={paid(<TemplateEdit />)} />
        <Route path="weight" element={paid(<Weight />)} />
        <Route path="profile" element={<Profile me={me} />} />
        {me.is_admin && (
          <Route path="admin" element={<AdminLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="users" element={<Users />} />
            <Route path="users/:id" element={<UserDetail />} />
            <Route path="broadcasts" element={<Broadcasts />} />
            <Route path="promos" element={<Promos />} />
            <Route path="referrals" element={<Referrals />} />
            <Route path="log" element={<Log />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        )}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

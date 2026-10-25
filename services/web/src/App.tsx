import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { api, errorMessage, hasToken, setToken, setUnauthorizedHandler } from "./api/client";
import { Layout } from "./components/Layout";
import { ErrorState, Spinner } from "./components/States";
import { useMe } from "./lib/queries";
import { webApp } from "./lib/telegram";
import { AddMeal } from "./pages/AddMeal";
import { ExerciseProgress } from "./pages/ExerciseProgress";
import { Login } from "./pages/Login";
import { Paywall } from "./pages/Paywall";
import { Profile } from "./pages/Profile";
import { Today } from "./pages/Today";
import { Weight } from "./pages/Weight";
import { Workouts } from "./pages/Workouts";

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
      return <ErrorState message="Не удалось войти. Закрой и снова открой приложение." />;
    case "anonymous":
      return <Login onToken={signIn} />;
    case "authenticated":
      return <AuthenticatedApp />;
  }
}

function AuthenticatedApp() {
  const { data: me, isPending, error, refetch } = useMe();
  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  if (!me.profile_complete) {
    return (
      <Routes>
        <Route path="*" element={<Profile me={me} onboarding />} />
      </Routes>
    );
  }

  const paid = (page: ReactNode) => (me.has_access ? page : <Paywall />);
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={paid(<Today />)} />
        <Route path="add" element={paid(<AddMeal />)} />
        <Route path="workouts" element={paid(<Workouts />)} />
        <Route path="workouts/:name" element={paid(<ExerciseProgress />)} />
        <Route path="weight" element={paid(<Weight />)} />
        <Route path="profile" element={<Profile me={me} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

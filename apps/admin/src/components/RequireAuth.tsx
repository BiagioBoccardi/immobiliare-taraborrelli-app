import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useSession } from "../auth/SessionContext";
import { Loading } from "./ui";

export function RequireAuth({
  children,
  adminOnly = false,
}: {
  children: ReactNode;
  adminOnly?: boolean;
}) {
  const { status, user } = useSession();
  const location = useLocation();

  if (status === "loading") return <Loading />;
  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (adminOnly && user?.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

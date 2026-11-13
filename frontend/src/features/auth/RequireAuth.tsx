import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { Loading } from "../../components/Temporary";
import type { Role } from "../../types/api";
import { useSession } from "./session";

/** Shows children only to logged-in users (optionally of certain roles). */
export function RequireAuth({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { data: session, isPending } = useSession();
  const location = useLocation();

  if (isPending) return <Loading />;
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (roles && !roles.includes(session.user.role)) return <Navigate to="/home" replace />;
  return <>{children}</>;
}

/** Logged-in users skip the landing, login and signup pages. */
export function GuestOnly({ children }: { children: ReactNode }) {
  const { data: session, isPending } = useSession();
  if (isPending) return <Loading />;
  if (session) return <Navigate to="/home" replace />;
  return <>{children}</>;
}

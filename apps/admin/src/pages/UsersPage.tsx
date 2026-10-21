import type { Role, User } from "@taraborrelli/api-client";
import { useState, type FormEvent } from "react";

import { useCreateStaff, useUpdateUser, useUsers } from "../api/queries";
import { useSession } from "../auth/SessionContext";
import { PasswordInput } from "../components/PasswordInput";
import {
  Empty,
  ErrorAlert,
  Field,
  Loading,
  PageHeader,
  Pagination,
  SuccessAlert,
} from "../components/ui";
import { t, tEnum } from "../i18n";
import { formatDateTime } from "../utils/format";

const ROLES: Role[] = ["staff", "admin", "user"];
const PAGE_SIZE = 20;

function CreateStaffForm() {
  const create = useCreateStaff();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"staff" | "admin">("staff");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      { full_name: fullName.trim(), email: email.trim(), password, role },
      {
        onSuccess: () => {
          setFullName("");
          setEmail("");
          setPassword("");
          setRole("staff");
        },
      },
    );
  };

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>{t("users.new")}</h2>
      {create.isSuccess ? <SuccessAlert>{t("users.created")}</SuccessAlert> : null}
      <ErrorAlert error={create.error} />
      <Field label={t("users.name")} htmlFor="new-name">
        <input
          id="new-name"
          type="text"
          required
          minLength={2}
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />
      </Field>
      <Field label={t("users.email")} htmlFor="new-email">
        <input
          id="new-email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </Field>
      <Field label={t("users.password")} htmlFor="new-password">
        <PasswordInput
          id="new-password"
          autoComplete="new-password"
          required
          minLength={10}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </Field>
      <Field label={t("users.role")} htmlFor="new-role">
        <select
          id="new-role"
          value={role}
          onChange={(e) => setRole(e.target.value as "staff" | "admin")}
        >
          <option value="staff">{tEnum("role", "staff")}</option>
          <option value="admin">{tEnum("role", "admin")}</option>
        </select>
      </Field>
      <button
        type="submit"
        className="button button-primary"
        disabled={create.isPending || fullName.trim().length < 2 || !email || password.length < 10}
      >
        {t("users.create")}
      </button>
    </form>
  );
}

function UserRow({ user, isSelf }: { user: User; isSelf: boolean }) {
  const update = useUpdateUser();
  return (
    <tr>
      <td>{user.full_name}</td>
      <td>{user.email}</td>
      <td>
        <select
          aria-label={t("users.role")}
          value={user.role}
          disabled={isSelf || update.isPending}
          onChange={(e) =>
            update.mutate({ id: user.id, changes: { role: e.target.value as Role } })
          }
        >
          {ROLES.map((role) => (
            <option key={role} value={role}>
              {tEnum("role", role)}
            </option>
          ))}
        </select>
        <ErrorAlert error={update.error} />
      </td>
      <td>
        <input
          type="checkbox"
          aria-label={t("users.active")}
          checked={user.is_active}
          disabled={isSelf || update.isPending}
          onChange={(e) => update.mutate({ id: user.id, changes: { is_active: e.target.checked } })}
        />
      </td>
      <td>{formatDateTime(user.last_login_at)}</td>
    </tr>
  );
}

export function UsersPage() {
  const { user: me } = useSession();
  const [role, setRole] = useState<Role | "">("staff");
  const [page, setPage] = useState(1);
  const users = useUsers(role || undefined, page);

  return (
    <>
      <PageHeader title={t("users.title")} />
      <div className="detail-layout">
        <div>
          <div className="filters">
            <Field label={t("users.filterRole")} htmlFor="role-filter">
              <select
                id="role-filter"
                value={role}
                onChange={(e) => {
                  setRole(e.target.value as Role | "");
                  setPage(1);
                }}
              >
                <option value="">{t("common.all")}</option>
                {ROLES.map((value) => (
                  <option key={value} value={value}>
                    {tEnum("role", value)}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          {users.isPending ? <Loading /> : null}
          <ErrorAlert error={users.error} />
          {users.data ? (
            users.data.items.length === 0 ? (
              <div className="table-wrapper">
                <Empty />
              </div>
            ) : (
              <>
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>{t("users.name")}</th>
                        <th>{t("users.email")}</th>
                        <th>{t("users.role")}</th>
                        <th>{t("users.active")}</th>
                        <th>{t("users.lastLogin")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.data.items.map((user) => (
                        <UserRow key={user.id} user={user} isSelf={user.id === me?.id} />
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  page={page}
                  size={PAGE_SIZE}
                  total={users.data.total}
                  onChange={setPage}
                />
              </>
            )
          ) : null}
        </div>
        <CreateStaffForm />
      </div>
    </>
  );
}

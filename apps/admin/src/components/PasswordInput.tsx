import { useState, type InputHTMLAttributes } from "react";

import { t } from "../i18n";

/** Password field with an eye button to show what was typed. */
export function PasswordInput(props: Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  const [revealed, setRevealed] = useState(false);
  return (
    <div className="password-input">
      <input {...props} type={revealed ? "text" : "password"} />
      <button
        type="button"
        className="password-toggle"
        aria-label={revealed ? t("login.hidePassword") : t("login.showPassword")}
        aria-pressed={revealed}
        onClick={() => setRevealed((value) => !value)}
      >
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
          <path
            d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
          {revealed ? (
            <path d="M4 4l16 16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          ) : null}
        </svg>
      </button>
    </div>
  );
}

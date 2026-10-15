import { createSession } from "./session";

/** One session and one API client for the whole app. */
export const { session, api } = createSession();

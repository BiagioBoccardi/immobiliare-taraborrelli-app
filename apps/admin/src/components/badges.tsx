import type { LeadPriority, LeadStatus, PropertyStatus } from "@taraborrelli/api-client";

import { tEnum } from "../i18n";
import { Badge, type BadgeTone } from "./ui";

const PRIORITY_TONE: Record<LeadPriority, BadgeTone> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};

const LEAD_STATUS_TONE: Record<LeadStatus, BadgeTone> = {
  new: "info",
  contacted: "neutral",
  appointment_scheduled: "warning",
  mandate_acquired: "success",
  lost: "neutral",
};

const PROPERTY_STATUS_TONE: Record<PropertyStatus, BadgeTone> = {
  draft: "neutral",
  published: "success",
  reserved: "warning",
  sold: "info",
  rented: "info",
  archived: "neutral",
};

export function PriorityBadge({ priority }: { priority: LeadPriority }) {
  return <Badge tone={PRIORITY_TONE[priority]}>{tEnum("leadPriority", priority)}</Badge>;
}

export function LeadStatusBadge({ status }: { status: LeadStatus }) {
  return <Badge tone={LEAD_STATUS_TONE[status]}>{tEnum("leadStatus", status)}</Badge>;
}

export function PropertyStatusBadge({ status }: { status: PropertyStatus }) {
  return <Badge tone={PROPERTY_STATUS_TONE[status]}>{tEnum("propertyStatus", status)}</Badge>;
}

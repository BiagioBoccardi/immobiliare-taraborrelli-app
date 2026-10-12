from app.models.enums import LeadPriority, OwnerIntention

_PRIORITY_BY_INTENTION: dict[OwnerIntention, LeadPriority] = {
    OwnerIntention.KNOW_VALUE: LeadPriority.LOW,
    OwnerIntention.PLANNING: LeadPriority.MEDIUM,
    OwnerIntention.DECIDED: LeadPriority.HIGH,
}


def priority_for(intention: OwnerIntention) -> LeadPriority:
    """The owner's intention determines the initial priority of the lead."""
    return _PRIORITY_BY_INTENTION[intention]

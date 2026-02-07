import frappe


@frappe.whitelist(allow_guest=True)
def get_demo_info():
    """Get general information for the demo landing page"""
    tiers = frappe.get_all(
        "Package Tier",
        fields=["name", "display_name", "description", "is_popular", "trial_days"],
        order_by="sort_order asc",
    )

    industries = frappe.get_all(
        "Industry Template",
        filters={"enabled": 1},
        fields=["name", "industry_name", "icon", "description"],
        order_by="industry_name asc",
    )

    return {
        "tiers": tiers,
        "industries": industries,
    }

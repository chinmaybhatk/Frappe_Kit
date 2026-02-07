import frappe
from frappe.utils import now_datetime, add_days, getdate


def expire_old_demos():
    """Mark expired demo sites"""
    expired = frappe.get_all(
        "Demo Site",
        filters={
            "status": "Active",
            "expires_at": ["<", now_datetime()],
        },
        pluck="name",
    )

    for site_name in expired:
        doc = frappe.get_doc("Demo Site", site_name)
        doc.status = "Suspended"
        doc.save(ignore_permissions=True)

    frappe.db.commit()

    if expired:
        frappe.logger().info(f"Expired {len(expired)} demo sites")


def send_expiry_warnings():
    """Send warning emails for demos expiring soon"""
    settings = frappe.get_single("Provisioner Settings")
    warn_days = settings.expiry_warning_days or 3

    warn_date = add_days(getdate(), warn_days)

    expiring = frappe.get_all(
        "Demo Request",
        filters={
            "status": "Active",
            "trial_expires": ["between", [getdate(), warn_date]],
        },
        fields=[
            "name",
            "contact_email",
            "contact_name",
            "company_name",
            "trial_expires",
            "site_url",
        ],
    )

    for demo in expiring:
        if frappe.db.exists(
            "Communication",
            {
                "reference_doctype": "Demo Request",
                "reference_name": demo.name,
                "subject": ["like", "%expiring%"],
            },
        ):
            continue

        if settings.expiry_warning_template:
            frappe.sendmail(
                recipients=[demo.contact_email],
                template=settings.expiry_warning_template,
                args=demo,
                now=True,
            )


def cleanup_failed_requests():
    """Clean up stuck provisioning requests"""
    stuck = frappe.get_all(
        "Demo Request",
        filters={
            "status": "Provisioning",
            "provisioning_started": ["<", add_days(now_datetime(), -1)],
        },
        pluck="name",
    )

    for req_name in stuck:
        doc = frappe.get_doc("Demo Request", req_name)
        doc.mark_failed("Provisioning timed out after 24 hours")

    frappe.db.commit()

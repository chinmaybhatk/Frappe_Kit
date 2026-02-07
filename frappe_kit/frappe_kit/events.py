import frappe


def on_demo_request_created(doc, method):
    """Handle new demo request creation"""
    frappe.logger().info(
        f"New demo request created: {doc.name} for {doc.company_name}"
    )

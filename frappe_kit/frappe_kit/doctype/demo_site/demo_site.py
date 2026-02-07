import frappe
from frappe.model.document import Document


class DemoSite(Document):
    @frappe.whitelist()
    def send_conversion_link(self):
        """Generate a conversion token and email it to the customer"""
        if self.status != "Active":
            frappe.throw("Can only send conversion links for Active demo sites")

        from frappe_kit.frappe_kit.api.conversion import generate_conversion_token

        token = generate_conversion_token(self.name)

        demo_req = frappe.get_doc("Demo Request", self.demo_request)
        site_url = frappe.utils.get_url()
        convert_url = f"{site_url}/convert?token={token}&site={self.name}"

        frappe.sendmail(
            recipients=[demo_req.contact_email],
            subject=f"Convert your {demo_req.company_name} demo to production",
            message=f"""
            <p>Hi {demo_req.contact_name},</p>
            <p>Ready to take your demo site to production? Click the link below to choose your deployment option:</p>
            <p><a href="{convert_url}" style="background:#4F46E5;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block;">Convert to Production</a></p>
            <p>This link expires in 72 hours.</p>
            <p>If you have any questions, just reply to this email.</p>
            """,
            now=True,
        )

        frappe.msgprint(f"Conversion link sent to {demo_req.contact_email}")
        return {"status": "sent", "email": demo_req.contact_email}

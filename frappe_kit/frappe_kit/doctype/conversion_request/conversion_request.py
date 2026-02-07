import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class ConversionRequest(Document):
    def validate(self):
        if self.demo_site:
            site = frappe.get_doc("Demo Site", self.demo_site)
            if site.status not in ("Active", "Converted"):
                frappe.throw(
                    f"Demo site must be Active to request conversion (current: {site.status})"
                )

        if self.conversion_type == "FC New Site" and not self.production_subdomain:
            frappe.throw("Production subdomain is required for 'FC New Site' conversion")

    @frappe.whitelist()
    def approve(self):
        if self.status != "Pending":
            frappe.throw(f"Cannot approve a request with status: {self.status}")

        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approved_on = now_datetime()
        self.append_log("Conversion request approved")
        self.save()

        return {"status": "approved"}

    @frappe.whitelist()
    def reject(self, reason=None):
        if self.status != "Pending":
            frappe.throw(f"Cannot reject a request with status: {self.status}")

        self.status = "Rejected"
        if reason:
            self.admin_notes = (self.admin_notes or "") + f"\nRejection reason: {reason}"
        self.append_log(f"Conversion request rejected: {reason or 'No reason given'}")
        self.save()

        return {"status": "rejected"}

    @frappe.whitelist()
    def start_conversion(self):
        if self.status != "Approved":
            frappe.throw(f"Cannot start conversion with status: {self.status}")

        self.status = "In Progress"
        self.conversion_started = now_datetime()
        self.save()

        frappe.enqueue(
            "frappe_kit.frappe_kit.api.conversion.process_conversion",
            queue="long",
            timeout=600,
            conversion_request=self.name,
        )

        return {"status": "started", "message": "Conversion process initiated"}

    def append_log(self, message):
        timestamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.conversion_log = (self.conversion_log or "") + log_entry
        self.save(ignore_permissions=True)

    def mark_completed(self, production_url=None):
        self.status = "Completed"
        self.conversion_completed = now_datetime()

        if production_url:
            self.production_site_url = production_url

        self.append_log(f"Conversion completed: {production_url or 'Self-hosted backup ready'}")
        self.save(ignore_permissions=True)

        site = frappe.get_doc("Demo Site", self.demo_site)
        site.status = "Converted"
        site.converted_to_paid = 1
        site.conversion_request = self.name
        if production_url:
            site.production_site_url = production_url
        site.save(ignore_permissions=True)

        self.send_conversion_email()

    def mark_failed(self, error_message):
        self.status = "Failed"
        self.error_message = error_message
        self.append_log(f"Conversion failed: {error_message}")
        self.save(ignore_permissions=True)

    def send_conversion_email(self):
        settings = frappe.get_single("Provisioner Settings")

        if not settings.conversion_email_template:
            self.append_log("No conversion email template configured")
            return

        try:
            frappe.sendmail(
                recipients=[self.contact_email],
                template=settings.conversion_email_template,
                args={
                    "contact_name": self.contact_name,
                    "company_name": self.company_name,
                    "conversion_type": self.conversion_type,
                    "production_site_url": self.production_site_url,
                    "backup_url": self.backup_url,
                },
                now=True,
            )
            self.append_log("Conversion confirmation email sent")
        except Exception as e:
            self.append_log(f"Failed to send conversion email: {str(e)}")

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, add_days
import re


class DemoRequest(Document):
    def validate(self):
        self.validate_email()
        self.generate_subdomain()
        self.set_recommended_tier()

    def validate_email(self):
        """Validate email format and check for disposable domains"""
        if not self.contact_email:
            frappe.throw("Contact email is required")

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, self.contact_email):
            frappe.throw("Invalid email format")

        disposable_domains = [
            "tempmail.com",
            "throwaway.email",
            "guerrillamail.com",
        ]
        domain = self.contact_email.split("@")[1].lower()
        if domain in disposable_domains:
            frappe.throw("Please use a business email address")

    def generate_subdomain(self):
        """Generate subdomain from company name if not provided"""
        if not self.subdomain and self.company_name:
            subdomain = self.company_name.lower()
            subdomain = re.sub(r"[^a-z0-9]", "-", subdomain)
            subdomain = re.sub(r"-+", "-", subdomain)
            subdomain = subdomain.strip("-")[:30]

            settings = frappe.get_single("Provisioner Settings")
            if settings.subdomain_prefix:
                subdomain = f"{settings.subdomain_prefix}{subdomain}"

            original = subdomain
            counter = 1
            while frappe.db.exists("Demo Site", {"subdomain": subdomain}):
                subdomain = f"{original}-{counter}"
                counter += 1

            self.subdomain = subdomain

    def set_recommended_tier(self):
        """Auto-recommend tier based on employee count"""
        if self.employee_count:
            emp_count = int(self.employee_count)
            tiers = frappe.get_all(
                "Package Tier",
                filters={"employee_range_min": ["<=", emp_count]},
                fields=["name", "employee_range_min", "employee_range_max"],
                order_by="employee_range_min desc",
            )

            for tier in tiers:
                if int(tier.employee_range_min) <= emp_count <= (
                    int(tier.employee_range_max) if tier.employee_range_max else 999999
                ):
                    self.recommended_tier = tier.name
                    break

    @frappe.whitelist()
    def start_provisioning(self):
        """Initiate the demo site provisioning process"""
        if self.status not in ["Pending", "Failed"]:
            frappe.throw(f"Cannot provision demo with status: {self.status}")

        self.status = "Provisioning"
        self.provisioning_started = now_datetime()
        self.save()

        frappe.enqueue(
            "frappe_kit.frappe_kit.api.provisioning.provision_demo_site",
            queue="long",
            timeout=600,
            demo_request=self.name,
        )

        return {"status": "started", "message": "Provisioning initiated"}

    def append_log(self, message):
        """Append message to provisioning log"""
        timestamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        self.provisioning_log = (self.provisioning_log or "") + log_entry
        self.save(ignore_permissions=True)

    def mark_completed(self, site_url, username, password):
        """Mark provisioning as completed"""
        self.status = "Active"
        self.provisioning_completed = now_datetime()
        self.site_url = site_url
        self.demo_username = username
        self.demo_password = password

        settings = frappe.get_single("Provisioner Settings")
        tier = frappe.get_doc("Package Tier", self.package_tier)
        trial_days = tier.trial_days or settings.default_trial_days or 14
        self.trial_expires = add_days(now_datetime(), trial_days)

        self.append_log(f"Demo site ready: {site_url}")
        self.save(ignore_permissions=True)

        self.send_welcome_email()

    def mark_failed(self, error_message):
        """Mark provisioning as failed"""
        self.status = "Failed"
        self.error_message = error_message
        self.append_log(f"Provisioning failed: {error_message}")
        self.save(ignore_permissions=True)

    def send_welcome_email(self):
        """Send welcome email with credentials"""
        settings = frappe.get_single("Provisioner Settings")

        if not settings.welcome_email_template:
            self.append_log("No welcome email template configured")
            return

        try:
            frappe.sendmail(
                recipients=[self.contact_email],
                template=settings.welcome_email_template,
                args={
                    "contact_name": self.contact_name,
                    "company_name": self.company_name,
                    "site_url": self.site_url,
                    "username": self.demo_username,
                    "password": self.demo_password,
                    "trial_expires": self.trial_expires,
                    "package_tier": self.package_tier,
                },
                now=True,
            )

            self.credentials_sent = 1
            self.save(ignore_permissions=True)
            self.append_log("Welcome email sent")

        except Exception as e:
            self.append_log(f"Failed to send email: {str(e)}")

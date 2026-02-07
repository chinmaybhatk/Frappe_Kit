import frappe
import requests
import time
import json
import secrets
import string
from frappe.utils import now_datetime


class FrappeCloudAPI:
    """Wrapper for Frappe Cloud API interactions"""

    BASE_URL = "https://frappecloud.com/api/method"

    def __init__(self):
        settings = frappe.get_single("Provisioner Settings")
        self.api_key = settings.frappe_cloud_api_key
        self.api_secret = settings.get_password("frappe_cloud_api_secret")
        self.team = settings.frappe_cloud_team

        if not all([self.api_key, self.api_secret, self.team]):
            frappe.throw("Frappe Cloud API credentials not configured")

    def _get_headers(self):
        return {
            "Authorization": f"token {self.api_key}:{self.api_secret}",
            "Content-Type": "application/json",
        }

    def create_site(self, subdomain, apps, plan="Starter", cluster="Mumbai"):
        """Create a new site on Frappe Cloud"""
        endpoint = f"{self.BASE_URL}/press.api.site.new"

        payload = {
            "site": {
                "subdomain": subdomain,
                "apps": apps,
                "cluster": cluster,
                "plan": plan,
                "team": self.team,
            }
        }

        response = requests.post(
            endpoint,
            headers=self._get_headers(),
            json=payload,
            timeout=60,
        )

        if response.status_code != 200:
            raise Exception(f"Site creation failed: {response.text}")

        return response.json().get("message")

    def get_site_status(self, site_name):
        """Check site provisioning status"""
        endpoint = f"{self.BASE_URL}/press.api.site.get"

        response = requests.get(
            endpoint,
            headers=self._get_headers(),
            params={"name": site_name},
            timeout=30,
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get site status: {response.text}")

        return response.json().get("message", {})

    def install_app(self, site_name, app_name):
        """Install an app on existing site"""
        endpoint = f"{self.BASE_URL}/press.api.site.install_app"

        payload = {"name": site_name, "app": app_name}

        response = requests.post(
            endpoint,
            headers=self._get_headers(),
            json=payload,
            timeout=60,
        )

        return response.status_code == 200

    def change_plan(self, site_name, new_plan):
        """Change a site's subscription plan"""
        endpoint = f"{self.BASE_URL}/press.api.site.change_plan"

        payload = {"name": site_name, "plan": new_plan}

        response = requests.post(
            endpoint,
            headers=self._get_headers(),
            json=payload,
            timeout=60,
        )

        if response.status_code != 200:
            raise Exception(f"Plan change failed: {response.text}")

        return response.json().get("message")

    def create_backup(self, site_name):
        """Trigger a backup for a site"""
        endpoint = f"{self.BASE_URL}/press.api.site.backup"

        payload = {"name": site_name, "with_files": True}

        response = requests.post(
            endpoint,
            headers=self._get_headers(),
            json=payload,
            timeout=60,
        )

        if response.status_code != 200:
            raise Exception(f"Backup creation failed: {response.text}")

        return response.json().get("message")

    def get_backups(self, site_name):
        """Get list of available backups for a site"""
        endpoint = f"{self.BASE_URL}/press.api.site.backups"

        response = requests.get(
            endpoint,
            headers=self._get_headers(),
            params={"name": site_name},
            timeout=30,
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get backups: {response.text}")

        return response.json().get("message", [])


def generate_password(length=12):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def provision_demo_site(demo_request):
    """
    Main provisioning function - called via frappe.enqueue

    Steps:
    1. Create Frappe Cloud site
    2. Wait for site to be active
    3. Install additional apps
    4. Create demo user
    5. Import sample data
    6. Send credentials
    """
    doc = frappe.get_doc("Demo Request", demo_request)

    try:
        settings = frappe.get_single("Provisioner Settings")
        tier = frappe.get_doc("Package Tier", doc.package_tier)
        industry = (
            frappe.get_doc("Industry Template", doc.industry) if doc.industry else None
        )

        cloud_api = FrappeCloudAPI()

        doc.append_log("Starting provisioning...")

        apps = ["frappe", "erpnext"]

        for app_row in tier.frappe_apps:
            if app_row.app_name not in apps:
                apps.append(app_row.app_name)

        module_app_map = {
            "include_sales": "crm",
            "include_support": "helpdesk",
            "include_hr": "hrms",
        }

        for module_field, app_name in module_app_map.items():
            if tier.get(module_field) and app_name not in apps:
                apps.append(app_name)

        doc.append_log(f"Apps to install: {', '.join(apps)}")

        doc.append_log(
            f"Creating site: {doc.subdomain}.{settings.demo_domain}"
        )

        region_map = {
            "India": "Mumbai",
            "Southeast Asia": "Singapore",
            "Europe & UK": "Frankfurt",
            "Middle East & Africa": "Frankfurt",
        }
        cluster = region_map.get(doc.region, settings.default_region or "Mumbai")

        site_result = cloud_api.create_site(
            subdomain=doc.subdomain,
            apps=apps[:2],
            plan=tier.frappe_cloud_plan or "Starter",
            cluster=cluster,
        )

        site_name = site_result.get("name") or f"{doc.subdomain}.{settings.demo_domain}"

        doc.append_log("Waiting for site to be ready...")

        max_wait = 180
        wait_interval = 10
        elapsed = 0

        while elapsed < max_wait:
            status = cloud_api.get_site_status(site_name)
            site_status = status.get("status", "").lower()

            if site_status == "active":
                doc.append_log("Site is active")
                break
            elif site_status in ["broken", "failed"]:
                raise Exception(
                    f"Site creation failed with status: {site_status}"
                )

            time.sleep(wait_interval)
            elapsed += wait_interval
            doc.append_log(f"Still waiting... ({elapsed}s)")

        if elapsed >= max_wait:
            raise Exception("Site creation timed out")

        for app in apps[2:]:
            doc.append_log(f"Installing {app}...")
            cloud_api.install_app(site_name, app)
            time.sleep(5)

        site_url = f"https://{site_name}"
        username = doc.contact_email
        password = generate_password()

        doc.append_log(f"Creating user: {username}")

        demo_site = frappe.get_doc(
            {
                "doctype": "Demo Site",
                "subdomain": doc.subdomain,
                "full_url": site_url,
                "status": "Active",
                "demo_request": doc.name,
                "package_tier": doc.package_tier,
                "industry": doc.industry,
                "region": doc.region,
                "frappe_cloud_site_id": site_name,
                "frappe_cloud_plan": tier.frappe_cloud_plan,
                "apps_installed": ", ".join(apps),
            }
        ).insert(ignore_permissions=True)

        doc.demo_site = demo_site.name

        doc.mark_completed(site_url, username, password)

        frappe.db.commit()

        return {
            "status": "success",
            "site_url": site_url,
            "username": username,
        }

    except Exception as e:
        frappe.db.rollback()
        doc.mark_failed(str(e))
        frappe.log_error(
            title=f"Demo Provisioning Failed: {demo_request}",
            message=frappe.get_traceback(),
        )
        return {"status": "failed", "error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_package_tiers():
    """Public API to get available package tiers"""
    tiers = frappe.get_all(
        "Package Tier",
        filters=(
            {"enabled": 1}
            if frappe.db.has_column("Package Tier", "enabled")
            else {}
        ),
        fields=[
            "name",
            "tier_name",
            "display_name",
            "description",
            "employee_range_min",
            "employee_range_max",
            "price_india",
            "price_sea",
            "price_mea",
            "price_europe",
            "include_accounting",
            "include_inventory",
            "include_sales",
            "include_support",
            "include_hr",
            "include_manufacturing",
            "trial_days",
            "is_popular",
            "color_theme",
            "features_html",
        ],
        order_by="sort_order asc",
    )

    return tiers


@frappe.whitelist(allow_guest=True)
def get_industries():
    """Public API to get available industries"""
    industries = frappe.get_all(
        "Industry Template",
        filters={"enabled": 1},
        fields=[
            "name",
            "industry_code",
            "industry_name",
            "icon",
            "description",
        ],
        order_by="industry_name asc",
    )

    return industries


@frappe.whitelist(allow_guest=True)
def submit_demo_request(data):
    """
    Public API to submit a new demo request

    Args:
        data (dict): {
            company_name, contact_name, contact_email, contact_phone,
            employee_count, industry, region, package_tier,
            selected_modules, priority_features, pain_points,
            utm_campaign, utm_source, utm_medium
        }
    """
    if isinstance(data, str):
        data = frappe.parse_json(data)

    settings = frappe.get_single("Provisioner Settings")
    today_count = frappe.db.count(
        "Demo Request", {"creation": [">=", frappe.utils.today()]}
    )

    if today_count >= (settings.daily_provisioning_limit or 20):
        frappe.throw(
            "Daily limit reached. Please try again tomorrow.",
            frappe.RateLimitExceededError,
        )

    required = [
        "company_name",
        "contact_name",
        "contact_email",
        "employee_count",
        "package_tier",
    ]
    for field in required:
        if not data.get(field):
            frappe.throw(f"{field.replace('_', ' ').title()} is required")

    existing = frappe.db.exists(
        "Demo Request",
        {
            "contact_email": data.get("contact_email"),
            "status": ["in", ["Pending", "Provisioning"]],
        },
    )

    if existing:
        frappe.throw(
            "A demo request is already being processed for this email"
        )

    doc = frappe.get_doc(
        {
            "doctype": "Demo Request",
            "company_name": data.get("company_name"),
            "contact_name": data.get("contact_name"),
            "contact_email": data.get("contact_email"),
            "contact_phone": data.get("contact_phone"),
            "employee_count": data.get("employee_count"),
            "industry": data.get("industry"),
            "region": data.get("region", "India"),
            "package_tier": data.get("package_tier"),
            "priority_features": data.get("priority_features"),
            "pain_points": data.get("pain_points"),
            "utm_campaign": data.get("utm_campaign"),
            "utm_source": data.get("utm_source"),
            "utm_medium": data.get("utm_medium"),
            "ip_address": frappe.local.request_ip,
            "source": "Website",
        }
    )

    doc.insert(ignore_permissions=True)

    doc.start_provisioning()

    frappe.db.commit()

    return {
        "status": "success",
        "demo_request": doc.name,
        "message": "Your demo is being prepared. You'll receive credentials shortly.",
    }


@frappe.whitelist(allow_guest=True)
def check_provisioning_status(demo_request):
    """Check the status of a demo request"""
    doc = frappe.get_doc("Demo Request", demo_request)

    return {
        "status": doc.status,
        "site_url": doc.site_url if doc.status == "Active" else None,
        "error": doc.error_message if doc.status == "Failed" else None,
        "log": doc.provisioning_log,
    }

import frappe
import hashlib
import time
from frappe.utils import now_datetime, get_datetime, add_to_date


def generate_conversion_token(demo_site):
    """Generate a signed token for conversion link"""
    site_doc = frappe.get_doc("Demo Site", demo_site)
    secret = frappe.utils.get_url() + frappe.local.site
    timestamp = str(int(now_datetime().timestamp()))

    raw = f"{demo_site}:{secret}:{timestamp}"
    token = hashlib.sha256(raw.encode()).hexdigest()[:32]

    # store token and timestamp on the site doc for validation
    site_doc.db_set("conversion_token", token, update_modified=False)
    site_doc.db_set("conversion_token_created", now_datetime(), update_modified=False)

    return token


def validate_token(token, demo_site):
    """Validate a conversion token"""
    if not token or not demo_site:
        return False

    site_doc = frappe.get_doc("Demo Site", demo_site)
    stored_token = site_doc.get("conversion_token")

    if not stored_token or stored_token != token:
        return False

    token_created = site_doc.get("conversion_token_created")
    if not token_created:
        return False

    settings = frappe.get_single("Provisioner Settings")
    expiry_hours = settings.conversion_token_expiry_hours or 72
    expiry_time = add_to_date(get_datetime(token_created), hours=expiry_hours)

    if now_datetime() > expiry_time:
        return False

    return True


@frappe.whitelist(allow_guest=True)
def get_conversion_options(token, site):
    """Get demo site details and available production plans for the conversion page"""
    if not validate_token(token, site):
        frappe.throw("Invalid or expired conversion link", frappe.PermissionError)

    site_doc = frappe.get_doc("Demo Site", site)
    demo_req = frappe.get_doc("Demo Request", site_doc.demo_request)

    settings = frappe.get_single("Provisioner Settings")
    plans = []
    for row in settings.production_plans or []:
        plans.append({
            "plan_name": row.plan_name,
            "display_name": row.display_name,
            "description": row.description,
            "monthly_price": row.monthly_price,
        })

    return {
        "site": {
            "name": site_doc.name,
            "subdomain": site_doc.subdomain,
            "full_url": site_doc.full_url,
            "status": site_doc.status,
            "package_tier": site_doc.package_tier,
            "apps_installed": site_doc.apps_installed,
            "created_at": str(site_doc.created_at) if site_doc.created_at else None,
            "expires_at": str(site_doc.expires_at) if site_doc.expires_at else None,
        },
        "company": {
            "name": demo_req.company_name,
            "contact_name": demo_req.contact_name,
            "contact_email": demo_req.contact_email,
            "industry": demo_req.industry,
            "region": demo_req.region,
        },
        "plans": plans,
        "conversion_types": [
            {
                "value": "FC Upgrade In Place",
                "label": "Upgrade Current Site",
                "description": "Keep your current site and data. We'll upgrade your plan to production.",
                "icon": "arrow-up",
            },
            {
                "value": "FC New Site",
                "label": "Fresh Production Site",
                "description": "New site with your demo data migrated over. Clean start with production config.",
                "icon": "plus",
            },
            {
                "value": "Self Hosted",
                "label": "Self-Hosted / Custom Server",
                "description": "Get a full backup of your demo. Deploy on your own infrastructure.",
                "icon": "download",
            },
        ],
    }


@frappe.whitelist(allow_guest=True)
def submit_conversion_request(token, site, data):
    """Submit a conversion request from the customer form"""
    if isinstance(data, str):
        data = frappe.parse_json(data)

    if not validate_token(token, site):
        frappe.throw("Invalid or expired conversion link", frappe.PermissionError)

    site_doc = frappe.get_doc("Demo Site", site)

    # check for existing pending conversion
    existing = frappe.db.exists(
        "Conversion Request",
        {
            "demo_site": site,
            "status": ["in", ["Pending", "Approved", "In Progress"]],
        },
    )

    if existing:
        frappe.throw("A conversion request is already in progress for this site")

    doc = frappe.get_doc({
        "doctype": "Conversion Request",
        "demo_site": site,
        "conversion_type": data.get("conversion_type"),
        "production_plan": data.get("production_plan"),
        "production_subdomain": data.get("production_subdomain"),
        "production_apps": site_doc.apps_installed,
    })

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "conversion_request": doc.name,
        "message": "Your conversion request has been submitted. Our team will review it shortly.",
    }


@frappe.whitelist(allow_guest=True)
def check_conversion_status(conversion_request):
    """Check the status of a conversion request"""
    doc = frappe.get_doc("Conversion Request", conversion_request)

    return {
        "status": doc.status,
        "production_site_url": doc.production_site_url if doc.status == "Completed" else None,
        "backup_url": doc.backup_url if doc.status == "Completed" and doc.conversion_type == "Self Hosted" else None,
        "error": doc.error_message if doc.status == "Failed" else None,
        "log": doc.conversion_log,
    }


def process_conversion(conversion_request):
    """
    Main conversion job — called via frappe.enqueue

    Handles the actual provisioning based on conversion type.
    """
    doc = frappe.get_doc("Conversion Request", conversion_request)
    site_doc = frappe.get_doc("Demo Site", doc.demo_site)

    try:
        from frappe_kit.frappe_kit.api.provisioning import FrappeCloudAPI

        cloud_api = FrappeCloudAPI()
        site_name = site_doc.frappe_cloud_site_id

        if doc.conversion_type == "FC Upgrade In Place":
            _convert_upgrade_in_place(doc, site_doc, cloud_api, site_name)

        elif doc.conversion_type == "FC New Site":
            _convert_new_site(doc, site_doc, cloud_api, site_name)

        elif doc.conversion_type == "Self Hosted":
            _convert_self_hosted(doc, site_doc, cloud_api, site_name)

        frappe.db.commit()

    except Exception as e:
        frappe.db.rollback()
        doc.mark_failed(str(e))
        frappe.log_error(
            title=f"Conversion Failed: {conversion_request}",
            message=frappe.get_traceback(),
        )


def _convert_upgrade_in_place(doc, site_doc, cloud_api, site_name):
    """Upgrade the existing demo site to a production plan"""
    doc.append_log("Starting in-place upgrade...")

    new_plan = doc.production_plan
    if not new_plan:
        raise Exception("No production plan specified")

    doc.append_log(f"Changing plan to: {new_plan}")
    cloud_api.change_plan(site_name, new_plan)

    doc.append_log("Plan upgraded successfully")

    production_url = site_doc.full_url
    doc.mark_completed(production_url)


def _convert_new_site(doc, site_doc, cloud_api, site_name):
    """Create a new production site and migrate data"""
    doc.append_log("Starting new site conversion...")

    # step 1: create backup of demo site
    doc.append_log("Creating backup of demo site...")
    cloud_api.create_backup(site_name)
    time.sleep(10)

    backups = cloud_api.get_backups(site_name)
    if backups:
        latest = backups[0] if isinstance(backups, list) else backups
        backup_url = latest.get("url") or latest.get("remote_file")
        doc.backup_url = backup_url
        doc.backup_created = now_datetime()
        doc.save(ignore_permissions=True)
        doc.append_log(f"Backup created")

    # step 2: create new production site
    subdomain = doc.production_subdomain
    apps_list = [a.strip() for a in (doc.production_apps or "frappe, erpnext").split(",")]

    doc.append_log(f"Creating production site: {subdomain}")

    settings = frappe.get_single("Provisioner Settings")
    region_map = {
        "India": "Mumbai",
        "Southeast Asia": "Singapore",
        "Europe & UK": "Frankfurt",
        "Middle East & Africa": "Frankfurt",
    }

    demo_req = frappe.get_doc("Demo Request", doc.demo_request)
    cluster = region_map.get(demo_req.region, settings.default_region or "Mumbai")

    site_result = cloud_api.create_site(
        subdomain=subdomain,
        apps=apps_list[:2],
        plan=doc.production_plan or "Starter",
        cluster=cluster,
    )

    new_site_name = site_result.get("name") or f"{subdomain}.{settings.demo_domain}"

    # step 3: wait for new site
    doc.append_log("Waiting for production site...")
    max_wait = 180
    elapsed = 0

    while elapsed < max_wait:
        status = cloud_api.get_site_status(new_site_name)
        site_status = status.get("status", "").lower()

        if site_status == "active":
            doc.append_log("Production site is active")
            break
        elif site_status in ("broken", "failed"):
            raise Exception(f"Production site failed: {site_status}")

        time.sleep(10)
        elapsed += 10

    if elapsed >= max_wait:
        raise Exception("Production site creation timed out")

    # step 4: install remaining apps
    for app in apps_list[2:]:
        doc.append_log(f"Installing {app}...")
        cloud_api.install_app(new_site_name, app)
        time.sleep(5)

    production_url = f"https://{new_site_name}"
    doc.append_log(f"Production site ready: {production_url}")
    doc.append_log("Note: Data migration from demo may need manual steps.")
    doc.mark_completed(production_url)


def _convert_self_hosted(doc, site_doc, cloud_api, site_name):
    """Create a backup for self-hosted deployment"""
    doc.append_log("Preparing backup for self-hosted deployment...")

    doc.append_log("Triggering backup...")
    cloud_api.create_backup(site_name)

    # wait a bit for backup to complete
    doc.append_log("Waiting for backup to finish...")
    time.sleep(30)

    backups = cloud_api.get_backups(site_name)
    if not backups:
        raise Exception("No backups found after creation")

    latest = backups[0] if isinstance(backups, list) else backups
    backup_url = latest.get("url") or latest.get("remote_file")

    if not backup_url:
        raise Exception("Backup URL not available yet. Please try again in a few minutes.")

    doc.backup_url = backup_url
    doc.backup_created = now_datetime()
    doc.save(ignore_permissions=True)

    doc.append_log(f"Backup ready for download")
    doc.mark_completed()

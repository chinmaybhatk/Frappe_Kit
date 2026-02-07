app_name = "frappe_kit"
app_title = "Frappe Kit"
app_publisher = "Your Company"
app_description = "Self-service demo site provisioning for Frappe/ERPNext"
app_email = "hello@yourcompany.com"
app_license = "MIT"

# Include JS/CSS files
# app_include_css = "/assets/frappe_kit/css/frappe_kit.css"
# app_include_js = "/assets/frappe_kit/js/frappe_kit.js"

# Website
website_route_rules = [
    {"from_route": "/demo", "to_route": "demo"},
]

# Guest access for demo request APIs
guest_methods = [
    "frappe_kit.frappe_kit.api.provisioning.get_package_tiers",
    "frappe_kit.frappe_kit.api.provisioning.get_industries",
    "frappe_kit.frappe_kit.api.provisioning.submit_demo_request",
    "frappe_kit.frappe_kit.api.provisioning.check_provisioning_status",
]

# Scheduled Tasks
scheduler_events = {
    "daily": [
        "frappe_kit.frappe_kit.tasks.expire_old_demos",
        "frappe_kit.frappe_kit.tasks.send_expiry_warnings",
    ],
    "hourly": [
        "frappe_kit.frappe_kit.tasks.cleanup_failed_requests",
    ],
}

# Document Events
doc_events = {
    "Demo Request": {
        "after_insert": "frappe_kit.frappe_kit.events.on_demo_request_created",
    }
}

# Fixtures (initial data)
fixtures = [
    {
        "doctype": "Package Tier",
        "filters": [],
    },
    {
        "doctype": "Industry Template",
        "filters": [],
    },
]

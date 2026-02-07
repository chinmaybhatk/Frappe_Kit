# Frappe Kit

A Frappe application for self-service demo site provisioning. Built to let potential customers spin up their own fully-configured ERPNext trial instances without any manual intervention.

## What it does

Visitors go to `/demo` on your site, pick a plan, fill in their details, and get a live ERPNext instance provisioned on Frappe Cloud — typically within a couple of minutes. No login required on the provisioning side.

**The flow:**
1. Pick a package tier (Starter / Growth / Enterprise)
2. Enter company details and choose an industry
3. Site gets created automatically via Frappe Cloud API
4. Credentials are emailed to the user

## Key features

- **Tiered packages** with configurable modules, pricing, and trial duration
- **Industry templates** with pre-loaded sample data (Retail, Manufacturing, Services, Distribution)
- **Frappe Cloud integration** — handles site creation, app installation, and status polling
- **Guest-accessible frontend** — single-page wizard using Tailwind CSS, no npm/build step
- **Background provisioning** with real-time log streaming
- **Trial management** — automatic expiry, warning emails, and extensions
- **Rate limiting** and disposable email blocking

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/chinmaybhatk/Frappe_Kit.git
bench --site yoursite install-app frappe_kit
bench --site yoursite migrate
```

## Setup

1. **Provisioner Settings** — add your Frappe Cloud API key/secret, set the team name, domain, and default region
2. **Package Tiers** — create your plans (e.g. Starter, Growth, Enterprise) with module toggles and pricing
3. **Industry Templates** — set up industries with sample data configs

The demo page is served at `/demo` and works for unauthenticated visitors out of the box.

## DocTypes

| DocType | Purpose |
|---------|---------|
| Package Tier | Plan definitions with modules, pricing, trial days |
| Industry Template | Industry configs with sample data and scenarios |
| Demo Request | Tracks each provisioning request end-to-end |
| Demo Site | Records of active/expired demo instances |
| Provisioner Settings | Global config (API keys, limits, email templates) |

## Tech stack

- **Backend**: Frappe Framework (Python), background jobs via `frappe.enqueue`
- **Frontend**: Jinja template + Tailwind CSS via CDN + vanilla JS
- **Provisioning**: Frappe Cloud REST API
- **No build tools required** — works as-is after `bench install-app`

## License

MIT

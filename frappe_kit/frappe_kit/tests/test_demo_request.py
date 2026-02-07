import frappe
import unittest


class TestDemoRequest(unittest.TestCase):
    def setUp(self):
        # Ensure Provisioner Settings exists
        if not frappe.db.exists("Provisioner Settings"):
            frappe.get_doc(
                {"doctype": "Provisioner Settings", "demo_domain": "frappe.cloud"}
            ).insert(ignore_permissions=True)

    def test_subdomain_generation(self):
        doc = frappe.get_doc(
            {
                "doctype": "Demo Request",
                "company_name": "Acme Corporation",
                "contact_name": "John",
                "contact_email": "john@acme.com",
                "employee_count": 25,
                "industry": "",
                "region": "India",
                "package_tier": "Growth",
            }
        )
        doc.generate_subdomain()

        self.assertTrue(doc.subdomain.startswith("acme"))
        self.assertNotIn(" ", doc.subdomain)

    def test_email_validation_rejects_disposable(self):
        doc = frappe.get_doc(
            {
                "doctype": "Demo Request",
                "company_name": "Test",
                "contact_name": "Test",
                "contact_email": "test@tempmail.com",
                "employee_count": 10,
                "region": "India",
                "package_tier": "Starter",
            }
        )

        with self.assertRaises(frappe.ValidationError):
            doc.validate_email()

    def test_email_validation_accepts_valid(self):
        doc = frappe.get_doc(
            {
                "doctype": "Demo Request",
                "company_name": "Test",
                "contact_name": "Test",
                "contact_email": "test@validcompany.com",
                "employee_count": 10,
                "region": "India",
                "package_tier": "Starter",
            }
        )

        # Should not raise
        doc.validate_email()

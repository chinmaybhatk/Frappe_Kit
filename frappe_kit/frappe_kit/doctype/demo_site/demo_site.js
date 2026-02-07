frappe.ui.form.on("Demo Site", {
    refresh(frm) {
        if (frm.doc.status === "Active" && !frm.doc.converted_to_paid) {
            frm.add_custom_button(__("Send Conversion Link"), function () {
                frappe.confirm(
                    "Send a conversion link to the customer?",
                    function () {
                        frm.call("send_conversion_link").then(() =>
                            frm.reload_doc()
                        );
                    }
                );
            }).addClass("btn-primary");
        }

        if (frm.doc.conversion_request) {
            frm.add_custom_button(__("View Conversion"), function () {
                frappe.set_route("Form", "Conversion Request", frm.doc.conversion_request);
            });
        }

        if (frm.doc.production_site_url) {
            frm.add_custom_button(__("Open Production Site"), function () {
                window.open(frm.doc.production_site_url, "_blank");
            });
        }
    },
});

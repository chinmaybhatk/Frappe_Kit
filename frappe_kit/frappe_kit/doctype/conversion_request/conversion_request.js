frappe.ui.form.on("Conversion Request", {
    refresh(frm) {
        if (frm.doc.status === "Pending") {
            frm.add_custom_button(__("Approve"), function () {
                frappe.confirm(
                    "Approve this conversion request?",
                    function () {
                        frm.call("approve").then(() => frm.reload_doc());
                    }
                );
            }, __("Actions"));

            frm.add_custom_button(__("Reject"), function () {
                frappe.prompt(
                    {
                        fieldname: "reason",
                        label: "Rejection Reason",
                        fieldtype: "Small Text",
                    },
                    function (values) {
                        frm.call("reject", { reason: values.reason }).then(() =>
                            frm.reload_doc()
                        );
                    },
                    __("Reject Conversion Request")
                );
            }, __("Actions"));
        }

        if (frm.doc.status === "Approved") {
            frm.add_custom_button(__("Start Conversion"), function () {
                frappe.confirm(
                    "Start the conversion process? This will begin provisioning.",
                    function () {
                        frm.call("start_conversion").then(() =>
                            frm.reload_doc()
                        );
                    }
                );
            }).addClass("btn-primary");
        }

        if (frm.doc.production_site_url) {
            frm.add_custom_button(__("Open Production Site"), function () {
                window.open(frm.doc.production_site_url, "_blank");
            });
        }

        if (frm.doc.backup_url) {
            frm.add_custom_button(__("Download Backup"), function () {
                window.open(frm.doc.backup_url, "_blank");
            });
        }

        // color indicators
        if (frm.doc.status === "Completed") {
            frm.page.set_indicator(__("Completed"), "green");
        } else if (frm.doc.status === "Failed") {
            frm.page.set_indicator(__("Failed"), "red");
        } else if (frm.doc.status === "In Progress") {
            frm.page.set_indicator(__("In Progress"), "orange");
        } else if (frm.doc.status === "Approved") {
            frm.page.set_indicator(__("Approved"), "blue");
        }
    },
});

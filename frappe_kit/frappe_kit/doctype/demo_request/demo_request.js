frappe.ui.form.on("Demo Request", {
  refresh: function (frm) {
    if (frm.doc.status === "Pending" || frm.doc.status === "Failed") {
      frm.add_custom_button(__("Start Provisioning"), function () {
        frm.call("start_provisioning").then(() => {
          frappe.show_alert({
            message: __("Provisioning started"),
            indicator: "green",
          });
          frm.reload_doc();
        });
      });
    }

    if (frm.doc.site_url) {
      frm.add_custom_button(__("Open Demo Site"), function () {
        window.open(frm.doc.site_url, "_blank");
      });
    }
  },
});

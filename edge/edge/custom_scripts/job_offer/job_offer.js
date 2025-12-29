// Copyright (c) 2025, efeone and contributors
// For license information, please see license.txt
frappe.ui.form.on('Job Offer', {
	refresh(frm) {
		add_send_offer_letter_button(frm);
	}
});

/*
* Adds the "Send Offer Letter" button to the Job Offer form.
*/
function add_send_offer_letter_button(frm) {
	if (frm.is_new() || frm.doc.status !== "Awaiting Response") {
		return;
	}

	frm.add_custom_button(__('Send Offer Letter'), () => {
		frappe.call({
			method: "edge.edge.custom_scripts.job_offer.job_offer.send_offer_letter",
			args: {
				job_offer: frm.doc.name
			},
			callback(r) {
				if (!r.exc) {
					frappe.msgprint(__('Offer letter sent successfully.'));
				}
			}
		});
	});
}

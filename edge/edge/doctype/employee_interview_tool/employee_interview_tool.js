// Copyright (c) 2025, efeone and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Interview Tool",{
	onload(frm) {
		frm.set_value('date', frappe.datetime.get_today());
		frm.toggle_display('job_applicants', false);
		!frm.doc.company && frappe.db.get_single_value('Global Defaults','default_company')
		.then(value => frm.set_value('company',value))
	},
    refresh : function (frm){
		frm.disable_save()
		frm.set_value('interview_round', '');
		frm.set_value('scheduled_on', '');
		frm.set_value('from_time', '');
		frm.set_value('to_time', '');
		frm.set_value('department', '');
		frm.set_value('designation', '');
		frm.set_value('status', '');
		frm.set_value('job_opening', '');
		frm.set_value('location', '');
		frm.clear_table('job_applicants');
		frm.refresh_field('job_applicants');
		frm.toggle_display('job_applicants', false);
        fetch_job_applicant(frm);
		toggle_create_interview_button(frm);
        
    }
});

/**
* create a button to fetch job applicants
* On click, fetches job applicants based on filters and populates the child table.
*/
function fetch_job_applicant(frm){
  	let  create_applicant_button = frm.add_custom_button("Get Job Applicants",function(){
        const filters = {};
        if (frm.doc.job_opening){
            filters.job_title = frm.doc.job_opening;
        }
        if (frm.doc.designation){
            filters.designation = frm.doc.designation;
        }
        if (frm.doc.status){
            filters.status = frm.doc.status;
        }
        frappe.call({
            method:"edge.edge.doctype.employee_interview_tool.employee_interview_tool.fetch_job_applicants",
            args:{filters},
            callback:function(r){
                if (r.message){
                    frm.clear_table("job_applicants");
                    r.message.forEach(function(applicant){
                        let row = frm.add_child("job_applicants");
                        row.job_applicant = applicant.name;
                        row.applicant_name = applicant.applicant_name;
                        row.status = applicant.status;
                        row.designation = applicant.designation;
                    });
                    frm.refresh_field("job_applicants");
					frm.toggle_display('job_applicants', true);
					toggle_create_interview_button(frm);
                 } 
            }

        });

    })
	create_applicant_button.removeClass('btn-default').addClass('btn-primary');
}

/**
* create interview for the selected job applicants
* On click, creates interviews or prompts for rescheduling if already exists.
*/
let create_interview_btn = null;
function toggle_create_interview_button(frm) {
	if (create_interview_btn) {
		create_interview_btn.remove();
		create_interview_btn = null;
	}
		create_interview_btn = frm.add_custom_button('Create Interview', function () {
			let selected_rows = frm.fields_dict.job_applicants.grid.get_selected_children();
			if (!selected_rows.length) {
				frappe.msgprint(__('Please select one or more rows in the Job Applicants table.'));
				return;
			}
			let missing_fields = [];
			if (!frm.doc.interview_round) missing_fields.push(__('Interview Round'));
			if (!frm.doc.scheduled_on) missing_fields.push(__('Scheduled On'));
			if (!frm.doc.from_time) missing_fields.push(__('From Time'));
			if (!frm.doc.to_time) missing_fields.push(__('To Time'));
			if (missing_fields.length) {
				frappe.msgprint({
					title: __('Missing Required Scheduling Fields'),
					message: __('Please ensure the following fields are filled:') +
						'<br><b>' + missing_fields.join(', ') + '</b>',
					indicator: 'orange'
				});
				return;
			}
			frappe.call({
				method: 'edge.edge.doctype.employee_interview_tool.employee_interview_tool.create_bulk_interviews',
				args: {
					applicants: selected_rows.map(row => ({
						job_applicant: row.job_applicant,
						applicant_name: row.applicant_name,
						designation: row.designation,
						interview_round: frm.doc.interview_round,
						scheduled_on: frm.doc.scheduled_on,
						from_time: frm.doc.from_time,
						to_time: frm.doc.to_time
					}))
				},
				callback: function (r) {
					if (!r.exc) {
						let data = r.message || {};
						if (Array.isArray(data.created) && data.created.length > 0) {
							const created_ids = data.created.map(c => c.job_applicant).join(', ');
							frappe.msgprint(__('Interviews created successfully for: ') + created_ids);
						}
						if (Array.isArray(data.skipped_applicants) && data.skipped_applicants.length > 0) {
							frappe.confirm(
								__('Interviews already exist for: {0}.<br>Do you want to reschedule?', [data.skipped_applicants.join(', ')]),
								() => {
									frappe.prompt([
										{
											label: 'Scheduled On',
											fieldname: 'scheduled_on',
											fieldtype: 'Date',
											default: frm.doc.scheduled_on,
											reqd: 1
										},
										{
											label: 'From Time',
											fieldname: 'from_time',
											fieldtype: 'Time',
											default: frm.doc.from_time,
											reqd: 1
										},
										{
											label: 'To Time',
											fieldname: 'to_time',
											fieldtype: 'Time',
											default: frm.doc.to_time,
											reqd: 1
										}
									], (values) => {
										frappe.call({
											method: 'edge.edge.doctype.employee_interview_tool.employee_interview_tool.reschedule_interviews',
											args: {
												applicants: data.skipped_applicants,
												interview_round: frm.doc.interview_round,
												scheduled_on: values.scheduled_on,
												from_time: values.from_time,
												to_time: values.to_time,
											},
											callback: function(r) {
												if (!r.exc) {
													frappe.msgprint(__('Interview rescheduled successfully.'));
													frm.refresh();
												}
											}
										});
									}, __('Reschedule Interviews'));
								},
								() => {
									frappe.msgprint(__('Reschedule cancelled.'));
								}
							);
						}
					}
				}
			});
		});
		create_interview_btn.removeClass('btn-default').addClass('btn-primary');
}
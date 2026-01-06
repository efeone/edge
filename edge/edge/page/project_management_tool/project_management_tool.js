frappe.pages['project-management-tool'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Project Management Tool',
		single_column: true
	});
	let $button = page.set_secondary_action('Refresh', () => location.reload())
	page.main.addClass("frappe-card");
	make_filters(page);
	page.current_page = 1;
	page.page_length = 20;
	refresh_projects(page);
}

/*
Creates filter fields on the page and binds change events to refresh the project list.
*/
function make_filters(page) {
	const filters = [
		{ label: "Project", fieldname: "project", options: "Project" },
		{ label: "Customer", fieldname: "customer", options: "Customer" },
		{
			label: "Employee",
			fieldname: "employee",
			options: "User",
			default: get_employee_id(),
			read_only: frappe.session.user === 'Administrator' ? 0 : 1
		},
		{ label: "Department", fieldname: "department", options: "Department" },
		{ label: "From Date", fieldname: "from_date", fieldtype: "Date" },
		{ label: "To Date", fieldname: "to_date", fieldtype: "Date" }
	];
	const bind_refresh = (fieldname) => {
		let field = page.fields_dict[fieldname];
		field.$input.on('change', function () {
			refresh_projects(page);
		});
	};
	filters.forEach(f => {
		page.add_field({
			label: __(f.label),
			fieldname: f.fieldname,
			fieldtype: f.fieldtype || "Link",
			options: f.options,
			default: f.default || undefined,
			read_only: f.read_only || 0,
			change() {
				refresh_projects(page);
			}
		});
		bind_refresh(f.fieldname);
	});
	page.add_field({
		label: __("Status"),
		fieldname: "status",
		fieldtype: "Select",
		options: [
			"",
			"Open",
			"Completed",
			"Cancelled"
		],
		default: "",
		change() {
			refresh_projects(page);
		}
	});
}

/*
 Returns the current user's Employee ID, or an empty string if user is Administrator.
*/
function get_employee_id() {
	if (frappe.session.user === 'Administrator') {
		return '';
	}
	else {
		return frappe.session.user
	}
}

/*
 Clear existing projects from the page
*/
function refresh_projects(page, page_num = null) {
	if (page_num) {
		page.current_page = page_num;
	} else {
		page.current_page = page.current_page || 1;
	}
	page.body.find(".frappe-list").remove();
	const selected_status = page.fields_dict.status.get_value();
	const project_name = page.fields_dict.project.get_value();
	const customer_name = page.fields_dict.customer.get_value();
	const department = page.fields_dict.department.get_value();
	const employee = page.fields_dict.employee.get_value()  || null;
	const from_date = page.fields_dict.from_date.get_value();
	const to_date = page.fields_dict.to_date.get_value();
	frappe.call({
		method: "edge.edge.page.project_management_tool.project_management_tool.get_project",
		args: {
			status: selected_status,
			project: project_name,
			customer: customer_name,
			department: department,
			employee: employee,
			from_date: from_date,
			to_date: to_date,
			page: page.current_page,
			page_length: page.page_length
		},
		callback: (r) => {
			if (r.message && r.message.length > 0) {
				$(frappe.render_template("project_management_tool", { project_list: r.message })).appendTo(page.body); 
				page.body.find(".showTask").on("click", function () {
					var project_id = $(this).attr("project");
					frappe.route_options = {
						project: project_id
					};					
				});
				render_pagination_controls(page, r.message.length);
				setup_page_length_buttons(page);
			} else {
				$('<div class="frappe-list"></div>').appendTo(page.body)
					.append('<div class="no-result text-muted flex justify-center align-center" style="text-align: center;"><p>No Project found with matching filters.</p></div>');
			}
		},
		freeze: true,
		freeze_message: 'Loading Project'
	});
}

/*
Renders pagination controls (Previous, Next, and Page Info) inside #pagination-container.
*/
function render_pagination_controls(page, result_count) {
	const container = $("#pagination-container");
	container.empty();
	const prev_btn = $('<button class="page-btn btn btn-default btn-sm me-2">Previous</button>');
	const next_btn = $('<button class="page-btn btn btn-default btn-sm">Next</button>');
	const info_text = $(`<span style="margin: 0 10px;">Page ${page.current_page}</span>`);
	if (page.current_page === 1) prev_btn.prop('disabled', true);
	if (result_count < page.page_length) next_btn.prop('disabled', true);
	prev_btn.on('click', () => refresh_projects(page, page.current_page - 1));
	next_btn.on('click', () => refresh_projects(page, page.current_page + 1));
	container.append(prev_btn, info_text, next_btn);
}

/*
Sets up event listeners for page length buttons to change the number of items displayed per page.
*/
function setup_page_length_buttons(page) {
	$(".page-length-btn").removeClass("active");
	$(`.page-length-btn[data-length="${page.page_length}"]`).addClass("active");
	$(".page-length-btn").off('click').on('click', function () {
		$(".page-length-btn").removeClass("active");
		$(this).addClass("active");
		page.page_length = parseInt($(this).attr("data-length"));
		page.current_page = 1;
		refresh_projects(page);
	});
}

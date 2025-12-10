import json
from datetime import datetime, timedelta

import frappe
import pytz
from frappe.utils import (
	formatdate,
	get_first_day,
	get_last_day,
	getdate,
	now_datetime,
	nowdate,
	today,
)


@frappe.whitelist()
def get_holidays_by_list_name(holiday_list_name):
    """
    Return holidays for the given Holiday List name
    """
	if not holiday_list_name:
		frappe.throw("Holiday List name is required")

	holidays = frappe.get_all(
		"Holiday",
		filters={"parent": holiday_list_name},
		fields=["holiday_date", "description", "weekly_off"],
		order_by="holiday_date asc",
	)
	return holidays


@frappe.whitelist()
def get_attendance_summary(user_id=None, month=None):
	"""Return attendance summary for given month (default: current month)"""
	import datetime

	if not user_id:
		user_id = frappe.session.user

	employee = frappe.db.get_value("Employee", {"user_id": user_id}, "name")
	if not employee:
		return {
			"Present": 0,
			"Absent": 0,
			"Work From Home": 0,
			"On Leave": 0,
			"Half Day": 0,
		}

	today = getdate(nowdate())
	if month:
		year, month_num = map(int, month.split("-"))
		month_start = datetime.date(year, month_num, 1)
		# get first day of next month, then subtract 1 day
		if month_num == 12:
			month_end = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
		else:
			month_end = datetime.date(year, month_num + 1, 1) - datetime.timedelta(
				days=1
			)
	else:
		month_start = get_first_day(today)
		month_end = get_last_day(today)

	# Count attendance
	summary = {}
	statuses = ["Present", "Absent", "Work From Home", "On Leave", "Half Day"]
	for status in statuses:
		summary[status] = frappe.db.count(
			"Attendance",
			{
				"employee": employee,
				"status": status,
				"attendance_date": ["between", [month_start, month_end]],
				"docstatus": ["!=", 2],
			},
		)

	return summary


@frappe.whitelist()
def get_today_checkin_status():
    """
    Return today's check-in status for logged-in employee
    """
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		return {"error": "No Employee linked with this user"}

	# Get today's date in server timezone
	from frappe.utils import get_datetime, getdate

	today_date = getdate()

	# Fetch all checkins for today, ordered by time
	checkins_today = frappe.db.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ["between", [f"{today_date} 00:00:00", f"{today_date} 23:59:59"]],
		},
		fields=["log_type", "time"],
		order_by="time asc",
	)

	if not checkins_today:
		# No check-ins today
		return {
			"first_checkin": None,
			"last_checkin": None,
			"last_checkout": None,
			"worked_seconds": 0,
		}

	# Get first check-in
	first_checkin = next((c.time for c in checkins_today if c.log_type == "IN"), None)

	# Get last entry to determine current state
	last_entry = checkins_today[-1]

	# Determine if currently checked in or out
	is_checked_in = last_entry.log_type == "IN"

	# Calculate worked seconds
	worked_seconds = 0
	temp_checkin = None

	for entry in checkins_today:
		if entry.log_type == "IN":
			temp_checkin = entry.time
		elif entry.log_type == "OUT" and temp_checkin:
			# Calculate duration for this session
			checkin_dt = get_datetime(temp_checkin)
			checkout_dt = get_datetime(entry.time)
			worked_seconds += (checkout_dt - checkin_dt).total_seconds()
			temp_checkin = None

	# If currently checked in, add ongoing session time
	if temp_checkin:
		checkin_dt = get_datetime(temp_checkin)
		now = now_datetime()
		worked_seconds += (now - checkin_dt).total_seconds()

	# Convert to user timezone
	user_timezone = (
		frappe.db.get_value("User", frappe.session.user, "time_zone") or "Asia/Kolkata"
	)
	server_timezone = "Asia/Kolkata"
	tz_user = pytz.timezone(user_timezone)
	tz_server = pytz.timezone(server_timezone)

	def convert_to_user_tz(dt):
		if not dt:
			return None
		dt = get_datetime(dt)
		if dt.tzinfo is None:
			dt_server = tz_server.localize(dt)
		else:
			dt_server = dt
		dt_user = dt_server.astimezone(tz_user)
		return dt_user.strftime("%Y-%m-%d %H:%M:%S")

	# Get last check-in and last check-out times
	last_checkin = None
	last_checkout = None

	for entry in reversed(checkins_today):
		if entry.log_type == "IN" and not last_checkin:
			last_checkin = entry.time
		if entry.log_type == "OUT" and not last_checkout:
			last_checkout = entry.time
		if last_checkin and last_checkout:
			break

	return {
		"first_checkin": convert_to_user_tz(first_checkin),
		"last_checkin": convert_to_user_tz(last_checkin),
		"last_checkout": (
			convert_to_user_tz(last_checkout) if not is_checked_in else None
		),
		"worked_seconds": int(worked_seconds),
		"is_checked_in": is_checked_in,
	}


@frappe.whitelist()
def mark_checkin(log_type, latitude=None, longitude=None):
    """
    Mark check-in or check-out for logged-in employee with location data
    """
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		frappe.throw("No Employee linked with this user")

	# Validate location data
	if not latitude or not longitude:
		frappe.throw("Location data (latitude and longitude) is required for check-in")

	# Convert to float
	try:
		lat = float(latitude)
		lng = float(longitude)
	except (ValueError, TypeError):
		frappe.throw("Invalid latitude or longitude values")

	# Create geolocation GeoJSON format
	geolocation = json.dumps(
		{
			"type": "FeatureCollection",
			"features": [
				{
					"type": "Feature",
					"properties": {},
					"geometry": {
						"type": "Point",
						"coordinates": [
							lng,
							lat,
						],  # GeoJSON uses [longitude, latitude] order
					},
				}
			],
		}
	)

	# Insert new checkin/out
	doc = frappe.get_doc(
		{
			"doctype": "Employee Checkin",
			"employee": employee,
			"time": now_datetime(),
			"log_type": log_type,
			"latitude": lat,
			"longitude": lng,
			"geolocation": geolocation,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	# Fetch checkins for today
	checkins_today = frappe.db.get_all(
		"Employee Checkin",
		filters={"employee": employee, "time": [">=", today() + " 00:00:00"]},
		fields=["log_type", "time"],
		order_by="time asc",
	)

	first_checkin = next((c.time for c in checkins_today if c.log_type == "IN"), None)
	last_checkin_of_day = next(
		(c.time for c in reversed(checkins_today) if c.log_type == "IN"), None
	)

	# --- Convert from server timezone to user timezone ---
	user_timezone = (
		frappe.db.get_value("User", frappe.session.user, "time_zone") or "Asia/Kolkata"
	)
	server_timezone = "Asia/Kolkata"  # replace with your server timezone
	tz_user = pytz.timezone(user_timezone)
	tz_server = pytz.timezone(server_timezone)

	def convert_to_user_tz(dt):
		if not dt:
			return None
		# If dt is string, parse it; else use directly
		if isinstance(dt, str):
			dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
		# Localize as server timezone
		if dt.tzinfo is None:
			dt_server = tz_server.localize(dt)
		else:
			dt_server = dt
		# Convert to user timezone
		dt_user = dt_server.astimezone(tz_user)
		return dt_user.strftime("%Y-%m-%d %H:%M:%S")

	first_checkin_local = convert_to_user_tz(first_checkin)
	last_checkin_local = convert_to_user_tz(last_checkin_of_day)

	return {
		"success": True,
		"log_type": log_type,
		"first_checkin": first_checkin_local,
		"last_checkin": last_checkin_local,
	}


@frappe.whitelist()
def get_today_checkin_checkout(employee=None):
	"""Return today's check-in and check-out times for logged-in employee"""
	if not employee:
		employee = frappe.db.get_value(
			"Employee", {"user_id": frappe.session.user}, "name"
		)

	logs = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ["between", [today() + " 00:00:00", today() + " 23:59:59"]],
		},
		fields=["time", "log_type"],
		order_by="time asc",
		ignore_permissions=True,
	)

	checkin, checkout = None, None
	for log in logs:
		if log.log_type == "IN" and not checkin:
			checkin = log.time
		if log.log_type == "OUT":
			checkout = log.time

	return {
		"checkin": checkin.time().strftime("%H:%M:%S") if checkin else "00:00:00",
		"checkout": checkout.time().strftime("%H:%M:%S") if checkout else "00:00:00",
	}


@frappe.whitelist()
def get_employee_attendance():
	"""Return Present / Absent count of logged-in employee for current month"""
	today = frappe.utils.getdate(nowdate())
	start_date = get_first_day(today)
	end_date = get_last_day(today)

	# Get Employee linked to logged-in user
	employee = frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user}, "name", as_dict=False
	)
	if not employee:
		return {"present": 0, "absent": 0}

	# Count Present
	present_count = frappe.get_all(
		"Attendance",
		filters={
			"employee": employee,
			"status": "Present",
			"attendance_date": ["between", [start_date, end_date]],
			"docstatus": ["!=", 2],
		},
		ignore_permissions=True,
		pluck="name",
	)
	present_count = len(present_count)

	# Count Absent
	absent_count = frappe.get_all(
		"Attendance",
		filters={
			"employee": employee,
			"status": "Absent",
			"attendance_date": ["between", [start_date, end_date]],
			"docstatus": ["!=", 2],
		},
		ignore_permissions=True,
		pluck="name",
	)
	absent_count = len(absent_count)

	return {"present": present_count, "absent": absent_count}


@frappe.whitelist()
def get_absent_days(user_id=None):
	"""
    Return leave applications active today (with their workflow_state).
	If user_id is provided, restrict to the employee mapped to that user.
	Otherwise return all leave applications that cover today.
	"""
	# If user_id is provided, resolve employee; otherwise return for all employees
	employee = None
	if user_id:
		employee = frappe.db.get_value(
			"Employee", {"user_id": user_id}, "name", as_dict=False
		)
		if not employee:
			return []

	today_date = today()  # YYYY-MM-DD

	filters = {
		"docstatus": ["!=", 2],
		"from_date": ["<=", today_date],
		"to_date": [">=", today_date],
	}

	leaves = frappe.db.get_all(
		"Leave Application",
		filters=filters,
		fields=[
			"name",
			"employee",
			"leave_type",
			"from_date",
			"to_date",
			"status",
		],
		order_by="from_date asc, name asc",
		ignore_permissions=True,
	)

	return leaves


@frappe.whitelist()
def get_today_birthdays():
	"""Return employees with birthday today (ignoring year)"""
	today = nowdate()  # YYYY-MM-DD
	today_mm_dd = today[5:]  # "MM-DD"

	employees = frappe.db.sql(
		"""
		SELECT name, employee_name, department, designation, company, date_of_birth, image
		FROM `tabEmployee`
		WHERE date_of_birth IS NOT NULL
		  AND DATE_FORMAT(date_of_birth, '%%m-%%d') = %s
		  AND status = 'Active'
	""",
		(today_mm_dd,),
		as_dict=True,
	)

	return employees


@frappe.whitelist()
def get_today_anniversaries():
	# Get today's month and day
	today = frappe.utils.nowdate()  # YYYY-MM-DD
	today_month_day = frappe.utils.formatdate(today, "MM-dd")

	# Query employees whose DOJ month+day matches today's month+day
	employees = frappe.db.sql(
		"""
		SELECT
			name,
			employee_name,
			date_of_joining,
			image,
			department,
			designation
		FROM `tabEmployee`
		WHERE status = 'Active'
		  AND DATE_FORMAT(date_of_joining, '%%m-%%d') = %s
	""",
		(today_month_day,),
		as_dict=True,
	)

	return employees


@frappe.whitelist()
def get_weekly_schedule():
    """Return weekly shift schedule for logged-in employee (Mon → Sun)"""
	from datetime import timedelta

	from frappe.utils import getdate

	today = getdate()
	weekday = today.weekday()  # 0 = Monday
	monday = today - timedelta(days=weekday)  # this week's Monday
	next_monday = monday + timedelta(days=7)

	# Get logged-in employee
	emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not emp:
		return []

	# Fetch shift assignments for this week
	shift_assignments = frappe.db.sql(
		"""
		SELECT sa.start_date, sa.end_date, s.start_time, s.end_time
		FROM `tabShift Assignment` sa
		JOIN `tabShift Type` s ON sa.shift_type = s.name
		WHERE sa.employee = %s
		  AND sa.start_date <= %s
		  AND sa.end_date >= %s
	""",
		(emp, next_monday, monday),
		as_dict=True,
	)

	schedule = []
	for i in range(7):  # Mon → Sun
		day_date = monday + timedelta(days=i)
		date_str = formatdate(day_date, "yyyy-MM-dd")
		day_str = day_date.strftime("%A")

		row = {
			"date": date_str,
			"day": day_str,
			"in_time": "",
			"end_time": "",
			"status": "OK",
			"remarks": "Accepted",
		}

		# Check if any shift assignment covers this day
		for sa in shift_assignments:
			if sa.start_date <= day_date <= sa.end_date:
				row["in_time"] = str(sa.start_time) if sa.start_time else ""
				row["end_time"] = str(sa.end_time) if sa.end_time else ""
				break

		schedule.append(row)

	return schedule


@frappe.whitelist()
def get_employee_adherence():
	"""Return Adherence % for logged-in employee (monthly)"""
	today = nowdate()
	start_date = get_first_day(today)
	end_date = get_last_day(today)

	# Get Employee linked to logged-in user
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		return {"adherence": 0}

	# Fetch all attendances in current month
	attendances = frappe.get_all(
		"Attendance",
		filters={
			"employee": employee,
			"attendance_date": ["between", [start_date, end_date]],
			"status": "Present",
			"docstatus": ["!=", 2],
		},
		fields=["attendance_date", "in_time", "out_time", "shift"],
	)

	buffer = timedelta(minutes=10)
	total_scheduled_time = timedelta(0)
	total_non_adherence = timedelta(0)

	for att in attendances:
		# Get shift timings (example: from Shift Type)
		shift_start, shift_end = (
			frappe.db.get_value("Shift Type", att.shift, ["start_time", "end_time"])
			if att.shift
			else (None, None)
		)

		if not (shift_start and shift_end and att.in_time and att.out_time):
			continue

		# Ensure shift_start and shift_end are datetime.time
		if isinstance(shift_start, timedelta):
			shift_start = (datetime.min + shift_start).time()
		elif isinstance(shift_start, str):
			shift_start = datetime.strptime(shift_start, "%H:%M:%S").time()

		if isinstance(shift_end, timedelta):
			shift_end = (datetime.min + shift_end).time()
		elif isinstance(shift_end, str):
			shift_end = datetime.strptime(shift_end, "%H:%M:%S").time()

		# Convert shift times into datetime objects
		date = att.attendance_date
		scheduled_start_dt = datetime.combine(date, shift_start)
		scheduled_end_dt = datetime.combine(date, shift_end)
		checkin_dt = att.in_time
		checkout_dt = att.out_time

		# Add scheduled time for the day
		scheduled_time = scheduled_end_dt - scheduled_start_dt
		total_scheduled_time += scheduled_time

		# Calculate allowed login time (with buffer)
		allowed_start = scheduled_start_dt + buffer

		# Late login beyond buffer
		if checkin_dt > allowed_start:
			total_non_adherence += checkin_dt - allowed_start

		# Early logout
		if checkout_dt < scheduled_end_dt:
			total_non_adherence += scheduled_end_dt - checkout_dt

	adherence = 0
	if total_scheduled_time.total_seconds() > 0:
		adherence = (
			(total_scheduled_time - total_non_adherence).total_seconds()
			/ total_scheduled_time.total_seconds()
		) * 100

	return {"adherence": round(adherence, 2)}


@frappe.whitelist()
def get_employee_shrinkage():
	"""Return Shrinkage % of logged-in employee for current month"""
	from frappe.utils import get_first_day, get_last_day, nowdate

	today = nowdate()
	start_date = get_first_day(today)
	end_date = get_last_day(today)

	# Get Employee linked to logged-in user
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		return {"shrinkage": 0}

	# Total scheduled working days (Attendance record exists)
	scheduled_days = frappe.db.count(
		"Attendance",
		{
			"employee": employee,
			"attendance_date": ["between", [start_date, end_date]],
			"docstatus": ["!=", 2],
		},
	)

	if scheduled_days == 0:
		return {"shrinkage": 0}

	# Shrinkage days = Approved Leave (On Leave) + Absent
	shrinkage_days = frappe.db.count(
		"Attendance",
		{
			"employee": employee,
			"attendance_date": ["between", [start_date, end_date]],
			"status": ["in", ["On Leave", "Absent"]],
			"docstatus": ["!=", 2],
		},
	)

	# Shrinkage % formula
	shrinkage_percent = round((shrinkage_days / scheduled_days) * 100, 2)

	return {"shrinkage": shrinkage_percent}

@frappe.whitelist()
def set_employee_mood(mood):
	user = frappe.session.user
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

	if not employee:
		frappe.throw("No Employee linked with this user")

	# Get or create today's tracker
	tracker_name = frappe.db.exists("Employee Mood Tracker", {"date": today()})
	if tracker_name:
		tracker = frappe.get_doc("Employee Mood Tracker", tracker_name)
	else:
		tracker = frappe.get_doc(
			{
				"doctype": "Employee Mood Tracker",
				"date": today(),
				"mood": "{}",  # start empty JSON
			}
		)
		tracker.insert(ignore_permissions=True)

	# Convert JSON string -> dict
	moods = {}
	if tracker.mood:
		try:
			moods = json.loads(tracker.mood)
		except Exception:
			moods = {}

	# Overwrite today's mood for this employee
	moods[employee] = mood

	# Save back as JSON string
	tracker.mood = json.dumps(moods, ensure_ascii=False)  # keep emoji properly
	tracker.save(ignore_permissions=True)

	return {"employee": employee, "mood": mood}


@frappe.whitelist()
def get_employee_mood():
    """Return today's mood for logged-in employee"""
	user = frappe.session.user
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

	if not employee:
		return {}

	tracker_name = frappe.db.exists("Employee Mood Tracker", {"date": today()})
	if not tracker_name:
		return {}

	tracker = frappe.get_doc("Employee Mood Tracker", tracker_name)
	if not tracker.mood:
		return {}

	try:
		moods = json.loads(tracker.mood)
	except Exception:
		moods = {}

	return {"employee": employee, "mood": moods.get(employee)}


@frappe.whitelist()
def get_new_joinees(start_date=None, end_date=None):
	"""Return employees who joined in the last 30 days"""
	from datetime import timedelta

	from frappe.utils import getdate, nowdate

	if not start_date:
		start_date = end_date - timedelta(days=30)
	if not end_date:
		end_date = nowdate()

	employees = frappe.db.get_all(
		"Employee",
		filters={
			"date_of_joining": ["between", [start_date, end_date]],
			"status": "Active",
		},
		fields=[
			"name",
			"employee_name",
			"date_of_joining",
			"department",
			"designation",
			"image",
		],
		order_by="date_of_joining desc",
	)

	return employees


@frappe.whitelist()
def get_late_arrival_status(month):
	"""
	Get late arrival status for an employee for the given month.
	Only returns data if employee is approaching or exceeding the limit.

	Args:
			month (str): Month in format 'YYYY-MM'

	Returns:
			dict: Warning information if applicable, None otherwise
	"""
	from datetime import datetime

	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")

	if not employee:
		return {"show_warning": False}

	# Parse month
	year, month_num = month.split("-")
	from_date = f"{year}-{month_num}-01"

	# Get last day of month
	import calendar

	last_day = calendar.monthrange(int(year), int(month_num))[1]
	to_date = f"{year}-{month_num}-{last_day}"

	# Get late arrival log for this month
	late_log = frappe.db.get_value(
		"Employee Late Arrival Log",
		{"employee": employee, "from_date": from_date, "to_date": to_date},
		["total_late_time", "allowed_late_arrival_time"],
		as_dict=True,
	)

	if not late_log:
		return {"show_warning": False}

	# Convert seconds to minutes
	total_late_minutes = (late_log.total_late_time or 0) / 60
	allowed_minutes = (late_log.allowed_late_arrival_time or 0) / 60

	if allowed_minutes == 0:
		return {"show_warning": False}

	# Calculate percentage used
	percentage_used = (total_late_minutes / allowed_minutes) * 100

	# Only show warning if >= 70% used
	if percentage_used < 70:
		return {"show_warning": False}

	remaining_minutes = max(0, allowed_minutes - total_late_minutes)
	exceeded = total_late_minutes > allowed_minutes
	excess_minutes = max(0, total_late_minutes - allowed_minutes)

	# Determine warning level
	if exceeded or percentage_used >= 100:
		warning_level = "critical"
	elif percentage_used >= 90:
		warning_level = "high"
	else:
		warning_level = "medium"

	return {
		"show_warning": True,
		"total_late_minutes": round(total_late_minutes, 0),
		"allowed_minutes": round(allowed_minutes, 0),
		"remaining_minutes": round(remaining_minutes, 0),
		"percentage_used": round(percentage_used, 1),
		"exceeded": exceeded,
		"excess_minutes": round(excess_minutes, 0),
		"warning_level": warning_level,
	}
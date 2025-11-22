"""
University Appointment System
-----------------------------
This Flask application allows students to register, log in, view available appointments,
schedule new appointments, and manage their bookings. It connects to a SQLite database
and provides basic CRUD operations for appointments and availability.
"""

from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)

# =========================
# Database Models
# =========================

class Department(db.Model):
    __tablename__ = "departments"
    department_id = db.Column(db.Integer, primary_key=True)
    department_name = db.Column(db.String(100), nullable=False, unique=True)
    building = db.Column(db.String(100))
    phone = db.Column(db.String(20))

    users = db.relationship("User", backref="department", lazy=True)


class User(db.Model):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'student', 'faculty', 'admin'
    password_hash = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.department_id"))

    availabilities = db.relationship(
        "Availability", backref="faculty", lazy=True,
        foreign_keys="Availability.faculty_id"
    )
    student_appointments = db.relationship(
        "Appointment", backref="student", lazy=True,
        foreign_keys="Appointment.student_id"
    )
    faculty_appointments = db.relationship(
        "Appointment", backref="faculty", lazy=True,
        foreign_keys="Appointment.faculty_id"
    )


class Availability(db.Model):
    __tablename__ = "availability"
    availability_id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    day_of_week = db.Column(db.String(10), nullable=False)  # e.g. 'Mon'
    start_time = db.Column(db.String(5), nullable=False)    # '09:00'
    end_time = db.Column(db.String(5), nullable=False)      # '10:00'
    is_available = db.Column(db.Boolean, default=True)


class Appointment(db.Model):
    __tablename__ = "appointments"
    appointment_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    appointment_date = db.Column(db.String(10), nullable=False)  # 'YYYY-MM-DD'
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    status = db.Column(db.String(20), default="scheduled")  # scheduled/cancelled/completed
    purpose = db.Column(db.String(255))


class Notification(db.Model):
    __tablename__ = "notifications"
    notification_id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(
        db.Integer,
        db.ForeignKey("appointments.appointment_id"),
        nullable=False
    )
    message = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_status = db.Column(db.String(20), default="pending")


# =========================
# Helper functions
# =========================

def current_user():
    uid = session.get("user_id")
    if uid:
        return User.query.get(uid)
    return None


def login_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


# =========================
# Routes: Auth
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]
        department_id = request.form.get("department_id")

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        user = User(
            name=name,
            email=email,
            role=role,
            password_hash=password_hash,
            department_id=department_id if department_id else None
        )
        db.session.add(user)
        db.session.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    departments = Department.query.all()
    return render_template("register.html", departments=departments)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.user_id
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# =========================
# Routes: Dashboard & Visualization
# =========================

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()

    # Basic stats
    total_appointments = Appointment.query.count()
    my_appointments = 0

    if user.role == "student":
        my_appointments = Appointment.query.filter_by(student_id=user.user_id).count()
    elif user.role == "faculty":
        my_appointments = Appointment.query.filter_by(faculty_id=user.user_id).count()
    else:  # admin sees all
        my_appointments = total_appointments

    # Visualization: appointments per department
    dept_counts = (
        db.session.query(Department.department_name, db.func.count(Appointment.appointment_id))
        .join(User, User.department_id == Department.department_id)
        .join(Appointment, Appointment.faculty_id == User.user_id)
        .group_by(Department.department_name)
        .all()
    )

    labels = [name for name, _ in dept_counts]
    values = [count for _, count in dept_counts]

    return render_template(
        "dashboard.html",
        user=user,
        total_appointments=total_appointments,
        my_appointments=my_appointments,
        chart_labels=labels,
        chart_values=values
    )


# =========================
# Routes: Appointments (CRUD)
# =========================

@app.route("/appointments")
@login_required
def appointments():
    user = current_user()
    if user.role == "student":
        appts = Appointment.query.filter_by(student_id=user.user_id).all()
    elif user.role == "faculty":
        appts = Appointment.query.filter_by(faculty_id=user.user_id).all()
    else:  # admin
        appts = Appointment.query.all()

    return render_template("appointments.html", appointments=appts, user=user)


@app.route("/appointments/new", methods=["GET", "POST"])
@login_required
def new_appointment():
    user = current_user()
    if user.role != "student":
        flash("Only students can create appointments in this demo.", "warning")
        return redirect(url_for("appointments"))

    if request.method == "POST":
        faculty_id = int(request.form["faculty_id"])
        appointment_date = request.form["appointment_date"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        purpose = request.form["purpose"]

        appt = Appointment(
            student_id=user.user_id,
            faculty_id=faculty_id,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            purpose=purpose,
            status="scheduled"
        )
        db.session.add(appt)
        db.session.commit()

        # create a basic notification
        notif = Notification(
            appointment_id=appt.appointment_id,
            message=f"New appointment on {appointment_date} at {start_time}",
            sent_status="pending"
        )
        db.session.add(notif)
        db.session.commit()

        flash("Appointment created.", "success")
        return redirect(url_for("appointments"))

    # faculty list for dropdown
    faculty_members = User.query.filter_by(role="faculty").all()
    return render_template("new_appointment.html", faculty_members=faculty_members)


@app.route("/appointments/cancel/<int:appointment_id>")
@login_required
def cancel_appointment(appointment_id):
    user = current_user()
    appt = Appointment.query.get_or_404(appointment_id)

    # Simple authorization check
    if user.role == "student" and appt.student_id != user.user_id:
        flash("You cannot cancel others' appointments.", "danger")
        return redirect(url_for("appointments"))
    if user.role == "faculty" and appt.faculty_id != user.user_id:
        flash("You cannot cancel others' appointments.", "danger")
        return redirect(url_for("appointments"))

    appt.status = "cancelled"
    db.session.commit()
    flash("Appointment cancelled.", "info")
    return redirect(url_for("appointments"))


# =========================
# Routes: Availability (basic CRUD)
# =========================

@app.route("/availability", methods=["GET", "POST"])
@login_required
def availability():
    user = current_user()
    if user.role != "faculty":
        flash("Only faculty can manage availability.", "warning")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        day_of_week = request.form["day_of_week"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]

        slot = Availability(
            faculty_id=user.user_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            is_available=True
        )
        db.session.add(slot)
        db.session.commit()
        flash("Availability slot added.", "success")

    slots = Availability.query.filter_by(faculty_id=user.user_id).all()
    return render_template("availability.html", slots=slots)


# =========================
# Routes: Departments (admin)
# =========================

@app.route("/departments", methods=["GET", "POST"])
@login_required
def departments():
    user = current_user()
    if user.role != "admin":
        flash("Only admin can manage departments.", "warning")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form["department_name"]
        building = request.form["building"]
        phone = request.form["phone"]

        dept = Department(department_name=name, building=building, phone=phone)
        db.session.add(dept)
        db.session.commit()
        flash("Department added.", "success")

    depts = Department.query.all()
    return render_template("departments.html", departments=depts)


# =========================
# CLI Helper to initialize DB
# =========================

@app.cli.command("init-db")
def init_db():
    """Initialize database and add sample data."""
    db.drop_all()
    db.create_all()

    # Sample departments
    cs = Department(
        department_name="Computer Science",
        building="Ahlberg Hall",
        phone="316-978-3000"
    )
    math = Department(
        department_name="Mathematics",
        building="Jabara Hall",
        phone="316-978-3160"
    )
    ee = Department(
        department_name="Electrical Engineering",
        building="Wallace Hall",
        phone="316-978-3400"
    )

    db.session.add_all([cs, math, ee])
    db.session.commit()

    # Admin
    admin = User(
        name="Admin User",
        email="admin@university.edu",
        role="admin",
        department_id=cs.department_id,
        password_hash=generate_password_hash("admin123")
    )

    # Faculty members
    faculty1 = User(
        name="Dr. Johnson (Computer Science)",
        email="johnson@wsu.edu",
        role="faculty",
        department_id=cs.department_id,
        password_hash=generate_password_hash("demo-johnson")
    )

    faculty2 = User(
        name="Dr. Emily Lee (Mathematics)",
        email="elee@wsu.edu",
        role="faculty",
        department_id=math.department_id,
        password_hash=generate_password_hash("demo-lee")
    )

    faculty3 = User(
        name="Dr. Patel (Electrical Engineering)",
        email="patel@wsu.edu",
        role="faculty",
        department_id=ee.department_id,
        password_hash=generate_password_hash("demo-patel")
    )

    # Student
    student = User(
        name="John Student",
        email="student@university.edu",
        role="student",
        department_id=cs.department_id,
        password_hash=generate_password_hash("student123")
    )

    db.session.add_all([admin, faculty1, faculty2, faculty3, student])
    db.session.commit()

    print("Database initialized with sample data.")


# =========================
# Run the app (port 5001)
# =========================

if __name__ == "__main__":
    app.run(debug=True, port=5001)

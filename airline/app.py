from flask import Flask, render_template, request, session, redirect, url_for, flash
from datetime import datetime
import mysql.connector
import re
import db_utils

# App initlization:
# ======================================================================================
app = Flask(__name__)

app.secret_key = 'some key that you will never guess'
conn = mysql.connector.connect(host='localhost',
                               user='root',
                               password='',
                               database='air_ticket_reservation_system')
app.config["SEND-FILE_MAX_AGE_DEFAULT"] = 1
EMAIL_REGEX = '^(\w|\.|\_|\-)+[@](\w|\_|\-|\.)+[.]\w{2,3}$'


# ======================================================================================


# Utility functions: 
# ======================================================================================
def is_match(stdin, pattern):
    return re.search(pattern, stdin) is not None


def logged_in_redirect():
    if session["type"] == "airline_staff":
        return redirect(url_for())
    else:
        return redirect(url_for("search_flight"))


# ======================================================================================


# App initialization:
@app.route('/')
def home():
    if session.get("logged_in", False):
        return logged_in_redirect()
    return redirect(url_for("search_flight"))


# Public view functions:
# ======================================================================================
@app.route('/SearchFlight', methods=['GET', 'POST'])
def search_flight():
    if session.get("logged_in", False) and session.get("type") == "airline_staff":
        return redirect(url_for())

    # results for autocomplete in the client side
    airport_city = db_utils.get_airport_and_city(conn)
    flights = []
    # print(airport_city)

    if request.method == "GET":
        return render_template("public_view.html", airport_city=airport_city, flights=flights)
    elif request.method == "POST":
        source = request.form['depart']
        destination = request.form['arrive']
        date = request.form['date']

        source = source.split(" - ")
        destination = destination.split(" - ")
        # print(source, destination, date)

        src_city = source[0]
        dst_city = destination[0]
        src_airport = ""
        dst_airport = ""
        if len(source) == 2:
            src_airport = source[1]
        if len(destination) == 2:
            dst_airport = destination[1]

        # flights is a nested list, with its sublist:
        # [airline_name, flight_num, depart_airport, depart_city, depart_time,
        #  arrive_airport, arrive_city, arrive_time, price, status, plane_id]
        flights = db_utils.get_flights_by_location(conn, date, src_city, dst_city, src_airport, dst_airport)
        if not flights:
            flights = ["No flights"]
        # print(flights)
        return render_template("public_view.html", airport_city=airport_city, flights=flights)


@app.route('/CheckStatus', methods=['GET', 'POST'])
def check_flight_status():
    if session.get("logged_in", False) and session.get("type") == "airline_staff":
        return redirect(url_for())

    if request.method == "GET":
        today = datetime.now().strftime("%Y-%m-%d")
        #today = "2021-05-01"
        recent_flight_status = db_utils.get_flight_status(conn, "", today, "")
        print(recent_flight_status)
        return render_template("check_status.html", status_result=recent_flight_status)
    elif request.method == "POST":
        flight_num = request.form.get("flight_num", "")
        departure_date = request.form.get("departure_date", "")
        arrival_date = request.form.get("arrival_date", "")

        flight_status_ans = db_utils.get_flight_status(conn, flight_num, departure_date, arrival_date)
        if not flight_status_ans:
            flight_status_ans = ["No such a flight at the given time!"]
        print(flight_status_ans)
        return render_template("check_status.html", status_result=flight_status_ans)


@app.route('/ViewMyFlights', methods=["GET"])
def view_my_flights():
    if not session.get("logged_in", False):
        return redirect(url_for("home"))

    identity = session.get("type", "guest")
    if request.method == "GET":
        upcoming_flights = db_utils.get_upcoming_flights(conn, identity, session["email"])
        print(upcoming_flights)
        return render_template("view_my_flights.html", flights=upcoming_flights)


@app.route('/purchase/<airline_name>/<flight_num>', methods=["GET"])
def purchase(airline_name, flight_num):
    if not session.get("logged_in", False):
        return redirect(url_for("home"))
    elif session.get("type", "guest") == "airline_staff":
        return redirect(url_for())

    if request.method == "GET":
        return redirect(url_for("purchase_confirm", airline_name=airline_name, flight_num=flight_num))


@app.route('/purchase/confirm/<airline_name>/<flight_num>', methods=["GET", "POST"])
def purchase_confirm(airline_name, flight_num):
    if not session.get("logged_in", False):
        return redirect(url_for("home"))
    elif session.get("type", "guest") == "airline_staff":
        return redirect(url_for())

    if request.method == "GET":
        # print(airline_name, flight_num)
        return render_template("purchase_confirm.html", email=session["email"], airline_name=airline_name, flight_num=flight_num)
    elif request.method == "POST":
        # print(airline_name, flight_num)
        identity = session["type"]
        if identity == "customer":
            customer_email = session["email"]
            agent_email = ""
        else:
            customer_email = request.form.get("customer_email")
            agent_email = session["email"]

        if db_utils.purchase_ticket(conn, identity, customer_email, agent_email, airline_name, flight_num):
            print("purchase success")
            return redirect(url_for("view_my_flights"))
        else:
            print("purchase fail")
            error = "No ticket! This flight is full!"
            return render_template("purchase_confirm.html", email=session["email"], airline_name=airline_name, flight_num=flight_num, error=error)


@app.route('/TrackMySpending', methods=["GET"])
def track_my_spending():
    if not session.get("logged_in", False):
        flash("Don't cheat! Login first!")
        return redirect(url_for("home"))
    elif session.get("type", "guest") != "customer":
        flash("You don't have the authority to do so!")
        return redirect(url_for("home"))

    if request.method == "GET":
        # List of lists: [[purchase_date, price], .........]
        my_spendings = db_utils.get_my_spendings(conn, email=session["email"])
        print(my_spendings)
        return render_template("track_my_spending.html", my_spendings=my_spendings)


@app.route('/ViewMyCommission', methods=["GET"])
def view_my_commission():
    if not session.get("logged_in", False):
        flash("Don't cheat! Login first!")
        return redirect(url_for("home"))
    elif session.get("type", "guest") != "booking_agent":
        flash("You don't have the authority to do so!")
        return redirect(url_for("home"))

    if request.method == "GET":
        my_commission = db_utils.get_my_commission(conn, session["email"], "", "")
        print(my_commission)
        return render_template("ViewMyCommission.html", my_commission=my_commission)


@app.route('/ViewTopCustomers', methods=["GET"])
def view_top_customers():
    if not session.get("logged_in", False):
        flash("Don't cheat! Login first!")
        return redirect(url_for("home"))
    elif session.get("type", "guest") != "booking_agent":
        flash("You don't have the authority to do so!")
        return redirect(url_for("home"))

    if request.method == "GET":
        most_tickets, most_commission = db_utils.top_customers(conn, email=session["email"])
        print(most_tickets, most_commission)
        return render_template("ViewTopCustomers.html", most_tickets=most_tickets, most_commission=most_commission)


@app.route('/CreateNewFlights', methods=["GET", "POST"])
def create_new_flights():
    if not session.get("logged_in", False):
        flash("Don't cheat! Login first!")
        return redirect(url_for("home"))
    elif session.get("type", "guest") != "airline_staff":
        flash("You don't have the authority to do so!")
        return redirect(url_for("home"))

    if request.method == "GET":
        return render_template("CreateNewFlights.html", status=False, error="")
    elif request.method == "POST":
        info = {"airline_name": request.form["airline_name"],
                "flight_num": request.form["flight_num"],  # no repetitive check
                "departure_airport": request.form["departure_airport"],  # have check
                "departure_time": request.form["departure_time"],
                "arrival_airport": request.form["arrival_airport"],  # have check
                "arrival_time": request.form["arrival_time"],
                "price": request.form["price"],
                "status": request.form["status"],
                "plane_id": request.form["plane_id"],  # have check
                }
        status, error = db_utils.create_new_flight(conn, info)
        return render_template("CreateNewFlights.html", status=status, error=error)


@app.route('/ChangeFlightStatus', methods=["GET", "POST"])
def change_status_of_flight():
    if not session.get("logged_in", False):
        flash("Don't cheat! Login first!")
        return redirect(url_for("home"))
    elif session.get("type", "guest") != "airline_staff":
        flash("You don't have the authority to do so!")
        return redirect(url_for("home"))

    if request.method == "GET":
        return render_template("ChangeFlightStatus.html", status=False, error="")
    elif request.method == "POST":
        flight_num = request.form["flight_num"]
        new_status = request.form["status"]
        status, error = db_utils.change_flight_status(conn, flight_num, new_status)
        return render_template("ChangeFlightStatus.html", status=status, error=error)


@app.route('/AddAirplane', methods=["GET", "POST"])
def add_airplane():
    if not session.get("logged_in", False):
        flash("Don't cheat! Login first!")
        return redirect(url_for("home"))
    elif session.get("type", "guest") != "airline_staff":
        flash("You don't have the authority to do so!")
        return redirect(url_for("home"))

    if request.method == "GET":
        return render_template("AddAirplane.html", status=False, error="")
    elif request.method == "POST":
        airline_name = request.form["airline_name"]
        airplane_id = request.form["airplane_id"]
        seats = request.form["seats"]

        status, error = db_utils.add_airplane(conn, airline_name, airplane_id, seats)
        return render_template("AddAirplane.html", status=status, error=error)


@app.route('/AddAirport')
def add_airport():
    if not session.get("logged_in", False):
        flash("Don't cheat! Login first!")
        return redirect(url_for("home"))
    elif session.get("type", "guest") != "airline_staff":
        flash("You don't have the authority to do so!")
        return redirect(url_for("home"))

    if request.method == "GET":
        return render_template("AddAirport.html", status=False, error="")
    elif request.method == "POST":
        airport_name = request.form["airport_name"]
        airport_city = request.form["airport_city"]

        status, error = db_utils.add_airport(conn, airport_name, airport_city)
        return render_template("AddAirport.html", status=status, error=error)


@app.route('/ViewAllBookingAgent', methods=["GET"])
def view_all_booking_agent():
    if not session.get("logged_in", False):
        flash("Don't cheat! Login first!")
        return redirect(url_for("home"))
    elif session.get("type", "guest") != "airline_staff":
        flash("You don't have the authority to do so!")
        return redirect(url_for("home"))

    if request.method == "GET":
        top_five_tickets_past_month = db_utils.top_five_tickets_past_month(conn)

# ======================================================================================


# Login functions:
# ======================================================================================
@app.route('/login', methods=['GET'])
def login_general_page():
    if session.get("logged_in", False):
        return logged_in_redirect()
    return render_template("login_general.html")


# identity = customer/booking_agent/airline_staff
@app.route('/login/<string:identity>', methods=['GET', 'POST'])
def login_page(identity):
    if identity not in ["customer", "booking_agent", "airline_staff"]:
        return redirect(url_for("login_general_page"))
    elif session.get("logged_in", False):
        return logged_in_redirect()

    error = ""
    if request.method == "GET":
        return render_template("login_%s.html" % identity, error=error)
    elif request.method == "POST":
        email = request.form["username"]
        password = request.form["password"]
        # if not is_match(email, EMAIL_REGEX):
        #     error = "Email address invalid"
        #     return render_template("login_%s.html" % identity, error=error)
        if not db_utils.login_check(conn, email, password, identity):
            error = "Email address or password invalid"
            return render_template("login_%s.html" % identity, error=error)
        else:
            session["logged_in"] = True
            session["type"] = identity
            session["email"] = email
            if identity == "airline_staff":
                session["airline"] = db_utils.airline_staff_initialization(conn, email)
            return redirect(url_for("search_flight"))


# ======================================================================================


# Register functions:
# ======================================================================================
@app.route('/register', methods=['GET'])
def register_general_page():
    if session.get("logged_in", False):
        return logged_in_redirect()
    return render_template("register_general.html")


# identity = customer/booking_agent/airline_staff
@app.route('/register/<string:identity>', methods=['GET', 'POST'])
def register_page(identity):
    if identity not in ["customer", "booking_agent", "airline_staff"]:
        return redirect(url_for("register_general_page"))
    elif session.get("logged_in", False):
        return logged_in_redirect()
    else:
        error = ""
        if request.method == "GET":
            return render_template("register_%s.html" % identity, error=error)
        elif request.method == "POST":
            info = {"email": request.form.get("username"),
                    "password": request.form.get("password"),
                    "name": request.form.get("name"),
                    "first_name": request.form.get("first_name"),
                    "last_name": request.form.get("last_name"),
                    "building_number": request.form.get("building_number"),
                    "street": request.form.get("street"),
                    "city": request.form.get("city"),
                    "state": request.form.get("state"),
                    "phone_number": request.form.get("phone_number"),
                    "passport_number": request.form.get("passport_number"),
                    "passport_expiration": request.form.get("passport_expiration"),
                    "passport_country": request.form.get("passport_country"),
                    "date_of_birth": request.form.get("date_of_birth"),
                    "booking_agent_id": request.form.get("booking_agent_id"),
                    "airline_name": request.form.get("airline_name")
                    }
            if not is_match(info["email"], EMAIL_REGEX):
                error = "Email address invalid"
                return render_template("register_%s.html" % identity, error=error)

            status, error = db_utils.register_check(conn, info, identity)
            if not status:
                return render_template("register_%s.html" % identity, error=error)

            db_utils.register_to_database(conn, info, identity)
            session["logged_in"] = True
            session["type"] = identity
            session["email"] = info["email"]
            if identity == "airline_staff":
                session["airline"] = info["airline_name"]
            return redirect(url_for("search_flight"))


# ======================================================================================


# Logout function:
# ======================================================================================
@app.route('/logout')
def logout():
    if session.get("logged_in", False):
        session["logged_in"] = False
    return redirect(url_for("home"))


# ======================================================================================


# Error page:
# ======================================================================================
# @app.errorhandler(404)
# def not_found(e):
#     return render_template("not_found.html"), 404



# ======================================================================================

if __name__ == '__main__':
    app.run(host="127.0.0.1", port=5000, debug=True)

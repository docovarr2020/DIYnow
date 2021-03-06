from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir
import sqlite3
import hashlib
import subprocess
import json
from helpers import *
import os
import logging
import sys

# -----------------------------database creation--------------------------------
# https://docs.python.org/3.6/library/sqlite3.html#sqlite3.Connection
# create a Connection object that represents the database.
conn = sqlite3.connect("DIYnow.db")

# http://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
# https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.row_factory
# change the way rows are accessed, dictionary instead of tuple
conn.row_factory = sqlite3.Row

# creating a cursor object for executing SQL commands
c = conn.cursor()

# ---------------------------------flask setup----------------------------------
# configure application
app = Flask(__name__)

# ensure responses aren't cached
# CREDIT PSET7
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
# ---------------------------------END SETUP------------------------------------


@app.route("/home", methods=["GET", "POST"])
@login_required
def home():
    """Show new projects and allow user to add projects to their list"""

    # if user reached route via POST (as by adding a project or searching for one)
    if request.method == "POST":
        # chck if the POST came from the user adding a project
        if "DIYnow" in request.form:
            user_id = session["user_id"]

            # get which project the user selected
            project_url = request.form["DIYnow"]

            # open last list of projects in home menu, store in json format
            json_data=open("ProjectOut.json").read()
            projects = json.loads(json_data)

            # http://stackoverflow.com/questions/19794695/flask-python-buttons
            # find which project's button the user clicked, get appropriate info from it
            for project in projects:
                if project["url"] == project_url:
                    project_url = project["url"]
                    project_name = project["title"]
                    image_url = project["image_url"]

            # insert the new project into the portfolio table
            try:
                c.execute("INSERT INTO projects (id, project_url, project_name, image_url) VALUES(:id, :project_url, :project_name, :image_url)",
                                {"id" : user_id, "project_url" : project_url, "project_name" : project_name, "image_url" : image_url })
                conn.commit()
            # if inserting into SQL table failed
            except RuntimeError:
                flash("ERROR: updated too few or too many rows of projects")
                return render_template("home.html", projects = projects)

            # http://stackoverflow.com/questions/29312882/sqlite-preventing-duplicate-rows
            # if the user tried to add a project twice:
            # unique SQL database index (user_project) prevents duplicate addition of projects
            except sqlite3.IntegrityError:
                flash("You've already added that project!")
                return render_template("home.html", projects = projects)

            flash("Added!")
            return render_template("home.html", projects = projects)

        # user has entered a search string
        else:
            # if output file already contains projects, delete it and start again
            if (os.path.isfile("ProjectOut.json")):
                os.remove("ProjectOut.json")

            # call our scrapy search spider by its name, Search
            # see DIYnow/DIYnow/spiders/diyspider.py for the spider, class SearchSpider
            projectSpiderName = "Search"

            # http://stackoverflow.com/questions/15611605/how-to-pass-a-user-defined-argument-in-scrapy-spider
            # running spider in a subprocess, passing in the user's search term as category
            # see https://doc.scrapy.org/en/latest/topics/spiders.html, spider arguments section
            subprocess.check_output(["scrapy", "crawl", projectSpiderName, "-a", ("category=" + request.form.get("search")), "-o", "ProjectOut.json"])

            # load our newly scraped projects into ProjectOut json file
            json_data=open("ProjectOut.json").read()
            projects = json.loads(json_data)

            # pass those projects to be displayed by home.html with jinja
            return render_template("home.html", projects = projects)

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        if (os.path.isfile("ProjectOut.json")):
            os.remove("ProjectOut.json")

        # http://stackoverflow.com/questions/36384286/how-to-integrate-flask-scrapy
        # call our scrapy general spider by its name, Projects
        # see DIYnow/DIYnow/spiders/diyspider.py for the spider, class ProjectSpider
        projectSpiderName = "Projects"

        # running spider in a subprocess and loading scraped projects into json
        subprocess.check_output(["scrapy", "crawl", projectSpiderName, "-o", "ProjectOut.json"])
        json_data=open("ProjectOut.json").read()
        projects = json.loads(json_data)

        # pass those projects to be displayed by home.html with jinja
        return render_template("home.html", projects = projects)


# CREDIT PSET 7
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide username")
            return render_template("login.html")

        # ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password")
            return render_template("login.html")

        # query database for username
        c.execute("SELECT * FROM users WHERE username = :username", {"username":request.form.get("username")})
        rows = c.fetchall()

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            flash("Invalid username and/or password")
            return render_template("login.html")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("my_projects"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

# CREDIT PSET7
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # ensure username was submitted
        username = request.form.get("username")
        if not username:
            flash("Must provide username")
            return render_template("register.html")

        # ensure username is unique
        if c.execute("SELECT username FROM users WHERE username = :username", {"username" : username}).fetchall() != []:
            flash("Must provide unique username")
            return render_template("register.html")

        # ensure password was submitted
        password = request.form.get("password")
        if not password:
            flash("Must provide password")
            return render_template("register.html")

        # ensure password was confirmed correctly
        if request.form.get("confirm_password") != password:
           flash("Incorrect password confirmation")
           return render_template("register.html")

        # encrypt user's password and insert user info into users table
        try:
            c.execute("INSERT INTO users (username, hash) VALUES(:username, :hash_)",
                        {"username" : username, "hash_" : pwd_context.encrypt(password)})
            c.execute("SELECT id FROM users WHERE username = :username", {"username":request.form.get("username")})
            # store this user's id
            new_id = c.fetchone()
            # save the changes to the table
            conn.commit()

        # if inserting into SQL table failed
        except RuntimeError:
            flash("ERROR creating new user")
            return render_template("register.html")

        # remember which user has logged in, redirect to index page and welcome
        session["user_id"] = new_id["id"]

        flash("Registered!")
        return redirect(url_for("home"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

# CREDIT PSET7
@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def my_projects():
    """Get all of user's favorited projects"""

    user_id = session["user_id"]
    # if user reached route via POST (as by deleting a project)
    if request.method == "POST":

        # get which project the user selected
        project_url = request.form["Delete"]

        # select all current user projects
        c.execute("SELECT project_url, project_name, image_url FROM projects WHERE id = :user_id", {"user_id" : user_id})
        all_projects = c.fetchall()

        # parse user projects, find the one with the url matching the deleted project
        for project in all_projects:
            if project["project_url"] == project_url:
                project_url = project["project_url"]

        # delete the project from the database
        try:
            c.execute("DELETE FROM projects WHERE id = :user_id AND project_url = :project_url", {"user_id" : user_id, "project_url" : project_url})
            # commit the changes
            conn.commit()

        # if deletion failed
        except RuntimeError:
            flash("ERROR: Deleting project")
            return render_template("my_projects.html", projects = all_projects)

        flash("Deleted!")

        # refresh project page, showing the user a successful deletion
        c.execute("SELECT project_url, project_name, image_url FROM projects WHERE id = :user_id", {"user_id" : user_id})
        all_projects = c.fetchall()
        return render_template("my_projects.html", projects = all_projects)

    # else if user reached route via GET (just browsisng)
    else:
        # select all of user's current projects, and display them
        c.execute("SELECT project_url, project_name, image_url FROM projects WHERE id = :user_id", {"user_id" : user_id})
        all_projects = c.fetchall()

        return render_template("my_projects.html", projects = all_projects)
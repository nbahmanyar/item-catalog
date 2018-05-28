#! /usr/bin/env python3

from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from n_database_setup import Base, Project, Item, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
from flask_oauthlib.client import OAuth


# Some code adapted from this flask-oauth example https://github.com/lepture/flask-oauthlib/blob/master/example/google.py


app = Flask(__name__)

engine = create_engine('sqlite:///projectplanner.db',
                       connect_args={'check_same_thread': False},
                       poolclass=StaticPool, echo=True)
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Configure the OAUTH parameters
app.config['GOOGLE_ID'] = "825349126192-ujidiia6lfn8vok2o1ep879r37qlrumv.apps.googleusercontent.com"
app.config['GOOGLE_SECRET'] = "mxi8yfVHvvtTDR8fSdFGesAm"
app.debug = True
app.secret_key = 'development'
oauth = OAuth(app)

google = oauth.remote_app(
    'google',
    consumer_key=app.config.get('GOOGLE_ID'),
    consumer_secret=app.config.get('GOOGLE_SECRET'),
    request_token_params={
        'scope': 'email'
    },
    base_url='https://www.googleapis.com/oauth2/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
)

# Login
@app.route('/login')
def login():
    return google.authorize(callback=url_for('authorized', _external=True))


@app.route('/logout')
def logout():
    google_token = login_session.pop('google_token', None)
    url = 'https://accounts.google.com/o/oauth2/revoke?token={}'.format(google_token)
    result = requests.get(url)

    del login_session['username']
    del login_session['email']
    return redirect(url_for('index'))


@app.route('/login/authorized')
def authorized():
    resp = google.authorized_response()
    if resp is None:
        return 'Access denied: reason=%s error=%s' % (
            request.args['error_reason'],
            request.args['error_description']
        )
    login_session['google_token'] = (resp['access_token'], '')
    me = google.get('userinfo')
    data = me.data
    login_session['username'] = data['name']
    login_session['email'] = data['email']

    # Create user if doesn't exist
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id


    return redirect(url_for('index'))
    # return jsonify({"data": me.data})
    # return jsonify({"login session": login_session})


@google.tokengetter
def get_google_oauth_token():
    return login_session.get('google_token')


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# Build out the JSON API endpoints
@app.route('/project/<int:project_id>/items/JSON')
def ProjectJSON(project_id):
    # project = session.query(Project).filter_by(id=project_id).one()
    items = session.query(Item).filter_by(
        project_id=project_id).all()
    return jsonify(Items=[i.serialize for i in items])


@app.route('/project/<int:project_id>/items/<int:item_id>/JSON')
def ProjectItemJSON(project_id, item_id):
    Project_Item = session.query(Item).filter_by(id=item_id).one()
    return jsonify(Project_Item=Project_Item.serialize)


@app.route('/project/JSON')
def allProjectsJSON():
    projects = session.query(Project).all()
    return jsonify(projects=[r.serialize for r in projects])


# Show all projects
@app.route('/')
@app.route('/project/')
def index():
    projects = session.query(Project).all()
    if 'username' not in login_session:
        # return jsonify(projects=[r.serialize for r in projects])
        return render_template('catalog-main-public.html', projects={})
        # return render_template('restaurants.html', restaurants={})
    else:
        return render_template('catalog-main.html', projects=projects)
        # return render_template('restaurants.html', restaurants=restaurants)




# Create a new project
@app.route('/project/new/', methods=['GET', 'POST'])
def newRestaurant():
    if 'username' not in login_session:
        return redirect('/')
    if request.method == 'POST':
        newProject = Project(name=request.form['name'])
        session.add(newProject)
        session.commit()
        return redirect(url_for('index'))
    else:
        # return "This page will be for making a new restaurant"
        return render_template('newProject.html')



# Edit a project
@app.route('/project/<int:project_id>/edit/', methods=['GET', 'POST'])
def editProject(project_id):
    if 'username' not in login_session:
        return redirect('/')
    editedProject = session.query(
        Project).filter_by(id=project_id).one()
    if request.method == 'POST':
        if request.form['name']:
            editedProject.name = request.form['name']
            return redirect(url_for('index'))
    else:
        return render_template(
            'editProject.html', project=editedProject)


# Edit a project's name
@app.route('/project/<int:project_id>/edit-name/', methods=['GET', 'POST'])
def editProjectName(project_id):
    if 'username' not in login_session:
        return redirect('/')
    editedProject = session.query(
        Project).filter_by(id=project_id).one()
    if request.method == 'POST':
        if request.form['name']:
            editedProject.name = request.form['name']
            return redirect(url_for('index'))
    else:
        return render_template(
            'editProjectName.html', project=editedProject)



# Delete a project
@app.route('/project/<int:project_id>/delete/', methods=['GET', 'POST'])
def deleteProject(project_id):
    if 'username' not in login_session:
        return redirect('/')
    projectToDelete = session.query(Project).filter_by(id=project_id).one()
    if request.method == 'POST':
        session.delete(projectToDelete)
        session.commit()
        return redirect(
            url_for('index', project_id=project_id))
    else:
        return render_template(
            'deleteProject.html', project=projectToDelete)


# # Show a restaproject
# @app.route('/project/<int:project_id>/')
# @app.route('/project/<int:project_id>/items/')
# def showMenu(project_id):
#     restaurant = session.query(Restaurant).filter_by(id=project_id).one()
#     items = session.query(MenuItem).filter_by(
#         project_id=project_id).all()
#     return render_template('menu.html', items=items, restaurant=restaurant)
#     # return 'This page is the menu for restaurant %s' % project_id

# # Create a new menu item


# @app.route(
#     '/project/<int:project_id>/items/new/', methods=['GET', 'POST'])
# def newMenuItem(project_id):
#     if request.method == 'POST':
#         newItem = MenuItem(name=request.form['name'], description=request.form[
#                            'description'], price=request.form['price'], course=request.form['course'], project_id=project_id)
#         session.add(newItem)
#         session.commit()

#         return redirect(url_for('showMenu', project_id=project_id))
#     else:
#         return render_template('newmenuitem.html', project_id=project_id)

#     return render_template('newMenuItem.html', restaurant=restaurant)
#     # return 'This page is for making a new menu item for restaurant %s'
#     # %project_id

# # Edit a menu item


# @app.route('/project/<int:project_id>/items/<int:item_id>/edit',
#            methods=['GET', 'Project_Item'])
# def editMenuItem(oject_id, menu_id):item editedItem = session.query(MenuItem).filter_by(id=menu_id).one()
#     if request.method == 'POST':
#         if request.form['name']:
#             editedItem.name = request.form['name']
#         if request.form['description']:
#             editedItem.description = request.form['name']
#         if request.form['price']:
#             editedItem.price = request.form['price']
#         if request.form['course']:
#             editedItem.course = request.form['course']
#         session.add(editedItem)
#         session.commit()
#         return redirect(url_for('showMenu', project_id=project_id))
#     else:

#         return render_template(
#             'editmenuitem.html', project_id=project_id, menu_id=menu_id, item=editedItem)

#     # return 'This page is for editing menu item %s' % menu_id

# # Delete a menu item


# @app.route('/project/<int:project_id>/items/<int:item_id>/delete',
#            methods=['GET', 'Project_Item'])
# def deleteMenuItem(oject_id, menu_id):item itemToDelete = session.query(MenuItem).filter_by(id=menu_id).one()
#     if request.method == 'POST':
#         session.delete(itemToDelete)
#         session.commit()
#         return redirect(url_for('showMenu', project_id=project_id))
#     else:
#         return render_template('deleteMenuItem.html', item=itemToDelete)
#     # return "This page is for deleting menu item %s" % menu_id


if __name__ == '__main__':
    app.debug = True
    app.run(host='localhost', port=5566)

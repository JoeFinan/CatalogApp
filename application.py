from flask import Flask, render_template, request, redirect,jsonify, url_for, flash
app = Flask(__name__)

from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Band, Song, User

#NEW IMPORTS
from flask import session as login_session
import random, string

#IMPORTS to store login credentials
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import  make_response
import requests

CLIENT_ID = json.loads(
    open('client_secrets.json','r').read())['web']['client_id']

#Connect to Database and create database session
engine = create_engine('sqlite:///bands.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

#global objects to use throughout the app
allBands = session.query(Band).order_by(asc(Band.name))
allUsers = session.query(User).order_by(asc(User.name))

@app.route('/gconnect', methods=['POST'])
def gconnect():
    code = request.data
    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s' % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Verify that the access token is used for the intended user
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        #return response
    if result['issued_to'] != CLIENT_ID:
        response = make_response(json.dumps("Token's client ID doesn't match app's."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    #Check to see if user is already logged in
    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        flash('User already Signed in!')
        output = '<h1>Welcome, '
        output += login_session['username']
        output += '!</h1>'
        return output
    
    #Store the access token in the session for later use
    login_session['credentials'] = credentials
    login_session['gplus_id'] = gplus_id
    
    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)
    
    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    
    # see if user exists, if it doesn't make a new one
    user_id = getUserID(login_session['email'])
    if(not user_id):
        print('user created')
        user_id = createUser(login_session)
    else:
        print('user exists!')
    login_session['user_id'] = user_id
    
    #setting user_admin in session
    login_session['user_admin'] = getUserInfo(user_id).user_admin
    
    output = '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    flash("You are now logged in as %s" % login_session['username'])
    return output
    
#DISCONNECT - Revoke a current user's token and reset their login_session
@app.route("/gdisconnect")
def gdisconnect():
    #Only disconnect a connected user
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    #Execute HTTP GET request to revoke current token
    access_token = credentials.access_token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    
    if result['status'] == '200':
        # Reset the user's session.
        del login_session['credentials']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_admin']
        
        flash('Successfully logged out!')
        return redirect(url_for('showBands'))
    else:
        # For whatever reason, the given token was invalid
        response = make_response(json.dumps('Failed to revoke token for given user.',400))
        response.headers['Content-Type'] = 'application/json'
        return response

#JSON API to view all bands
@app.route('/bands/JSON')
def bandsJSON():
    return jsonify(Bands=[i.serialize for i in allBands])
    
#JSON API to view all bands and songs
@app.route('/bandsWithSongs/JSON')
def bandsWithSongsJSON():
    songs = session.query(Song).all()
    return jsonify(Bands=[i.serialize for i in allBands], 
    Songs=[i.serialize for i in songs])
    
#JSON API to view a band's songs
@app.route('/bands/<int:band_id>/songs/JSON')
def bandSongsJSON(band_id):
    band = allBands.filter_by(id = band_id).one()
    songs = session.query(Song).filter_by(band_id = band_id).all()
    return jsonify(Songs=[i.serialize for i in songs])

#JSON API to view all songs
@app.route('/songs/JSON')
def songsJSON():
    songs = session.query(Song).all()
    return jsonify(Songs=[i.serialize for i in songs])
    
#JSON API to view all users
@app.route('/users/JSON')
def usersJSON():
    return jsonify(Users=[i.serialize for i in allUsers])
    
#Show all bands
@app.route('/')
@app.route('/bands/')
def showBands():
    loggedInUser = ''
    if 'username' in login_session:
        loggedInUser = getUserInfo(login_session['user_id'])
    return render_template('bands.html', allBands=allBands,
    loggedInUser=loggedInUser)
    
#Show user page
@app.route('/users/')
def showUsers():
    # must be logged in to continue
    if 'username' not in login_session:
        flash('You have to log in to view users!')
        return redirect(url_for('showBands'))
    loggedInUser = getUserInfo(login_session['user_id'])
    # must have admin rights to continue
    if loggedInUser.user_admin is False:
        flash('You have to have admin permissions view users!')
        return redirect(url_for('showBands'))
    return render_template('users.html', allUsers=allUsers, loggedInUser=loggedInUser)
    
#Show user page with a selected user
@app.route('/users/<int:user_id>/')
def showUser(user_id):
    # must be logged in to continue
    if 'username' not in login_session:
        flash('You have to log in to view users!')
        return redirect(url_for('showBands'))
    loggedInUser = getUserInfo(login_session['user_id'])
    # must have admin rights to continue
    if loggedInUser.user_admin is False:
        flash('You have to have admin permissions view users!')
        return redirect(url_for('showBands'))
    selectedUser = allUsers.filter_by(id = user_id).one()
    return render_template('users.html', allUsers=allUsers, selectedUser=selectedUser, loggedInUser=loggedInUser)

#Delete a user
@app.route('/users/delete/<int:user_id>',methods=['GET','POST'])
def deleteUser(user_id):
    # must be logged in to continue
    if 'username' not in login_session:
        flash('You have to log in to delete a user!')
        return redirect(url_for('showUsers'))
    loggedInUser = getUserInfo(login_session['user_id'])
    # must have admin rights to continue
    if loggedInUser.user_admin is False:
        flash('You have to have admin permissions delete users!')
        return redirect(url_for('showBands'))
    userToDelete = allUsers.filter_by(id = user_id).one()
    if request.method == 'POST':
        #delete user
        session.delete(userToDelete)
        session.commit()
        
        #delete bands created by that user
        session.query(Band).filter_by(user_id = user_id).delete()
        session.commit()
        
        #delete songs created by that user
        session.query(Song).filter_by(user_id = user_id).delete()
        session.commit()
        
        flash('User Successfully Deleted!')
        return redirect(url_for('showUsers'))
    else:
        return render_template('deleteUser.html', user=userToDelete, loggedInUser=loggedInUser)

#Add a users admin permissions
@app.route('/users/addAdmin/<int:user_id>')
def addAdminPermissions(user_id):
    # must be logged in to continue
    if 'username' not in login_session:
        flash('You have to log in to update permissions!')
        return redirect(url_for('showUsers'))
    # must have admin rights to continue
    if login_session['user_id'] == False:
        flash('You have to have admin permissions to update permissions!')
        return redirect(url_for('showUsers'))
    userToUpdate = allUsers.filter_by(id = user_id).one()
    #add permissions
    userToUpdate.user_admin = True
    session.add(userToUpdate)
    session.commit()
        
    flash('Permissions Successfully Added!')
    return redirect('/users/%s' % user_id)
    
#Delete a users admin permissions
@app.route('/users/deleteAdmin/<int:user_id>')
def delAdminPermissions(user_id):
    # must be logged in to continue
    if 'username' not in login_session:
        flash('You have to log in to update permissions!')
        return redirect(url_for('showUsers'))
    # must have admin rights to continue
    if login_session['user_id'] == False:
        flash('You have to have admin permissions to update permissions!')
        return redirect(url_for('showUsers'))
    userToUpdate = allUsers.filter_by(id = user_id).one()
    #remove permissions
    userToUpdate.user_admin = False
    session.add(userToUpdate)
    session.commit()

    flash('Permissions Successfully Removed!')
    return redirect('/users/%s' % user_id)

#Show band songs
@app.route('/bands/<int:band_id>/')
@app.route('/bands/<int:band_id>/songs/')
def showSongs(band_id):
    loggedInUser = ''
    if 'username' in login_session:
        loggedInUser = getUserInfo(login_session['user_id'])
    selectedBand = allBands.filter_by(id = band_id).one()
    songs = session.query(Song).filter_by(band_id = band_id).all()
    return render_template('bands.html', allBands=allBands, selectedBand=selectedBand, songs=songs, loggedInUser=loggedInUser)
    
#Add new band
@app.route('/bands/new/',methods=['GET','POST'])
def newBand():
    # must be logged in to continue
    if 'username' not in login_session:
        flash('You have to log in to add a band!')
        return redirect(url_for('showBands'))
    if request.method == 'POST':
        newBand = Band(name = request.form['name'], user_id=login_session['user_id'])
        session.add(newBand)
        session.commit()
        flash('New Band %s Successfully Added' % (newBand.name))
        return redirect(url_for('showBands'))
    else:
        loggedInUser = getUserInfo(login_session['user_id'])
        return render_template('newBand.html', loggedInUser=loggedInUser)
        
#Delete Band and songs of that band
@app.route('/bands/delete/<int:band_id>',methods=['GET','POST'])
def deleteBand(band_id):
    # must be logged in to continue
    if 'username' not in login_session:
        flash('You have to log in to delete a band!')
        return redirect(url_for('showBands'))
    loggedInUser = getUserInfo(login_session['user_id'])
    bandToDelete = allBands.filter_by(id = band_id).one()
    # must be the band creator to continue
    if loggedInUser.id != bandToDelete.user_id:
        flash('You have to be the creator of a band to delete the band!')
        return redirect(url_for('showBands'))
    if request.method == 'POST':
        #delete band
        session.delete(bandToDelete)
        session.commit()
        
        #delete songs by that band
        session.query(Song).filter_by(band_id = band_id).delete()
        session.commit()
        
        flash('Band Successfully Deleted!')
        return redirect(url_for('showBands'))
    else:
        return render_template('delete.html', whatToDelete=bandToDelete.name, band=bandToDelete, loggedInUser=loggedInUser)

#Add new song
@app.route('/bands/<int:band_id>/songs/new',methods=['GET','POST'])
def newSong(band_id):
    # must be logged in to continue
    if 'username' not in login_session:
        flash('You have to log in to add a song!')
        return redirect(url_for('showBands'))
    loggedInUser = getUserInfo(login_session['user_id'])
    band = allBands.filter_by(id = band_id).one()
    # must be the band creator to continue
    if loggedInUser.id != band.user_id:
        flash('You have to be the creator of a band to add a song!')
        return redirect(url_for('showBands'))
    if request.method == 'POST':
        newSong = Song(band_id=band_id, title = request.form['title'], description = request.form['description'], user_id=loggedInUser.id)
        session.add(newSong)
        session.commit()
        flash('New Song %s Successfully Added' % (newSong.title))
        return redirect(url_for('showSongs',band_id=band_id))
    else:    
        return render_template('newSong.html',band=band,loggedInUser=loggedInUser)
        
#Delete a song
@app.route('/bands/songs/<int:song_id>/delete',methods=['GET','POST'])
def deleteSong(song_id):
    # must be logged in to continue
    if 'username' not in login_session:
        flash('You have to log in to delete a song!')
        return redirect(url_for('showBands'))
    loggedInUser = getUserInfo(login_session['user_id'])
    songToDelete = session.query(Song).filter_by(id = song_id).one()
    # must be the song creator to continue
    if loggedInUser.id != songToDelete.user_id:
        flash('You have to be the creator of the song to delete!')
        return redirect(url_for('showBands'))
    if request.method == 'POST':
        #delete song
        session.delete(songToDelete)
        session.commit()
                
        flash('Song Successfully Deleted!')
        return redirect(url_for('showSongs',band_id=songToDelete.band_id))
    else:
        band = allBands.filter_by(id = songToDelete.band_id).one()
        return render_template('delete.html', whatToDelete=songToDelete.title, 
        band=band, loggedInUser=loggedInUser)
        
#Edit a song
@app.route('/bands/<int:band_id>/songs/<int:song_id>/edit',methods=['GET','POST'])
def editSong(band_id,song_id):
    # must be logged in to continue
    if 'username' not in login_session:
        flash('You have to log in to edit a song!')
        return redirect(url_for('showBands'))
    loggedInUser = getUserInfo(login_session['user_id'])
    songToEdit = session.query(Song).filter_by(id = song_id).one()
    # must be the song creator to continue
    if loggedInUser.id != songToEdit.user_id:
        flash('You have to be the creator of the song to edit!')
        return redirect(url_for('showBands'))
    if request.method == 'POST':
        if request.form['title']:
            songToEdit.title = request.form['title']
        if request.form['description']:
            songToEdit.description = request.form['description']
        session.add(songToEdit)
        session.commit() 
        flash('Song Successfully Updated')
        return redirect(url_for('showSongs',band_id=songToEdit.band_id))
    else:
        band = allBands.filter_by(id = band_id).one()
        return render_template('editSong.html', song=songToEdit, band=band, 
        loggedInUser=loggedInUser)

# Helper function to get user_id by email        
def getUserID(email):
    try:
        user = session.query(User).filter_by(email = email).one()
        return user.id
    except:
        return None

# Helper function to get user object
def getUserInfo(user_id):
    user = session.query(User).filter_by(id = user_id).one()
    return user 

# Helper function to create a new user
def createUser(login_session):
    # all users are created with user_admin permissions by default
    user_admin = True
    newUser = User(name = login_session['username'], email = login_session['email'], picture = login_session['picture'], user_admin = user_admin)
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email = login_session['email']).one()
    return user.id
        
if __name__ == '__main__':
  app.secret_key = 'super_secret_key'
  app.debug = True
  app.run(host = '0.0.0.0', port = 5000)
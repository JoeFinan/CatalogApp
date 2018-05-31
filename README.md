# Joe Finan: Catalog Project
This project contains a website with a list of bands and their songs. This site implements google authentication.

### Python Version
The application code was developed using Python 2.7

### Project Set-Up
   1. To run the code you must have python installed. You can [download Python by clicking here](https://www.python.org/downloads/). 
   2. Download and unzip the project code from the zip file submitted.

### How to run the code
   1. Open a Unix-like terminal (e.g. Git Bash for Windows, Terminal for Mac), and navigate to the project folder
   2. Type `python application.py` in the terminal window
   3. Open a browser and navigate to 'http://localhost:5000/bands/'
   
### A few things to note.
   1. The database will already have 1 User and 2 Bands with 2 Songs each.
   2. Any user can view a band and their songs just by clicking on the name of the band in the navigation menu.
    * This can be done without even logging in
   3. A user must be logged in through google oauth to create/update/delete bands or songs
    * Any user can create a band and songs for that band
    * A user must be the creator of a band to add a song for that band or to delete that band and it's songs
    * A user must be the creator of a song to update/delete that song
   3. I have also included a User Admin Module, all new users have user_admin permissions by default
    * A user admin can view user profile (name, user_id, email, profile picture, user_admin)
    * A user admin can delete users and all the bands & songs that user created
    * A user admin can also add/remove admin permissions for outher users
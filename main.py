import flask
from flask import render_template
from flask import request
from flask import url_for
from flask import jsonify # For AJAX transactions
import uuid

import json
import logging

# Date handling 
import arrow # Replacement for datetime, based on moment.js
import datetime # But we still need time
from dateutil import tz  # For interpreting local times


# OAuth2  - Google library implementation for convenience
from oauth2client import client
import httplib2   # used in oauth2 flow

# Google API for services 
from apiclient import discovery

# Module to handle busy/free time scheduling
from agenda import *

# Favicon rendering
import os

###
# Globals
###
import CONFIG
app = flask.Flask(__name__)

SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = CONFIG.GOOGLE_LICENSE_KEY  ## You'll need this
APPLICATION_NAME = 'MeetMe class project'

#############################
#
#  Pages (routed from URLs)
#
#############################

@app.route("/")
@app.route("/index")
def index():
  app.logger.debug("Entering index")
  return render_template('index.html')

@app.route("/choose")
def choose():
    ## We'll need authorization to list calendars 
    ## I wanted to put what follows into a function, but had
    ## to pull it back here because the redirect has to be a
    ## 'return' 
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
      app.logger.debug("Redirecting to authorization")
      return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    flask.session['calendars'] = list_calendars(gcal_service)
    return render_template('index.html')

#############################
#
#  AJAX request handler
#
#############################
@app.route("/_setbusytimes")
def find_busy():
	'''
	Receive AJAX request to find the busy times 
	'''
	indices = request.args.get("indices", type=str)
	
	credentials = valid_credentials()
	gcal_service = get_gcal_service(credentials)
	
	busy_times, free_times = get_freebusy_times(gcal_service, indices)	
	flask.session['busy_times'] = busy_times	
	flask.session['free_times'] = free_times
	
	return jsonify(result={})
	
	
def get_freebusy_times(gcal_service, calendar_indices):
	'''
	Sends requests to the Google Calendar API to determine the busy times for 
	the given calendars (based on the indices). Uses those busy times to determine
	the free times of a given time duration.
	
	Args:
		gcal_service: 		Google Calendar Service Object, the service to 
							send freebusy requests to
		calendar_indices: 	String, the indices of the calendars selected
	Returns:
		busy_times, free_times: 	A tuple consisting of the busy times and 
								free times of the given calendars. Both are
								lists of the form
								[ 
								  {"cal1" : [
												[time_start,time_end],
											 	[...]
											]
								   }, 
								  {"cal2" : ...} 
								]
	'''
	busy_times = []
	free_times = []
	
	start_date, end_date = flask.session['daterange'].split(" - ")
	time_range_start = arrow.get(start_date + flask.session['begin_time'], "MM/DD/YYYYHH:mm:ssZZ")
	time_range_end = arrow.get(start_date + flask.session['end_time'], "MM/DD/YYYYHH:mm:ssZZ")
	end_date = arrow.get(end_date, "MM/DD/YYYY")

	app.logger.debug("Sending freebusy requests to Google Cal")
	for index in calendar_indices:
		calendar = flask.session['calendars'][int(index)]
		calendar_name = calendar['summary']
		
		busy = {calendar_name : []}
		free = {calendar_name : []}
		timeMin = time_range_start.isoformat()
		timeMax = time_range_end.isoformat()
		
		for day in arrow.Arrow.span_range('day', time_range_start, end_date):		
			query = {
				"timeMin": timeMin,
				"timeMax": timeMax,
				"items": [
					{
						"id": calendar['id']
					}
				]
			}
			
			gcal_request = gcal_service.freebusy().query(body=query)	
			result = gcal_request.execute()
			
			for busy_time in result['calendars'][calendar['id']]['busy']:
			    start = arrow.get(busy_time['start']).to('local')
			    end = arrow.get(busy_time['end']).to('local')
			    conflict = [start.isoformat(), end.isoformat()]
			    busy[calendar_name].append(conflict)
			# Using the busy times, determine the free times
			free_time = determine_free_times(busy[calendar_name], timeMin, timeMax)
			free[calendar_name].extend(free_time)
			
			timeMin = next_day(timeMin)
			timeMax = next_day(timeMax)
		
		free_times.append(free)
		busy_times.append(busy)		
		
	return busy_times, free_times
	
def determine_free_times(busy_times, free_start, free_end):
	''' Given a list of busy times, and a free block (a beginning and ending free time),
	determines the free times. In other words, finds the complement of the busy_times.
	
	Args:
		busy_times: 		A list of busy times in the form [
															 	[start, end],
															 	[...]
															 ]
		free_start: 		A string representing the isoformat of the start time of the
							free block.
		free_end:			A string representing the isoformat of the end time of the
							free block.
							
	Returns:
		free_times:			A list of free times the form [
																[start, end],
																[...]
														  ]
	'''
	# app.logger.debug("Determining free times")
	busy_agenda = Agenda()
	for busy_time in busy_times:
		start, end = busy_time
		start = arrow.get(start)
		end = arrow.get(end)
		busy_agenda.append(Appt(start, end, ""))
	
	busy_agenda.normalize()
	free_start = arrow.get(free_start)
	free_end = arrow.get(free_end)
	free_block = Appt(free_start, free_end, "")
	free_agenda = busy_agenda.complement(free_block)
	
	free_times = [appt.get_isoformat() for appt in free_agenda]
	
	return free_times		
	
####
#
#  Google calendar authorization:
#      Returns us to the main /choose screen after inserting
#      the calendar_service object in the session state.  May
#      redirect to OAuth server first, and may take multiple
#      trips through the oauth2 callback function.
#
#  Protocol for use ON EACH REQUEST: 
#     First, check for valid credentials
#     If we don't have valid credentials
#         Get credentials (jump to the oauth2 protocol)
#         (redirects back to /choose, this time with credentials)
#     If we do have valid credentials
#         Get the service object
#
#  The final result of successful authorization is a 'service'
#  object.  We use a 'service' object to actually retrieve data
#  from the Google services. Service objects are NOT serializable ---
#  we can't stash one in a cookie.  Instead, on each request we
#  get a fresh serivce object from our credentials, which are
#  serializable. 
#
#  Note that after authorization we always redirect to /choose;
#  If this is unsatisfactory, we'll need a session variable to use
#  as a 'continuation' or 'return address' to use instead. 
#
####

def valid_credentials():
    """
    Returns OAuth2 credentials if we have valid
    credentials in the session.  This is a 'truthy' value.
    Return None if we don't have credentials, or if they
    have expired or are otherwise invalid.  This is a 'falsy' value. 
    """
    if 'credentials' not in flask.session:
      return None

    credentials = client.OAuth2Credentials.from_json(flask.session['credentials'])

    if (credentials.invalid or credentials.access_token_expired):
      return None
    return credentials


def get_gcal_service(credentials):
  """
  We need a Google calendar 'service' object to obtain
  list of calendars, busy times, etc.  This requires
  authorization. If authorization is already in effect,
  we'll just return with the authorization. Otherwise,
  control flow will be interrupted by authorization, and we'll
  end up redirected back to /choose *without a service object*.
  Then the second call will succeed without additional authorization.
  """
  app.logger.debug("Entering get_gcal_service")
  http_auth = credentials.authorize(httplib2.Http())
  service = discovery.build('calendar', 'v3', http=http_auth)
  app.logger.debug("Returning service")
  return service

@app.route('/oauth2callback')
def oauth2callback():
  """
  The 'flow' has this one place to call back to.  We'll enter here
  more than once as steps in the flow are completed, and need to keep
  track of how far we've gotten. The first time we'll do the first
  step, the second time we'll skip the first step and do the second,
  and so on.
  """
  app.logger.debug("Entering oauth2callback")
  flow =  client.flow_from_clientsecrets(
      CLIENT_SECRET_FILE,
      scope= SCOPES,
      redirect_uri=flask.url_for('oauth2callback', _external=True))
  ## Note we are *not* redirecting above.  We are noting *where*
  ## we will redirect to, which is this function. 
  
  ## The *second* time we enter here, it's a callback 
  ## with 'code' set in the URL parameter.  If we don't
  ## see that, it must be the first time through, so we
  ## need to do step 1. 
  app.logger.debug("Got flow")
  if 'code' not in flask.request.args:
    app.logger.debug("Code not in flask.request.args")
    auth_uri = flow.step1_get_authorize_url()
    return flask.redirect(auth_uri)
    ## This will redirect back here, but the second time through
    ## we'll have the 'code' parameter set
  else:
    ## It's the second time through ... we can tell because
    ## we got the 'code' argument in the URL.
    app.logger.debug("Code was in flask.request.args")
    auth_code = flask.request.args.get('code')
    credentials = flow.step2_exchange(auth_code)
    flask.session['credentials'] = credentials.to_json()
    ## Now I can build the service and execute the query,
    ## but for the moment I'll just log it and go back to
    ## the main screen
    app.logger.debug("Got credentials")
    return flask.redirect(flask.url_for('choose'))

#####
#
#  Option setting:  Buttons or forms that add some
#     information into session state.  Don't do the
#     computation here; use of the information might
#     depend on what other information we have.
#   Setting an option sends us back to the main display
#      page, where we may put the new information to use. 
#
#####

@app.route('/setrange', methods=['POST'])
def setrange():
    """
    User chose a date range with the bootstrap daterange widget.
    """
    app.logger.debug("Entering setrange")  
    daterange = request.form.get('daterange')
    begintime = request.form.get('begintime')
    endtime = request.form.get('endtime')
    ## flask.flash("Setrange gave us '{}', '{}', '{}'".format(daterange, begintime, endtime))
    
    bt = arrow.get(begintime, "HH:mm").replace(tzinfo=tz.tzlocal()).isoformat().split("T")[1]
    et = arrow.get(endtime, "HH:mm").replace(tzinfo=tz.tzlocal()).isoformat().split("T")[1]
    
    flask.session['daterange'] = daterange
    flask.session['begin_time'] = bt
    flask.session['end_time'] = et
    
    return flask.redirect(flask.url_for("choose"))


def next_day(isotext):
    """
    ISO date + 1 day (used in query to Google calendar)
    """
    as_arrow = arrow.get(isotext)
    return as_arrow.replace(days=+1).isoformat()

####
#
#  Functions (NOT pages) that return some information
#
####
  
def list_calendars(service):
    """
    Given a google 'service' object, return a list of
    calendars.  Each calendar is represented by a dict, so that
    it can be stored in the session object and converted to
    json for cookies. The returned list is sorted to have
    the primary calendar first, and selected (that is, displayed in
    Google Calendars web app) calendars before unselected calendars.
    """
    app.logger.debug("Entering list_calendars")  
    calendar_list = service.calendarList().list().execute()["items"]
    result = [ ]
    for cal in calendar_list:
        kind = cal["kind"]
        id = cal["id"]
        if "description" in cal: 
            desc = cal["description"]
        else:
            desc = "(no description)"
        summary = cal["summary"]
        # Optional binary attributes with False as default
        selected = ("selected" in cal) and cal["selected"]
        primary = ("primary" in cal) and cal["primary"]        

        result.append(
          { "kind": kind,
            "id": id,
            "summary": summary,
            "selected": selected,
            "primary": primary
            })
    return sorted(result, key=cal_sort_key)


def cal_sort_key( cal ):
    """
    Sort key for the list of calendars:  primary calendar first,
    then other selected calendars, then unselected calendars.
    (" " sorts before "X", and tuples are compared piecewise)
    """
    if cal["selected"]:
       selected_key = " "
    else:
       selected_key = "X"
    if cal["primary"]:
       primary_key = " "
    else:
       primary_key = "X"
    return (primary_key, selected_key, cal["summary"])
    
    
#################
#
# Favicon function rendering
#
#################
  
@app.route('/favicon.ico')
def favicon():
    return flask.send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

#################
#
# Functions used within the templates
#
#################

@app.template_filter( 'fmtdate' )
def format_arrow_date( date ):
    try: 
        normal = arrow.get( date )
        return normal.format("ddd MM/DD/YYYY")
    except:
        return "(bad date)"
        
@app.template_filter( 'fmttime' )
def format_arrow_time( time ):
    try:
        normal = arrow.get(time, "HH:mm:ssZZ")
        return normal.format("hh:mm A")
    except:
        return "(bad time)"

        
@app.template_filter( 'fmtdatetime' )
def format_arrow_datetime( datetime ):
    try:
        normal = arrow.get(datetime)
        return normal.format("MM/DD/YYYY hh:mm A")
    except:
        return "(bad time)"
    
#############


if __name__ == "__main__":
  # App is created above so that it will
  # exist whether this is 'main' or not
  # (e.g., if we are running in a CGI script)

  app.secret_key = str(uuid.uuid4())  
  app.debug=CONFIG.DEBUG
  app.logger.setLevel(logging.DEBUG)
  # We run on localhost only if debugging,
  # otherwise accessible to world
  if CONFIG.DEBUG:
    # Reachable only from the same computer
    app.run(port=CONFIG.PORT)
  else:
    # Reachable from anywhere 
    app.run(port=CONFIG.PORT,host="0.0.0.0")
    

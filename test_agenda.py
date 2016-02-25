"""
Nose test suite for agenda.py
"""

import arrow
from agenda import *

a = arrow.get("01/01/2014 17:00","MM/DD/YYYY HH:mm")
b = arrow.get("01/01/2014 18:00","MM/DD/YYYY HH:mm")
	
c = arrow.get("01/01/2014 17:30","MM/DD/YYYY HH:mm")
d = arrow.get("01/01/2014 18:45","MM/DD/YYYY HH:mm")
	
e = arrow.get("01/01/2014 20:00","MM/DD/YYYY HH:mm")
f = arrow.get("01/01/2014 21:30","MM/DD/YYYY HH:mm")

app1 = Appt(a,b,"Test 1")
app2 = Appt(c,d,"Test 2")
app3 = Appt(e,f,"Test 3")

def test_appt():
	'''
	Testing the 'Appt' class
	'''	
	
	assert(app1.begin == a)
	assert(app1.end == b)
	
	assert app1 < app3
	assert app2 < app3
	assert not app1 > app3

	assert app1.overlaps(app2)
	assert not app1.overlaps(app3)
	
	union = app1.union(app2)
	
	assert union.begin == a
	assert union.end == d
	
	intersection = app1.intersect(app2)
	
	assert intersection.begin == c
	assert intersection.end == b
	
	
def test_agenda_equality():
	'''
	Testing Agenda.__eq__
	'''
	agenda1 = Agenda()
	agenda2 = Agenda()
	
	agenda1.append(app1)
	agenda1.append(app2)
	
	agenda2.append(app1)
	agenda2.append(app2)
	
	assert agenda1 == agenda2
		
def test_agenda():
	'''
	Testing the 'Agenda' class
	'''
	schedule1 = Agenda()	
	
	schedule1.append(app1)
	schedule1.append(app2)
	
	normalized_schedule = schedule1.normalized()
	
	normalized_appt = Appt(a, d, "Normalized test")
	test_agenda = Agenda()
	test_agenda.append(normalized_appt)
	
	assert normalized_schedule == test_agenda
	
	schedule2 = Agenda()
	
	w = arrow.get("01/01/2014 17:15","MM/DD/YYYY HH:mm")
	x = arrow.get("01/01/2014 20:00","MM/DD/YYYY HH:mm")
	
	app4 = Appt(w, x, "Testing Agenda.intersect")
	
	schedule2.append(app4)
	
	intersection = schedule1.intersect(schedule2)
	intersection.normalize()
	
	solution = Agenda()
	solution.append(Appt(w, d, "Test"))
	assert intersection == solution
	
	y = arrow.get("01/01/2014 09:00","MM/DD/YYYY HH:mm")
	z = arrow.get("01/01/2014 22:00","MM/DD/YYYY HH:mm")
	
	free = Appt(y, z, "Freeblock")
	
	solution = Agenda()
	solution.append(Appt(y, a, "Free time 1"))
	solution.append(Appt(d, z, "Free time 2"))
	
	complement = schedule1.complement(free)
	assert complement == solution
	
""" Helper module to represent a schedule of appointments.

   Author: Alexander Owen   
   Starter code from M. Young, University of Oregon

   An Agenda is a list-like container of Appt (appointment).
   Appt consists of a begin time, ending time, and a description.
"""

import datetime
import arrow

class Appt:
    """
    A single appointment, starting on a particular
    date and time, and ending at a later time the same day.
    """
    
    def __init__(self, begin, end, desc):
        """Create an appointment on date from begin time to end time.
        
        Arguments:
            begin: An arrow object.  When the appointment starts. 
            end:  An arrow object.  When the appointments ends.
            desc: A string describing the appointment            
        Raises: 
        	ValueError if appointment ends before it begins        	
        """
        self.begin = begin
        self.end = end
        if begin >= end :
            raise ValueError("Appointment end must be after begin")
        self.desc = desc
        return
        
    def __lt__(self, other):
        """Does this appointment finish before other begins?
        
        Arguments:
        	other: another Appt
        Returns: 
        	True iff this Appt is done by the time other begins.
        """
        return self.end <= other.begin
        
    def __gt__(self, other):
        """Does other appointment finish before this begins?
        
        Arguments:
        	other: another Appt
        Returns: 
        	True iff other is done by the time this Appt begins
        """
        return other < self
        
    def overlaps(self, other):
        """Is there a non-zero overlap between this appointment
        and the other appointment?
		Arguments:
            other is an Appt
        Returns:
            True iff there exists some duration (greater than zero)
            between this Appt and other. 
        """
        return  not (self < other or other < self)
            
    def intersect(self, other, desc=""):
        """Return an appointment representing the period in
        common between this appointment and another.
        Requires self.overlaps(other).
        
        Note: Cannot handle intersections spanning multiple days...
        
		Arguments: 
			other:  Another Appt
			desc:  (optional) description text for this appointment. 

		Returns: 
			An appointment representing the time period in common
			between self and other.   Description of returned Appt 
			is copied from this (self), unless a non-null string is 
			provided as desc. 
        """
        if desc=="":
            desc = self.desc
        assert(self.overlaps(other))
        # We know the day must be the same. 
        # Find overlap of times: 
        #   Later of two begin times, earlier of two end times
        begin = max(self.begin, other.begin)
        end = min(self.end, other.end)
        return Appt(begin, end, desc)

    def union(self, other, desc=""):
        """Return an appointment representing the combined period in
        common between this appointment and another.
        Requires self.overlaps(other).
        
		Arguments: 
			other:  Another Appt
			desc:  (optional) description text for this appointment. 

		Returns: 
			An appointment representing the time period spanning
                        both self and other.   Description of returned Appt 
			is concatenation of two unless a non-null string is 
			provided as desc. 
        """
        if desc=="":
            desc = self.desc + " " + other.desc
        assert(self.overlaps(other))
        # We know the day must be the same. 
        # Find overlap of times: 
        #   Earlier of two begin times, later of two end times
        begin = min(self.begin, other.begin)
        end = max(self.end, other.end)
        return Appt(begin, end, desc)
        
    def get_isoformat(self):
    	""" Returns the isoformat of the begin and end of Appt.
    	
    	Returns:
    		A list of the form [begin time, end time]   	   
    	"""
    	start = self.begin.isoformat()
    	end = self.end.isoformat()
    	return [start, end]


class Agenda:
    """An Agenda is essentially a list of appointments,
    with some agenda-specific methods.
    """

    def __init__(self):
        """An empty agenda."""
        self.appts = [ ]
        
    def append(self, appt):
        """Add an Appt to the agenda.
        
        Throws: AssertionError if appt is not type 'Appt'.
        """
        assert isinstance(appt, Appt)
        self.appts.append(appt)

    def intersect(self,other,desc=""): 
        """Return a new agenda containing appointments
        that are overlaps between appointments in this agenda
        and appointments in the other agenda.

        Titles of appointments in the resulting agenda are
        taken from this agenda, unless they are overridden with
        the "desc" argument.

        Arguments:
           other: Another Agenda, to be intersected with this one
           desc:  If provided, this string becomes the title of
                all the appointments in the result.
        """
        default_desc = (desc == "")
        result = Agenda()
        for thisappt in self.appts:
            if default_desc: 
                desc = thisappt.desc
            for otherappt in other.appts:
                if thisappt.overlaps(otherappt):
                    result.append(thisappt.intersect(otherappt,desc))
        
        return result

    def normalize(self):
        """Merge overlapping events in an agenda. For example, if 
        the first appointment is from 1pm to 3pm, and the second is
        from 2pm to 4pm, these two are merged into an appt from 
        1pm to 4pm, with a combination description.  
        After normalize, the agenda is in order by date and time, 
        with no overlapping appointments.
        """
        if len(self.appts) == 0:
            return

        ordering = lambda ap: ap.begin
        self.appts.sort(key=ordering)

        normalized = [ ]
        cur = self.appts[0]  
        for appt in self.appts[1:]:
            if appt > cur:   # Not overlapping
                normalized.append(cur)
                cur = appt
            else:            # Overlapping
                cur = cur.union(appt)
        normalized.append(cur)
        self.appts = normalized

    def normalized(self):
        """
        A non-destructive normalize
        (like "sorted(l)" vs "l.sort()").
        Returns a normalized copy of this agenda.
        """
        copy = Agenda()
        copy.appts = self.appts
        copy.normalize()
        return copy
        
    def complement(self, freeblock):
        """Produce the complement of an agenda
        within the span of a timeblock represented by 
        an appointment.  For example, 
        if this agenda is a set of appointments, produce a 
        new agenda of the times *not* in appointments in 
        a given time period.
        Args: 
           freeblock: An 'Appt' object. Looking  for time blocks in this period 
               that are not conflicting with appointments in 
               this agenda.
        Returns: 
           A new agenda containing exactly the times that 
           are within the period of freeblock and 
           not within appointments in this agenda. The 
           description of the resulting appointments comes
           from freeblock.desc.
        """
        copy = self.normalized()
        comp = Agenda()
        day = freeblock.begin.date()
        desc = freeblock.desc
        cur_time = freeblock.begin
        for appt in copy.appts:
            if appt < freeblock:
                continue
            if appt > freeblock:
                if cur_time < freeblock.end:
                    comp.append(Appt(cur_time,freeblock.end, desc))
                    cur_time = freeblock.end
                break
            if cur_time < appt.begin:
                comp.append(Appt(cur_time, appt.begin, desc))
            cur_time = max(appt.end,cur_time)
        if cur_time < freeblock.end:
            comp.append(Appt(cur_time, freeblock.end, desc))
        return comp



    def __len__(self):
        """Number of appointments, callable as built-in len() function"""
        return len(self.appts)

    def __iter__(self):
        """An iterator through the appointments in this agenda."""
        return self.appts.__iter__()

    def __str__(self):
        """String representation of a whole agenda"""
        rep = ""
        for appt in self.appts:
            rep += str(appt) + "\n"
        return rep[:-1]

    def __eq__(self,other):
        """Equality, ignoring descriptions --- just equal blocks of time"""
        if len(self.appts) != len(other.appts):
            return False
        for i in range(len(self.appts)):
            mine = self.appts[i]
            theirs = other.appts[i]
            if not (mine.begin == theirs.begin and
                    mine.end == theirs.end):
                return False
        return True

    
    

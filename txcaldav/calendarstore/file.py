##
# Copyright (c) 2010 Apple Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##

"""
File calendar store.
"""

__all__ = [
    "CalendarStore",
    "CalendarHome",
    "Calendar",
    "CalendarObject",
]

import errno

from zope.interface import implements

from twisted.python.filepath import FilePath

from twext.log import LoggingMixIn
from twext.python.icalendar import Component as iComponent, InvalidICalendarDataError

from txcaldav.icalendarstore import ICalendarHome, ICalendar, ICalendarObject
#from txcaldav.icalendarstore import CalendarStoreError
#from txcaldav.icalendarstore import AlreadyExistsError
#from txcaldav.icalendarstore import CalendarAlreadyExistsError
#from txcaldav.icalendarstore import CalendarObjectNameAlreadyExistsError
#from txcaldav.icalendarstore import CalendarObjectUIDAlreadyExistsError
from txcaldav.icalendarstore import NotFoundError
#from txcaldav.icalendarstore import NoSuchCalendarError
from txcaldav.icalendarstore import NoSuchCalendarObjectError
#from txcaldav.icalendarstore import InvalidCalendarComponentError
from txcaldav.icalendarstore import InternalDataStoreError


class CalendarStore(LoggingMixIn):
    # FIXME: Do we need an interface?

    calendarHomeClass = property(lambda _: CalendarHome)

    def __init__(self, path):
        """
        @param path: a L{FilePath}
        """
        assert isinstance(path, FilePath)

        self.path = path

        if not path.isdir():
            # FIXME: If we add a CalendarStore interface, this should
            # be CalendarStoreNotFoundError.
            raise NotFoundError("No such calendar store")

    def __str__(self):
        return "<%s: %s>" % (self.__class__, self.path)

    def calendarHomeWithUID(self, uid):
        return CalendarHome(self.path.child(uid), self)


class CalendarHome(LoggingMixIn):
    implements(ICalendarHome)

    calendarClass = property(lambda _: Calendar)

    def __init__(self, path, calendarStore):
        self.path = path
        self.calendarStore = calendarStore

    def __str__(self):
        return "<%s: %s>" % (self.__class__, self.path)

    def uid(self):
        return self.path.basename()

    def calendars(self):
        return (
            self.calendarWithName(name)
            for name in self.path.listdir()
            if not name.startswith(".")
        )

    def calendarWithName(self, name):
        return Calendar(self.path.child(name), self)

    def createCalendarWithName(self, name):
        raise NotImplementedError()

    def removeCalendarWithName(self, name):
        raise NotImplementedError()

    def properties(self):
        raise NotImplementedError()


class Calendar(LoggingMixIn):
    implements(ICalendar)

    calendarObjectClass = property(lambda _: CalendarObject)

    def __init__(self, path, calendarHome):
        self.path = path
        self.calendarHome = calendarHome

    def __str__(self):
        return "<%s: %s>" % (self.__class__, self.path)

    def name(self):
        return self.path.basename()

    def ownerCalendarHome(self):
        return self.calendarHome

    def calendarObjects(self):
        return (
            self.calendarObjectWithName(name)
            for name in self.path.listdir()
            if not name.startswith(".")
        )

    def calendarObjectWithName(self, name):
        return CalendarObject(self.path.child(name), self)

    def calendarObjectWithUID(self, uid):
        raise NotImplementedError()

    def createCalendarObjectWithName(self, name, component):
        raise NotImplementedError()

    def removeCalendarObjectWithName(self, name):
        raise NotImplementedError()

    def removeCalendarObjectWithUID(self, uid):
        raise NotImplementedError()

    def syncToken(self):
        raise NotImplementedError()

    def calendarObjectsInTimeRange(self, start, end, timeZone):
        raise NotImplementedError()

    def calendarObjectsSinceToken(self, token):
        raise NotImplementedError()

    def properties(self):
        raise NotImplementedError()


class CalendarObject(LoggingMixIn):
    implements(ICalendarObject)

    def __init__(self, path, calendar):
        self.path = path
        self.calendar = calendar

    def __str__(self):
        return "<%s: %s>" % (self.__class__, self.path)

    def name(self):
        return self.path.basename()

    def setComponent(self, component):
        raise NotImplementedError()

    def component(self):
        if not hasattr(self, "_component"):
            text = self.iCalendarText()

            try:
                component = iComponent.fromString(text)
            except InvalidICalendarDataError, e:
                raise InternalDataStoreError(
                    "File corruption detected (%s) in file: %s"
                    % (e, self.path.path)
                )

            del self._text
            self._component = component

        return self._component

    def iCalendarText(self):
        #
        # Note I'm making an assumption here that caching both is
        # redundant, so we're caching the text if it's asked for and
        # we don't have the component cached, then tossing it and
        # relying on the component if we have that cached. -wsv
        #
        if not hasattr(self, "_text"):
            if hasattr(self, "_component"):
                return str(self._component)

            try:
                fh = self.path.open()
            except IOError, e:
                if e[0] == errno.ENOENT:
                    raise NoSuchCalendarObjectError(self)

            try:
                text = fh.read()
            finally:
                fh.close()

            if not (
                text.startswith("BEGIN:VCALENDAR\r\n") or
                text.endswith("\r\nEND:VCALENDAR\r\n")
            ):
                raise InternalDataStoreError(
                    "File corruption detected (improper start) in file: %s"
                    % (self.path.path,)
                )

            self._text = text

        return self._text

    def uid(self):
        if not hasattr(self, "_uid"):
            self._uid = self.component().resourceUID()
        return self._uid

    def componentType(self):
        if not hasattr(self, "_componentType"):
            self._componentType = self.component().mainType()
        return self._componentType

    def organizer(self):
        # FIXME: Ideally should return a URI object
        raise NotImplementedError()

    def properties(self):
        raise NotImplementedError()

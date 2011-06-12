from Components.ActionMap import ActionMap, HelpableActionMap
from Components.AVSwitch import AVSwitch
from Components.Button import Button
from Components.config import ConfigSubsection, config, ConfigSelection, ConfigClock, ConfigInteger, ConfigBoolean, getConfigListEntry
from Components.ConfigList import ConfigListScreen
from Components.EpgList import EPGList, Rect
from Components.GUIComponent import GUIComponent
from Components.HTMLComponent import HTMLComponent
from Components.Label import Label
from Components.Language import language
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaTest
from Components.Pixmap import Pixmap
from Components.Sources.Event import Event
from RecordTimer import RecordTimerEntry, parseEvent, AFTEREVENT
from Screens.EpgSelection import EPGSelection, RecordSetup
from Screens.EventView import EventViewSimple
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.TimeDateInput import TimeDateInput
from Screens.TimerEdit import TimerSanityConflict
from Screens.TimerEntry import TimerEntry
from ServiceReference import ServiceReference
from Tools.Directories import pathExists, resolveFilename, SCOPE_CURRENT_SKIN, SCOPE_LANGUAGE, SCOPE_PLUGINS
from Tools.LoadPixmap import LoadPixmap

from datetime import datetime
from time import time, strftime, localtime, mktime
from enigma import getDesktop, eListbox, eEPGCache, eTimer, eServiceCenter, eServiceReference, eListboxPythonMultiContent, eRect, ePicLoad, gFont, RT_HALIGN_LEFT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_WRAP
from skin import parseColor
from os import listdir, path, environ
import gettext

# Partnerbox installed and icons in epglist enabled?
try:
	from Plugins.Extensions.Partnerbox.plugin import PartnerboxSetup
except ImportError:
	pass
try:
	from Plugins.Extensions.AutoTimer.AutoTimerEditor import addAutotimerFromEvent
except ImportError:
	pass
try:
	from Plugins.Extensions.EPGSearch.EPGSearch import EPGSearch
except ImportError:
	pass
try:
	from Plugins.Extensions.IMDb.plugin import IMDB, IMDBEPGSelection
except ImportError:
	pass

config.plugins.VIXEPG=ConfigSubsection()
config.plugins.VIXEPG.OK = ConfigSelection(choices = [("Zap",_("Zap")), ("Zap + Exit", _("Zap + Exit"))], default = "Zap")
config.plugins.VIXEPG.OKLong = ConfigSelection(choices = [("Zap",_("Zap")), ("Zap + Exit", _("Zap + Exit"))], default = "Zap + Exit")
config.plugins.VIXEPG.Info = ConfigSelection(choices = [("Channel Info", _("Channel Info")), ("Single EPG", _("ViX Single EPG"))], default = "Channel Info")
config.plugins.VIXEPG.InfoLong = ConfigSelection(choices = [("Channel Info", _("Channel Info")), ("View Single EPG", _("View Single EPG"))], default = "View Single EPG")
config.plugins.VIXEPG.prev_time=ConfigClock(default = time())
config.plugins.VIXEPG.Primetime1 = ConfigInteger(default=20, limits=(0, 23))
config.plugins.VIXEPG.Primetime2 = ConfigInteger(default=0, limits=(0, 59))
config.plugins.VIXEPG.UsePicon = ConfigSelection(choices = [("No", _("No")), ("Yes", _("Yes"))], default = "Yes")
config.plugins.VIXEPG.channel1 = ConfigSelection(choices = [("No", _("No")), ("Yes", _("Yes"))], default = "No")
config.plugins.VIXEPG.coolswitch = ConfigSelection(choices = [("7-8", _("7-8")), ("14-16", _("14-16"))], default = "7-8")
config.plugins.VIXEPG.prev_time_period=ConfigInteger(default=180, limits=(60,300))
config.plugins.VIXEPG.Fontsize = ConfigInteger(default=18, limits=(10, 30))
config.plugins.VIXEPG.Left_Fontsize = ConfigInteger(default=22, limits=(10, 30))
config.plugins.VIXEPG.Timeline = ConfigInteger(default=20, limits=(10, 30))
config.plugins.VIXEPG.items_per_page = ConfigInteger(default=11, limits=(3, 16))
config.plugins.VIXEPG.left8 = ConfigInteger(default=110, limits=(70, 250))
config.plugins.VIXEPG.left16 = ConfigInteger(default=190, limits=(70, 250))
config.plugins.VIXEPG.overjump = ConfigBoolean(default=False)
config.plugins.VIXEPG.PIG = ConfigSelection(choices = [("No", _("No")), ("Yes", _("Yes"))], default = "No")
#######################################################################

#lang = language.getLanguage()
#environ["LANGUAGE"] = lang[:2]
#print "[VIXMainMenu] set language to ", lang[:2]
#gettext.bindtextdomain("enigma2", resolveFilename(SCOPE_LANGUAGE))
#gettext.textdomain("enigma2")
#gettext.bindtextdomain("VIX", "%s%s" % (resolveFilename(SCOPE_PLUGINS), "SystemPlugins/ViX/locale"))

#def _(txt):
	#t = gettext.dgettext("VIXMainMenu", txt)
	#if t == txt:
		#t = gettext.gettext(txt)
	#return t

def showVIXEPG(self):
	if isinstance(self, InfoBarEPG):
		if isinstance(self, InfoBar):
			global Session
			Session = self.session
			global Servicelist
			Servicelist = self.servicelist
			global bouquets
			bouquets = Servicelist and Servicelist.getBouquetList()
			global epg_bouquet
			epg_bouquet = Servicelist and Servicelist.getRoot()
			if epg_bouquet is not None:
				if len(bouquets) > 1 :
					cb = VIXEPG_CB
				else:
					cb = None
				services = VIXEPG_getBouquetServices(epg_bouquet)
				Session.openWithCallback(VIXEPG_closed, VIXEPG, services, VIXEPG_zapToService, cb, ServiceReference(epg_bouquet).getServiceName())

############################################################
# VIXEPG
############################################################
class VIXEPGEPGList(EPGList):
	searchPiconPaths = ['/usr/share/enigma2/picon/','/picon/']
	for f in listdir("/media"):
		if pathExists("/media/" + f + '/picon/'):
			searchPiconPaths.append('/media/' + f + '/picon/')
	if pathExists("/autofs"):
		for f in listdir("/autofs"):
			if pathExists("/autofs/" + f + '/picon/'):
				searchPiconPaths.append('/autofs/' + f + '/picon/')
	if path.exists("/media/net"):
		for f in listdir("/media/net"):
			if pathExists("/media/net/" + f + '/picon/'):
				searchPiconPaths.append('/media/net/' + f + '/picon/')

	def __init__(self, selChangedCB=None, timer = None, time_epoch = 120, overjump_empty=False):
		self.cur_event = None
		self.cur_service = None
		self.offs = 0
		self.timer = timer
		self.onSelChanged = [ ]
		self.type = VIXEPGEPGList

		if selChangedCB is not None:
			self.onSelChanged.append(selChangedCB)
		GUIComponent.__init__(self)
		self.l = eListboxPythonMultiContent()
		self.curr_refcool = None	
		self.coolheight = 54
		self.l.setBuildFunc(self.buildEntry)
		self.setOverjump_Empty(overjump_empty)
		self.epgcache = eEPGCache.getInstance()

		self.time_base = None
		self.time_epoch = time_epoch
		self.list = None
		self.event_rect = None
		self.nowForeColor = 0xffffff
		self.nowForeColorSelected = 0x000000
		self.foreColor = 0xffffff
		self.foreColorSelected = 0x000000
		self.borderColor = 0xC0C0C0
		self.backColor = 0x2D455E
		self.backColorSelected = 0xC0C0C0
		self.nowBackColor = 0x00825F
		self.nowBackColorSelected = 0x4800FF
		self.foreColorService = 0xffffff
		self.backColorService = 0x000000

	def applySkin(self, desktop, screen):
		if self.skinAttributes is not None:
			attribs = [ ]
			for (attrib, value) in self.skinAttributes:
				if attrib == "EntryForegroundColor":
					self.foreColor = parseColor(value).argb()
				elif attrib == "EntryForegroundColorSelected":
					self.foreColorSelected = parseColor(value).argb()
				elif attrib == "EntryNowForegroundColorSelected":
					self.nowForeColorSelected = parseColor(value).argb()
				elif attrib == "EntryNowForegroundColor":
					self.nowForeColor = parseColor(value).argb()
				elif attrib == "EntryBorderColor":
					self.borderColor = parseColor(value).argb()
				elif attrib == "EntryBackgroundColor":
					self.backColor = parseColor(value).argb()
				elif attrib == "EntryNowBackgroundColor":
					self.nowBackColor = parseColor(value).argb()
				elif attrib == "EntryBackgroundColorSelected":
					self.backColorSelected = parseColor(value).argb()
				elif attrib == "EntryNowBackgroundColorSelected":
					self.nowBackColorSelected = parseColor(value).argb()
				elif attrib == "ServiceNameForegroundColor":
					self.foreColorService = parseColor(value).argb()
				elif attrib == "ServiceNameBackgroundColor":
					self.backColorService = parseColor(value).argb()
				else:
					attribs.append((attrib,value))
			self.skinAttributes = attribs
		rc = GUIComponent.applySkin(self, desktop, screen)
		self.setItemsPerPage()
		return rc

	def isSelectable(self, service, sname, event_list):
		return (event_list and len(event_list) and True) or False

	def setOverjump_Empty(self, overjump_empty):
		if overjump_empty:
			self.l.setSelectableFunc(self.isSelectable)
		
	def setEpoch(self, epoch):
		self.offs = 0
		self.time_epoch = epoch
		self.fillVIXEPG(None)

	def setEpoch2(self, epoch):
		self.offs = 0
		self.time_epoch = epoch

	def getEventFromId(self, service, eventid):
		event = None
		if self.epgcache is not None and eventid is not None:
			event = self.epgcache.lookupEventId(service.ref, eventid)
		return event

	def moveToService(self,serviceref):
		if serviceref is not None:
			for x in range(len(self.list)):
				if self.list[x][0] == serviceref.toString():
					self.instance.moveSelectionTo(x)
					break
	
	def getIndexFromService(self, serviceref):
		if serviceref is not None:
			for x in range(len(self.list)):
				if self.list[x][0] == serviceref.toString():
					return x
		
	def setCurrentIndex(self, index):
		if self.instance is not None:
			self.instance.moveSelectionTo(index)
	
	def getCurrent(self):
		if self.cur_service is None:
			return ( None, None )
		old_service = self.cur_service  #(service, service_name, events)
		events = self.cur_service[2]
		refstr = self.cur_service[0]
		if self.cur_event is None or not events or not len(events):
			return ( None, ServiceReference(refstr) )
		event = events[self.cur_event] #(event_id, event_title, begin_time, duration)
		eventid = event[0]
		service = ServiceReference(refstr)
		event = self.getEventFromId(service, eventid)
		return ( event, service )

	def connectSelectionChanged(func):
		if not self.onSelChanged.count(func):
			self.onSelChanged.append(func)

	def disconnectSelectionChanged(func):
		self.onSelChanged.remove(func)

	def serviceChanged(self):
		cur_sel = self.l.getCurrentSelection()
		if cur_sel:
			self.findBestEvent()

	def findBestEvent(self):
		old_service = self.cur_service  #(service, service_name, events)
		cur_service = self.cur_service = self.l.getCurrentSelection()
		last_time = 0;
		time_base = self.getTimeBase()
		if old_service and self.cur_event is not None:
			events = old_service[2]
			cur_event = events[self.cur_event] #(event_id, event_title, begin_time, duration)
			last_time = cur_event[2]
			if last_time < time_base:
				last_time = time_base
		if cur_service:
			self.cur_event = 0
			events = cur_service[2]
			if events and len(events):
				if last_time:
					best_diff = 0
					best = len(events) #set invalid
					idx = 0
					for event in events: #iterate all events
						ev_time = event[2]
						if ev_time < time_base:
							ev_time = time_base
						diff = abs(ev_time-last_time)
						if (best == len(events)) or (diff < best_diff):
							best = idx
							best_diff = diff
						idx += 1
					if best != len(events):
						self.cur_event = best
			else:
				self.cur_event = None
		self.selEntry(0)

	def selectionChanged(self):
		for x in self.onSelChanged:
			if x is not None:
				x()

	GUI_WIDGET = eListbox

	def setItemsPerPage(self):
		global VIXEPG16
		global VIXEPGEPGheight
#		ItemHeight = None
		VIXEPGEPGheight = self.instance.size().height()
		if not config.plugins.VIXEPG.coolswitch.value == "14-16":
			self.l.setItemHeight(VIXEPGEPGheight / config.plugins.VIXEPG.items_per_page.value)
			self.coolheight = (VIXEPGEPGheight / config.plugins.VIXEPG.items_per_page.value)
		if ((VIXEPGEPGheight / config.plugins.VIXEPG.items_per_page.value) / 3) > 27:
			VIXEPG16 = ((VIXEPGEPGheight / config.plugins.VIXEPG.items_per_page.value) / 3)
		elif ((VIXEPGEPGheight / config.plugins.VIXEPG.items_per_page.value) / 2) > 27:
			VIXEPG16 = ((VIXEPGEPGheight / config.plugins.VIXEPG.items_per_page.value) / 2)
		else:
			VIXEPG16 = 27
		if config.plugins.VIXEPG.coolswitch.value == "14-16":
			self.coolheight = VIXEPG16
			self.l.setItemHeight(VIXEPG16)

	def setServiceFontsize(self):
		self.l.setFont(0, gFont("Regular", config.plugins.VIXEPG.Left_Fontsize.value))

	def setEventFontsize(self):
		self.l.setFont(1, gFont("Regular", config.plugins.VIXEPG.Fontsize.value))

	def postWidgetCreate(self, instance):
		instance.setWrapAround(True)
		instance.selectionChanged.get().append(self.serviceChanged)
		instance.setContent(self.l)
		self.l.setSelectionClip(eRect(0,0,0,0), False)
		self.setServiceFontsize()
		self.setEventFontsize()

	def preWidgetRemove(self, instance):
		instance.selectionChanged.get().remove(self.serviceChanged)
		instance.setContent(None)

	def recalcEntrySize(self):
		global VIXEPGNoPicon
		global ItemHeight
		esize = self.l.getItemSize()
		width = esize.width()
		height = esize.height()
		xpos = 0;
		if self.coolheight >=54 and config.plugins.VIXEPG.UsePicon.value == "Yes":
			w = config.plugins.VIXEPG.left8.value;
			ItemHeight = height;
			VIXEPGNoPicon = 1;
		elif self.coolheight >=54 and config.plugins.VIXEPG.UsePicon.value == "No":
			w = config.plugins.VIXEPG.left16.value;
			ItemHeight = height;
			VIXEPGNoPicon = 1;
		if self.coolheight <54:
			w = config.plugins.VIXEPG.left16.value;
			VIXEPGNoPicon = 2;
		self.service_rect = Rect(xpos, 0, w, height)
		xpos += w;
		w = width - xpos;
		self.event_rect = Rect(xpos, 0, w, height)
		
	def calcEntryPosAndWidthHelper(self, stime, duration, start, end, width):
		xpos = (stime - start) * width / (end - start)
		ewidth = (stime + duration - start) * width / (end - start) + 1
		ewidth -= xpos;
		if xpos < 0:
			ewidth += xpos;
			xpos = 0;
		if (xpos+ewidth) > width:
			ewidth = width - xpos
		return xpos, ewidth

	def calcEntryPosAndWidth(self, event_rect, time_base, time_epoch, ev_start, ev_duration):
		xpos, width = self.calcEntryPosAndWidthHelper(ev_start, ev_duration, time_base, time_base + time_epoch * 60, event_rect.width())
		return xpos+event_rect.left(), width

	def buildEntry(self, service, service_name, events):
		if service == self.cur_service[0]:
			piconbkcolor = 0xB5B5B5
		else:
			piconbkcolor = 0x909090
		r1=self.service_rect
		r2=self.event_rect
		foreColor = self.foreColor
		foreColorSelected = self.foreColorSelected
		backColor = self.backColor
		backColorSelected = self.backColorSelected
		borderColor = self.borderColor
		backColorService = self.backColorService
		backColorOrig = self.backColor # normale Eventsfarbe
#		VIXEPGEvent = 1
		if self.curr_refcool.toString() == service:
#			backColor = 0x516b96
#			backColorOrig = 0x516b96
			backColorService = 0x516b96
		res = [ None ]
		picon = self.findPicon(service, service_name)


		if picon is None or self.coolheight <54:
			res.append(MultiContentEntryText(
			pos = (r1.left(),r1.top()),
			size = (r1.width(), r1.height()),
				font = 0, flags = RT_HALIGN_CENTER | RT_VALIGN_CENTER,
			text = service_name,
				color = self.foreColorService,
				border_width = 1, border_color = borderColor,
				backcolor = backColorService, backcolor_sel = backColorService)) #backcolor_sel= Event left select

		elif self.coolheight >=54:
			res.append(MultiContentEntryPixmapAlphaTest(
				pos = (r1.left(),r1.top()),
				size = (r1.width(), r1.height()),
				png = LoadPixmap(picon),
				backcolor = piconbkcolor,
				backcolor_sel = 0))

		if events:
			start = self.time_base+self.offs*self.time_epoch*60
			end = start + self.time_epoch * 60
			left = r2.left()
			top = r2.top()
			width = r2.width()
			height = r2.height()
			coolflags = RT_HALIGN_LEFT | RT_VALIGN_CENTER
			thepraefix = " "

			if self.coolheight > 30:
				coolflags = RT_HALIGN_CENTER | RT_VALIGN_CENTER | RT_WRAP
				thepraefix = ""
#				if service == self.cur_service[0]:
#					backColorSelected = self.backColorSelected
			now = int(time())
			for ev in events:  #(event_id, event_title, begin_time, duration)
				rec=ev[2] and self.timer.isInTimer(ev[0], ev[2], ev[3], service)
				xpos, ewidth = self.calcEntryPosAndWidthHelper(ev[2], ev[3], start, end, width)

				if self.curr_refcool.toString() == service:
					backColorOrig = 0x516b96

				if ev[2] <= now and (ev[2] + ev[3]) > now:
					foreColor = self.nowForeColor
					foreColorSelected = self.nowForeColorSelected
					backColor = self.nowBackColor
#						backColorSelected = self.backColorSelected # Event Selected
				else:
					backColor = backColorOrig 
#						backColorSelected = self.backColorSelected

					foreColor = self.foreColor
					foreColorSelected = self.foreColorSelected

				if rec:
					cooltyp = self.VIXEPGRecRed(service, ev[2], ev[3], ev[0])
					if cooltyp == "record":
						backColor = 0xcf5353 
						backColorSelected = 0xf7664b
					elif cooltyp == "justplay":						
						backColor = 0x669466
						backColorSelected = 0x61a161
#					elif cooltyp == "nichts" and cooltyp != "record":						
#						backColor = 0xB6FF00
#						backColorSelected = 0xC0FF23
					else:
						backColor = backColorOrig 
						backColorSelected = self.backColorSelected

				res.append(MultiContentEntryText(
					pos = (left+xpos, top), size = (ewidth, height),
					font = 1, flags = coolflags,
					text = thepraefix + ev[1], color = foreColor, color_sel = foreColorSelected,
					backcolor = backColor, backcolor_sel = backColorSelected, border_width = 1, border_color = borderColor)) # Color select Event

		else:
			left = r2.left()
			top = r2.top()
			width = r2.width()
			height = r2.height()
			res.append(MultiContentEntryText(			
				pos = (left, top), size = (width, height),
				font = 1, flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER,
				text = " ", color = foreColor, color_sel = foreColorSelected,
				border_width = 1, backcolor_sel = backColorSelected, border_color = borderColor))
		return res

	def findPicon(self, service = None, serviceName = None):
		if config.plugins.VIXEPG.UsePicon.value == "Yes" and VIXEPGNoPicon == 1:
			service_refstr = None
			serviceName_ref = None
			if service is not None:
				serviceName_ref = ServiceReference(service).getServiceName()	#get true servicename
				serviceName_ref = serviceName_ref.replace('\xc2\x87', '').replace('\xc2\x86', '').decode("utf-8").encode("latin1")
				pos = service.rfind(':')
				if pos != -1:
					service_refstr = service[:pos].rstrip(':').replace(':','_')
				pngname = "/tmp/gmepgpicon/" + service_refstr + ".png"
				if pathExists(pngname):
					return pngname
			if serviceName is not None:
				pngname = "/tmp/gmepgpicon/" + serviceName + ".png"
				if pathExists(pngname):
					return pngname
			if serviceName_ref is not None:
				pngname = "/tmp/gmepgpicon/" + serviceName_ref + ".png"
				if pathExists(pngname):
					return pngname
			if service_refstr is not None:
				for path in self.searchPiconPaths:
					pngname = path + service_refstr + ".png"
					if pathExists(pngname):
						return pngname
			if serviceName is not None:
				for path in self.searchPiconPaths:
					pngname = path + serviceName + ".png"
					if pathExists(pngname):
						print"picon found"
						return pngname
			if serviceName_ref is not None:
				for path in self.searchPiconPaths:
					pngname = path + serviceName_ref + ".png"
					if pathExists(pngname):
						print"picon found"
						return pngname

	def selEntry(self, dir, visible=True):
		cur_service = self.cur_service #(service, service_name, events)
		self.recalcEntrySize()
		valid_event = self.cur_event is not None
		if cur_service:
			update = True
			entries = cur_service[2]
			if dir == 0: #current
				update = False
			elif dir == +1: #next
				if valid_event and self.cur_event+1 < len(entries):
					self.cur_event+=1
				else:
					self.offs += 1
					self.fillVIXEPG(None) # refill
					return True
			elif dir == -1: #prev
				if valid_event and self.cur_event-1 >= 0:
					self.cur_event-=1
				elif self.offs > 0:				
					self.offs -= 1
					self.fillVIXEPG(None) # refill
					return True
			elif dir == +2: #next page
				self.offs += 1
				self.fillVIXEPG(None) # refill
				return True
			elif dir == -2: #prev
				if self.offs > 0:
					self.offs -= 1
					self.fillVIXEPG(None) # refill
					return True

		self.l.setSelectionClip(eRect(self.service_rect.left(), self.service_rect.top(), self.service_rect.width(), self.service_rect.height()), False) # left Picon select
		if cur_service and valid_event:
			entry = entries[self.cur_event] #(event_id, event_title, begin_time, duration)
			time_base = self.time_base+self.offs*self.time_epoch*60
			xpos, width = self.calcEntryPosAndWidth(self.event_rect, time_base, self.time_epoch, entry[2], entry[3])
			self.l.setSelectionClip(eRect(xpos, 0, width, self.event_rect.height()), visible and update)
		else:
			self.l.setSelectionClip(eRect(self.event_rect.left(), self.event_rect.top(), self.event_rect.width(), self.event_rect.height()), False)
		self.selectionChanged()
		return False

	def queryEPG(self, list, buildFunc=None):
		if self.epgcache is not None:
			if buildFunc is not None:
				return self.epgcache.lookupEvent(list, buildFunc)
			else:
				return self.epgcache.lookupEvent(list)
		return [ ]

	def fillVIXEPG(self, services, stime=-1):
		if services is None:
			time_base = self.time_base+self.offs*self.time_epoch*60
			test = [ (service[0], 0, time_base, self.time_epoch) for service in self.list ]
		else:
			self.cur_event = None
			self.cur_service = None
			self.time_base = int(stime)
			test = [ (service.ref.toString(), 0, self.time_base, self.time_epoch) for service in services ]
		test.insert(0, 'XRnITBD')
		epg_data = self.queryEPG(test)
		self.list = [ ]
		tmp_list = None
		service = ""
		sname = ""
		for x in epg_data:
			if service != x[0]:
				if tmp_list is not None:
					self.list.append((service, sname, tmp_list[0][0] is not None and tmp_list or None))
				service = x[0]
				sname = x[1]
				tmp_list = [ ]
			tmp_list.append((x[2], x[3], x[4], x[5]))
		if tmp_list and len(tmp_list):
			self.list.append((service, sname, tmp_list[0][0] is not None and tmp_list or None))

		self.l.setList(self.list)
		self.findBestEvent()

	def getEventRect(self):
		rc = self.event_rect
		return Rect( rc.left() + (self.instance and self.instance.position().x() or 0), rc.top(), rc.width(), rc.height() )

	def getTimeEpoch(self):
		return self.time_epoch

	def getTimeBase(self):
		return self.time_base + (self.offs * self.time_epoch * 60)

	def resetOffset(self):
		self.offs = 0



	def VIXEPGRecRed(self, refstr, beginTime, duration, eventId):
#		for x in self.timer.timer_list:
#			if x.service_ref.ref.toString() == refstr:
#				if x.eit == eventId:
#					if x.justplay:
#						return "justplay"
#					else:
#						return "record"
#		return "nichts"
		pre_clock = 1
		post_clock = 2
		clock_type = 0
		endTime = beginTime + duration
		for x in self.timer.timer_list:
			if x.service_ref.ref.toString() == refstr:
				if x.eit == eventId:
					return "record"
				beg = x.begin
				end = x.end
				if beginTime > beg and beginTime < end and endTime > end:
					clock_type |= pre_clock
				elif beginTime < beg and endTime > beg and endTime < end:
					clock_type |= post_clock
		if clock_type == 0:
			return "record"
		elif clock_type == pre_clock:
			return "nichts"
		elif clock_type == post_clock:
			return "nichts"
		else:
			return "nichts"


class TimelineText(HTMLComponent, GUIComponent):
	def __init__(self):
		GUIComponent.__init__(self)
		self.l = eListboxPythonMultiContent()
		self.l.setSelectionClip(eRect(0,0,0,0))
		self.l.setItemHeight(25);
		self.l.setFont(0, gFont("Regular", config.plugins.VIXEPG.Timeline.value))

	GUI_WIDGET = eListbox

	def postWidgetCreate(self, instance):
		instance.setContent(self.l)

	def setEntries(self, entries):
		res = [ None ] # no private data needed
		hilfheute = localtime()
		hilfentry = localtime(entries[0][0])
#		if hilfheute[0] == hilfentry[0] and hilfheute[1] == hilfentry[1] and hilfheute[2] == hilfentry[2]:
#			hilf3 = ""
#		else:
#			hilf = hilfentry[6]
#			hilf3 = (_("Mon"), _("Tue"), _("Wed"), _("Thu"), _("Fri"), _("Sat"), _("Sun"))[hilf]
#		
#		res.append((eListboxPythonMultiContent.TYPE_TEXT, 30, 0, 60, 25, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, hilf3))

		for x in entries:
			tm = x[0]
			xpos = x[1]
			str = strftime("%H:%M", localtime(tm))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, xpos-30, 0, 60, 25, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str))
		self.l.setList([res])

class SingleEPG(EPGSelection):
	def __init__(self, session, service, zapFunc=None, bouquetChangeCB=None, serviceChangeCB=None):
		EPGSelection.__init__(self, session, service, zapFunc, bouquetChangeCB, serviceChangeCB)
		self.skinName = "EPGSelection"


class VIXEPG(Screen):
	EMPTY = 0
	ADD_TIMER = 1
	REMOVE_TIMER = 2
	ZAP = 1
	
	def __init__(self, session, services, zapFunc=None, bouquetChangeCB=None, bouquetname=""):
		Screen.__init__(self, session)
		Wide = getDesktop(0).size().width()
		skinpath = str(resolveFilename(SCOPE_CURRENT_SKIN))
		if config.plugins.VIXEPG.PIG.value == "No":
			if pathExists(skinpath + 'VIXEPG/Normal.xml'):
				skin = skinpath + 'VIXEPG/Normal.xml'
			else:
				if Wide == 720:
					skin = "/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/VIXEPG/skins/Normal_720.xml"
				if Wide == 1024:
					skin = "/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/VIXEPG/skins/Normal_1024.xml"
				if Wide == 1280:
					skin = "/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/VIXEPG/skins/Normal_1280.xml"
		elif config.plugins.VIXEPG.PIG.value == "Yes":
			if pathExists(skinpath + 'VIXEPG/PictureInGraphics.xml'):
				skin = skinpath + 'VIXEPG/PictureInGraphics.xml'
			else:
				if Wide == 720:
					skin = "/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/VIXEPG/skins/PictureInGraphics_720.xml"
				if Wide == 1024:
					skin = "/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/VIXEPG/skins/PictureInGraphics_1024.xml"
				if Wide == 1280:
					skin = "/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/VIXEPG/skins/PictureInGraphics_1280.xml"

		f = open(skin, "r")
		self.skin = f.read()
		f.close()
		self.bouquetChangeCB = bouquetChangeCB
		now = time()
		tmp = now % 900
		self.ask_time = now - tmp
		self.closeRecursive = False
		self.key_red_choice = self.EMPTY
		self.key_green_choice = self.EMPTY
		self.key_yellow_choice = self.EMPTY
		self.key_blue_choice = self.EMPTY
		self['lab1'] = Label()
		self["timeline_text"] = TimelineText()
		self["Event"] = Event()
		self.time_lines = [ ]
		for x in (0,1,2,3,4,5):
			pm = Pixmap()
			self.time_lines.append(pm)
			self["timeline%d"%(x)] = pm
		self["timeline_now"] = Pixmap()
		self.services = services
		self.zapFunc = zapFunc
		if bouquetname != "":
			Screen.setTitle(self, bouquetname)
		global VIXEPGList
		self["list"] = VIXEPGEPGList(selChangedCB = self.onSelectionChanged, timer = self.session.nav.RecordTimer,
					time_epoch = config.plugins.VIXEPG.prev_time_period.value,
					overjump_empty = config.plugins.VIXEPG.overjump.value)

		VIXEPGList = self["list"]
		self["main_actions"] = HelpableActionMap(self, "VIXEPGActions",
			{
				"Menu":			(self.showSetup,	_("show your Setup")),
				"Time":			(self.enterDateTime,	_("show Date Time")),
				"Red":			self.IMDbSearch,
				"Green":		self.timerAdd,
				"Yellow":		self.Search,
				"Blue":			self.AutoTimer,
				"OK":			self.OK,
				"OKLong":		self.OKLong,
				"Info":			self.Info,
				"InfoLong":		self.InfoLong,
				"Record":		(self.Record,	_("Record")),
			})

		self["actions"] = ActionMap(["EPGSelectActions", "OkCancelActions", "HelpActions"],
			{
				"cancel": self.VIXEPGClose,
				"displayHelp": self.myhelp,
				"nextBouquet": self.nextPressed,
				"prevBouquet": self.prevPressed,
				"prevService": self.nextBouquet,
				"nextService": self.prevBouquet,
			})
		self["actions"].csel = self

		self["input_actions"] = ActionMap(["InputActions"],
			{
				"left": self.leftPressed,
				"right": self.rightPressed,
				"1": self.key1,
				"2": self.key2,
				"3": self.key3,
				"4": self.key4,
				"5": self.key5,
				"6": self.key6,
				"7": self.key7,
				"8": self.key8,
				"9": self.key9,
				"0": self.key0,
			},-1)

		self["key_red"] = Button("IMDb Search")
		self["key_green"] = Button("")
		self["key_yellow"] = Button("Search")
		self["key_blue"] = Button("Add AutoTimer")
		self["date"] = Label()
		self.updateTimelineTimer = eTimer()
		self.updateTimelineTimer.callback.append(self.moveTimeLines)
		self.updateTimelineTimer.start(60*1000)
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.onCreate)
		self.updateList()
#		self.onLayoutFinish.append(self.updateList)

	def updateList(self):
		scanning = 'Wait please while gathering data...'
		self['lab1'].setText(scanning)
		self.activityTimer.start(750)

	#just used in multipeg
	def onCreate(self):
		self.activityTimer.stop()
		self["list"].curr_refcool = self.session.nav.getCurrentlyPlayingServiceReference()
		self["list"].fillVIXEPG(self.services, self.ask_time)
		self["list"].moveToService(self.session.nav.getCurrentlyPlayingServiceReference())
		self.moveTimeLines()
		if config.plugins.VIXEPG.channel1.value == "Yes":
			self["list"].instance.moveSelectionTo(0)
		self['lab1'].hide()


	def OpenSingleEPG(self):
		cur = self["list"].getCurrent()
		event = cur[0]
		serviceref = cur[1]
		refstr = serviceref.ref.toString()
		if event is not None:
			self.session.open(SingleEPG, refstr)		

	def AutoTimer(self):
		try:
			cur = self["list"].getCurrent()
			event = cur[0]
			if not event: return
			serviceref = cur[1]
			addAutotimerFromEvent(self.session, evt = event, service = serviceref)
		except:
			self.session.open(MessageBox, _("The AutoTimer plugin is not installed!\nPlease install it."), type = MessageBox.TYPE_INFO,timeout = 10 )

	def Record(self):
		cur = self["list"].getCurrent()
		event = cur[0]
		serviceref = cur[1]
		if event is None:
			return
		eventid = event.getEventId()
		refstr = serviceref.ref.toString()
		for timer in self.session.nav.RecordTimer.timer_list:
			if timer.eit == eventid and timer.service_ref.ref.toString() == refstr:
				self.removeTimer(timer)
				self["list"].fillVIXEPG(None)
				break
		else:
			newEntry = RecordTimerEntry(serviceref, checkOldTimers = True, *parseEvent(event))
			self.session.openWithCallback(self.finishedAdd, RecordSetup, newEntry)

	def Search(self):
		try:
			try:
				cur = self["list"].getCurrent()
				event = cur[0]
				name = event.getEventName()
			except:
				name = ''
			self.session.open(EPGSearch, name, False)
		except:
			self.session.open(MessageBox, _("The EPGSearch plugin is not installed!\nPlease install it."), type = MessageBox.TYPE_INFO,timeout = 10 )

	def IMDbSearch(self):
		try:
			try:
				cur = self["list"].getCurrent()
				event = cur[0]
				name = event.getEventName()
			except:
				name = ''
			self.session.open(IMDB, name, False)
		except:
			self.session.open(MessageBox, _("The IMDb plugin is not installed!\nPlease install it."), type = MessageBox.TYPE_INFO,timeout = 10 )

	def prevPressed(self):
		coolhilf = config.plugins.VIXEPG.prev_time_period.value
		if coolhilf == 60:
			for i in range(24):
				self.updEvent(-2)
		if coolhilf == 120:
			for i in range(12):
				self.updEvent(-2)
		if coolhilf == 180:
			for i in range(8):
				self.updEvent(-2)
		if coolhilf == 240:
			for i in range(6):
				self.updEvent(-2)
		if coolhilf == 300:
			for i in range(4):
				self.updEvent(-2)

	def nextPressed(self):
		coolhilf = config.plugins.VIXEPG.prev_time_period.value	
		if coolhilf == 60:
			for i in range(24):
				self.updEvent(+2)
		if coolhilf == 120:
			for i in range(12):
				self.updEvent(+2)
		if coolhilf == 180:
			for i in range(8):
				self.updEvent(+2)
		if coolhilf == 240:
			for i in range(6):
				self.updEvent(+2)
		if coolhilf == 300:
			for i in range(4):
				self.updEvent(+2)

	def leftPressed(self):
		self.updEvent(-1)

	def rightPressed(self):
		self.updEvent(+1)
		
	def updEvent(self, dir, visible=True):
		ret = self["list"].selEntry(dir, visible)
		if ret:
			self.moveTimeLines(True)		

	def myhelp(self):
		self.session.open(VIXEPGHelp, "/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/VIXEPG/help.jpg")

	def key1(self):
		hilf = config.plugins.VIXEPG.prev_time_period.value	
		if hilf > 60:
			hilf = hilf - 60
			self["list"].setEpoch(hilf)
			config.plugins.VIXEPG.prev_time_period.value = hilf
			self.moveTimeLines()

	def key2(self):
		self["list"].instance.moveSelection(self["list"].instance.pageUp)

	def key3(self):
		hilf = config.plugins.VIXEPG.prev_time_period.value	
		if hilf < 300:
			hilf = hilf + 60
			self["list"].setEpoch(hilf)
			config.plugins.VIXEPG.prev_time_period.value = hilf
			self.moveTimeLines()

	def key4(self):
		self.updEvent(-2)

	def key5(self):
		self["list"].instance.moveSelectionTo(0)
		now = time()
		tmp = now % 900
		cooltime = now - tmp
		self["list"].resetOffset()
		self["list"].fillVIXEPG(self.services, cooltime)
		self.moveTimeLines(True)

	def key6(self):
		self.updEvent(+2)

	def key7(self):
		EPGheight = getDesktop(0).size().height()
		VIXEPGman = (VIXEPGEPGheight / config.plugins.VIXEPG.items_per_page.value)
		if self["list"].coolheight == VIXEPG16:
			self["list"].coolheight = VIXEPGman
		else:
			self["list"].coolheight = VIXEPG16
		self["list"].l.setItemHeight(int(self["list"].coolheight))
		self["list"].fillVIXEPG(None)
		self.moveTimeLines()

	def key8(self):
		self["list"].instance.moveSelection(self["list"].instance.pageDown)

	def key9(self):
		cooltime = localtime(self["list"].getTimeBase())
		hilf = (cooltime[0], cooltime[1], cooltime[2], config.plugins.VIXEPG.Primetime1.value, config.plugins.VIXEPG.Primetime2.value,0, cooltime[6], cooltime[7], cooltime[8])
		cooltime = mktime(hilf)
		self["list"].resetOffset()
		self["list"].fillVIXEPG(self.services, cooltime)
		self.moveTimeLines(True)		

	def key0(self):
		self["list"].setEpoch2(180)
		config.plugins.VIXEPG.prev_time_period.value = 180
		self["list"].instance.moveSelectionTo(0)	
		now = time()
		tmp = now % 900
		cooltime = now - tmp
		self["list"].resetOffset()
		self["list"].fillVIXEPG(self.services, cooltime)
		self.moveTimeLines(True)

	def OK(self):
		if config.plugins.VIXEPG.OK.value == "Zap":
			self.zapTo()
		if config.plugins.VIXEPG.OK.value == "Zap + Exit":
			self.zap()

	def OKLong(self):
		if config.plugins.VIXEPG.OKLong.value == "Zap":
			self.zapTo()
		if config.plugins.VIXEPG.OKLong.value == "Zap + Exit":
			self.zap()

	def Info(self):
		if config.plugins.VIXEPG.Info.value == "Channel Info":
			self.infoKeyPressed()
		if config.plugins.VIXEPG.Info.value == "Single EPG":
			self.OpenSingleEPG()

	def InfoLong(self):
		if config.plugins.VIXEPG.InfoLong.value == "Channel Info":
			self.infoKeyPressed()
		if config.plugins.VIXEPG.InfoLong.value == "Single EPG":
			self.OpenSingleEPG()

	def nextBouquet(self):
		if self.bouquetChangeCB:
			self.bouquetChangeCB(1, self)

	def prevBouquet(self):
		if self.bouquetChangeCB:
			self.bouquetChangeCB(-1, self)

	def Bouquetlist(self):
		if self.bouquetChangeCB:
			self.bouquetChangeCB(0, self)

	def enterDateTime(self):
		self.session.openWithCallback(self.onDateTimeInputClosed, TimeDateInput, config.plugins.VIXEPG.prev_time )

	def onDateTimeInputClosed(self, ret):
		if len(ret) > 1:
			if ret[0]:
				self.ask_time=ret[1]
				l = self["list"]
				l.resetOffset()
				l.fillVIXEPG(self.services, ret[1])
				self.moveTimeLines(True)

	def showSetup(self):
		self.session.openWithCallback(self.onSetupClose, VIXEPGSetup )

	def onSetupClose(self):
		l = self["list"]
		l.setItemsPerPage()
		l.setEventFontsize()
		l.setServiceFontsize()
		l.setEpoch(config.plugins.VIXEPG.prev_time_period.value)
		l.setOverjump_Empty(config.plugins.VIXEPG.overjump.value)
		self.moveTimeLines()

	def VIXEPGClose(self):
		self.closeRecursive = True
		ref = self["list"].getCurrent()[1]
		if ref:
			self.closeScreen()		

	def closeScreen(self):
		config.plugins.VIXEPG.save()
		self.close(self.closeRecursive)

	def infoKeyPressed(self):
		cur = self["list"].getCurrent()
		event = cur[0]
		service = cur[1]
		if event is not None:
			self.session.open(EventViewSimple, event, service, self.eventViewCallback, self.openSimilarList)

	def openSimilarList(self, eventid, refstr):
		self.session.open(EPGSelection, refstr, None, eventid)

	def setServices(self, services):
		self.services = services
		self.onCreate()

	def eventViewCallback(self, setEvent, setService, val):
		l = self["list"]
		old = l.getCurrent()
		self.updEvent(val, False)
		cur = l.getCurrent()
		if cur[0] is None and cur[1].ref != old[1].ref:
			self.eventViewCallback(setEvent, setService, val)
		else:
			setService(cur[1])
			setEvent(cur[0])

	def zapTo(self):
		if self.zapFunc:
			self.closeRecursive = True
			ref = self["list"].getCurrent()[1]
			self["list"].curr_refcool = ref.ref
			self["list"].fillVIXEPG(None)
			if ref:
				self.zapFunc(ref.ref)
				
	def zap(self):
		if self.zapFunc :
			self.closeRecursive = True
			ref = self["list"].getCurrent()[1]
			if ref:
				self.zapFunc(ref.ref)
				self.closeScreen()

	def eventSelected(self):
		self.infoKeyPressed()

	def removeTimer(self, timer):
		timer.afterEvent = AFTEREVENT.NONE
		self.session.nav.RecordTimer.removeEntry(timer)
		self["key_green"].setText(_("Add timer"))
		self.key_green_choice = self.ADD_TIMER
	
	def timerAdd(self):
		cur = self["list"].getCurrent()
		event = cur[0]
		serviceref = cur[1]
		if event is None:
			return
		eventid = event.getEventId()
		refstr = serviceref.ref.toString()
		for timer in self.session.nav.RecordTimer.timer_list:
			if timer.eit == eventid and timer.service_ref.ref.toString() == refstr:
				cb_func = lambda ret : not ret or self.removeTimer(timer)
				self.session.openWithCallback(cb_func, MessageBox, _("Do you really want to delete %s?") % event.getEventName())
				break
		else:
			newEntry = RecordTimerEntry(serviceref, checkOldTimers = True, *parseEvent(event))
			self.session.openWithCallback(self.finishedAdd, TimerEntry, newEntry)

	def finishedAdd(self, answer):
		print "finished add"
		if answer[0]:
			entry = answer[1]
			simulTimerList = self.session.nav.RecordTimer.record(entry)
			if simulTimerList is not None:
				for x in simulTimerList:
					if x.setAutoincreaseEnd(entry):
						self.session.nav.RecordTimer.timeChanged(x)
				simulTimerList = self.session.nav.RecordTimer.record(entry)
				if simulTimerList is not None:
					self.session.openWithCallback(self.finishSanityCorrection, TimerSanityConflict, simulTimerList)
			self["key_green"].setText(_("Remove timer"))
			self.key_green_choice = self.REMOVE_TIMER
		else:
			self["key_green"].setText(_("Add timer"))
			self.key_green_choice = self.ADD_TIMER
			print "Timeredit aborted"
	
	def finishSanityCorrection(self, answer):
		self.finishedAdd(answer)

	def onSelectionChanged(self):
		cur = self["list"].getCurrent()
		if cur is None:
			if self.key_green_choice != self.EMPTY:
				self["key_green"].setText("")
				self.key_green_choice = self.EMPTY
			return
		
		event = cur[0]
		self["Event"].newEvent(event)

#apply	if self.type == EPG_TYPE_MULTI:
		count = self["list"].getCurrentChangeCount()
#		if self.ask_time != -1:
##			self.applyButtonState(0)
#		elif count > 1:
#			self.applyButtonState(3)
#		elif count > 0:
#			self.applyButtonState(2)
#		else:
#			self.applyButtonState(1)
		days = [ _("Mon"), _("Tue"), _("Wed"), _("Thu"), _("Fri"), _("Sat"), _("Sun") ]
		datestr = ""
		if event is not None:
			now = time()
			beg = event.getBeginTime()
			nowTime = localtime(now)
			begTime = localtime(beg)
			if nowTime[2] != begTime[2]:
				datestr = '%s'%(days[begTime[6]])
			else:
				datestr = '%s'%(_("Today"))
		self["date"].setText(datestr)
#		if cur[1] is None:
#			self["Service"].newService(None)
#		else:
#			self["Service"].newService(cur[1].ref)

		if cur[1] is None or cur[1].getServiceName() == "":
			if self.key_green_choice != self.EMPTY:
				self["key_green"].setText("")
				self.key_green_choice = self.EMPTY
			return

		if not event:
			if self.key_green_choice != self.EMPTY:
				self["key_green"].setText("")
				self.key_green_choice = self.EMPTY
			return
		
		serviceref = cur[1]
		eventid = event.getEventId()
		refstr = serviceref.ref.toString()
		isRecordEvent = False

		for timer in self.session.nav.RecordTimer.timer_list:
			if timer.eit == eventid and timer.service_ref.ref.toString() == refstr:
				isRecordEvent = True
				break
		if isRecordEvent and self.key_green_choice != self.REMOVE_TIMER:
			self["key_green"].setText(_("Remove timer"))
			self.key_green_choice = self.REMOVE_TIMER
		elif not isRecordEvent and self.key_green_choice != self.ADD_TIMER:
			self["key_green"].setText(_("Add timer"))
			self.key_green_choice = self.ADD_TIMER
	
	def moveTimeLines(self, force=False):
		self.updateTimelineTimer.start((60-(int(time())%60))*1000)	#keep syncronised
		l = self["list"]
		event_rect = l.getEventRect()
		time_epoch = l.getTimeEpoch()
		time_base = l.getTimeBase()
		if event_rect is None or time_epoch is None or time_base is None:
			return
		time_steps = time_epoch > 180 and 60 or 30
		
		num_lines = time_epoch/time_steps
		incWidth=event_rect.width()/num_lines
		pos=event_rect.left()
		timeline_entries = [ ]
		x = 0
		changecount = 0

		for line in self.time_lines:
			old_pos = line.position
			new_pos = (x == num_lines and event_rect.left()+event_rect.width() or pos, old_pos[1])
			if not x or x >= num_lines:
				line.visible = False
			else:
				if old_pos != new_pos:
					line.setPosition(new_pos[0], new_pos[1])
					changecount += 1
				line.visible = True
			if not x or line.visible:
				timeline_entries.append((time_base + x * time_steps * 60, new_pos[0]))
			x += 1
			pos += incWidth

		if changecount or force:
			self["timeline_text"].setEntries(timeline_entries)

		now=time()
		timeline_now = self["timeline_now"]
		if now >= time_base and now < (time_base + time_epoch * 60):
			xpos = int((((now - time_base) * event_rect.width()) / (time_epoch * 60))-(timeline_now.instance.size().width()/2))
			old_pos = timeline_now.position
			new_pos = (xpos+event_rect.left(), old_pos[1])
			if old_pos != new_pos:
				timeline_now.setPosition(new_pos[0], new_pos[1])
			timeline_now.visible = True
		else:
			timeline_now.visible = False

		l.l.invalidate()

		
class VIXEPGSetup(Screen, ConfigListScreen):
	skin = """
		<screen name="VIXEPGSetup" position="center,center" size="680,480" title="TV Guide Setup">
			<ePixmap pixmap="skin_default/buttons/red.png" position="20,5" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="185,5" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="350,5" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/blue.png" position="515,5" size="140,40" alphatest="on" />
			<widget name="canceltext" position="20,5" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget name="oktext" position="185,5" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
			<eLabel text="Standard for (HD), (XD), (SD) Skin" position="15,380" size="650,60" font="Regular;20" foregroundColor="#9f1313" backgroundColor="#000000" shadowColor="#000000" halign="center" transparent="1" />
			<eLabel text="Zap, Zap+Exit, Search, IMDb, VIXEPGSwitch, Channel Info, Timer" position="15,405" size="650,60" font="Regular;20" foregroundColor="#9f1313" backgroundColor="#000000" shadowColor="#000000" halign="center" transparent="1" />
			<eLabel text="QuickRec, AutoTimer, Primetime, Bouquet+, Bouquet-, Bouquetlist" position="15,430" size="650,60" font="Regular;20" foregroundColor="#9f1313" backgroundColor="#000000" shadowColor="#000000" halign="center" transparent="1" />
			<eLabel text="press ( left OK right ) to change your Buttons !!!" position="15,455" size="650,60" font="Regular;20" foregroundColor="#9f1313" backgroundColor="#000000" shadowColor="#000000" halign="center" transparent="1" />
			<widget name="config" position="20,60" size="640,298" />
		</screen>"""

	def __init__(self, session, args = None):
		Screen.__init__(self, session)
		self.setup_title = _("TV Guide Settings")
		self["actions"] = ActionMap(["SetupActions", "HelpActions"],
		{
			"ok": self.keySave,
			"save": self.keySave,
			"cancel": self.keyCancel,
			"red": self.keyCancel,
			"green": self.keySave,
			"displayHelp": self.myhelp,
		}, -1)

		self["oktext"] = Label(_("OK"))
		self["canceltext"] = Label(_("Cancel"))
		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("Save"))
		self.onChangedEntry = [ ]
		self.session = session
		self.list = []
		ConfigListScreen.__init__(self, self.list, session = self.session)
		self.createSetup()

	def myhelp(self):
		self.session.open(VIXEPGHelp, "/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/VIXEPG/help.jpg")

	def createSetup(self):
		print "Creating TV Guide Setup"
		self.list = [ ]
		self.list.append(getConfigListEntry(_("Info Button"), config.plugins.VIXEPG.Info))
		self.list.append(getConfigListEntry(_("Long Info Button"), config.plugins.VIXEPG.InfoLong))
		self.list.append(getConfigListEntry(_("OK Button"), config.plugins.VIXEPG.OK))
		self.list.append(getConfigListEntry(_("LongOK Button"), config.plugins.VIXEPG.OKLong))
		self.list.append(getConfigListEntry(_("Picture In Graphics (close EPG)"), config.plugins.VIXEPG.PIG))
		self.list.append(getConfigListEntry(_("Primetime hour"), config.plugins.VIXEPG.Primetime1))
		self.list.append(getConfigListEntry(_("Primetime minute"), config.plugins.VIXEPG.Primetime2))
		self.list.append(getConfigListEntry(_("Enable Picon"), config.plugins.VIXEPG.UsePicon))
		self.list.append(getConfigListEntry(_("Channel 1 at Start"), config.plugins.VIXEPG.channel1))
		self.list.append(getConfigListEntry(_("Start-Items 7-8 , 14-16"), config.plugins.VIXEPG.coolswitch))
		self.list.append(getConfigListEntry(_("Items per Page"), config.plugins.VIXEPG.items_per_page))
		self.list.append(getConfigListEntry(_("Event Fontsize"), config.plugins.VIXEPG.Fontsize))
		self.list.append(getConfigListEntry(_("Left Fontsize"), config.plugins.VIXEPG.Left_Fontsize))
		self.list.append(getConfigListEntry(_("Timeline Fontsize (restart plugin)"), config.plugins.VIXEPG.Timeline))
		self.list.append(getConfigListEntry(_("Left width Picon"), config.plugins.VIXEPG.left8))
		self.list.append(getConfigListEntry(_("Left width Text"), config.plugins.VIXEPG.left16))
		self.list.append(getConfigListEntry(_("Time Scale"), config.plugins.VIXEPG.prev_time_period))
		self.list.append(getConfigListEntry(_("Skip Empty Services (restart plugin)"), config.plugins.VIXEPG.overjump))
		self["config"].list = self.list
		self["config"].l.setList(self.list)

class VIXEPGHelp(Screen):
	if (getDesktop(0).size().width()) == 720:
		skin="""
			<screen flags="wfNoBorder" position="0,0" size="720,576" title="..Help.." backgroundColor="#ffffffff">
				<widget name="Picture" position="0,0" size="720,576" zPosition="1"/>
			</screen>"""	
	elif (getDesktop(0).size().width()) == 1024:
		skin="""
			<screen flags="wfNoBorder" position="0,0" size="1024,576" title="..Help.." backgroundColor="#ffffffff">
				<widget name="Picture" position="0,0" size="1024,576" zPosition="1"/>
			</screen>"""
	else:
		skin="""
			<screen flags="wfNoBorder" position="0,0" size="1280,720" title="..Help.." backgroundColor="#ffffffff">
				<widget name="Picture" position="0,0" size="1280,720" zPosition="1"/>
			</screen>"""

	def __init__(self, session, whatPic = None):
		self.skin = VIXEPGHelp.skin
		Screen.__init__(self, session)
		self.whatPic = whatPic
		self.EXscale = (AVSwitch().getFramebufferScale())
		self.EXpicload = ePicLoad()
		self["Picture"] = Pixmap()
		self["actions"] = ActionMap(["WizardActions", "ColorActions"],
		{
			"ok": self.close,
			"back": self.close,
			"red": self.close,
			"green": self.close
		}, -1)

		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("Save"))
		self.EXpicload.PictureData.get().append(self.DecodeAction)
		self.onLayoutFinish.append(self.Help_Picture)

	def Help_Picture(self):
		if self.whatPic is not None:
			self.EXpicload.setPara([self["Picture"].instance.size().width(), self["Picture"].instance.size().height(), self.EXscale[0], self.EXscale[1], 0, 1, "#121214"])
			self.EXpicload.startDecode(self.whatPic)

	def DecodeAction(self, pictureInfo=" "):
		if self.whatPic is not None:
			ptr = self.EXpicload.getData()
			self["Picture"].instance.setPixmap(ptr)

#!/usr/bin/python -tt
# -*- coding: iso-8859-1 -*-
#    Yum Exteder (yumex) - A GUI for yum
#    Copyright (C) 2006 Tim Lauridsen < tim<AT>yum-extender<DOT>org > 
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import gtk
import gobject
import pango

# Use iniparse if it exist, else use Python ConfigParser
try:
    from iniparse.compat import ConfigParser,SafeConfigParser
except:
    from ConfigParser import ConfigParser,SafeConfigParser


from misc import const,cleanMarkupSting,YumexConf
from i18n import _

class ConfimationDialog:
    def __init__( self, parent, pkgs, top_text = None, bottom_text = None, bottom_data = None ):

        self.xml = gtk.glade.XML( const.GLADE_FILE, 'confirmation',domain="yumex" )
        self.dialog = self.xml.get_widget( "confirmation" )
        self.dialog.set_transient_for( parent )
        self.action = self.xml.get_widget( "confAction" )
        self.bottomTitle = self.xml.get_widget( "bottomTitle" )
        self.bottomData = self.xml.get_widget( "bottomData" )

        # setup text
        if top_text == None:
            top_text = _("Please confirm the actions above")

        tit = "<span size='x-large'>%s</span>" % (top_text,)
        self.action.set_markup( tit )
        if bottom_text != None: self.bottomTitle.set_markup( bottom_text )
        if bottom_data != None: self.bottomData.set_text( bottom_data )

        self.pkgs = pkgs
        self.pkg = self.xml.get_widget( "confPkg" )
        self.pkgModel = self.setup_view( self.pkg )
        self.show_data( self.pkgModel, pkgs )
        self.pkg.expand_all()

    def run( self ):
        self.dialog.show_all()
        return self.dialog.run()

    def setup_view( self, view ):
        model = gtk.TreeStore( gobject.TYPE_STRING, gobject.TYPE_STRING )
        view.set_model( model )
        self.create_text_column( _( "Package" ), view, 0 )
        self.create_text_column( _( "Description" ), view, 1 )
        return model

    def create_text_column( self, hdr, view, colno, min_width=0 ):
         cell = gtk.CellRendererText()    # Size Column
         column = gtk.TreeViewColumn( hdr, cell, markup=colno )
         column.set_resizable( True )
         if not min_width == 0:
             column.set_min_width( min_width )
         view.append_column( column )


    def show_data( self, model, pkgs ):
        model.clear()
        for pkg in pkgs:
            label = "<b>%s</b>" % str(pkg)
            model.append( None, [label, pkg.description] )

    def show_data( self, model, pkgs ):
        model.clear()
        install = [x for x in pkgs if x.action == "i"]
        update = [x for x in pkgs if x.action == "u"]
        remove = [x for x in pkgs if x.action == "r"]
        # install
        if install:
            label = "<b>%s</b>" % _("To be installed")
            level1 = model.append( None, [label, " "] )
            for pkg in install:
                desc = pkg.description
                if not desc.strip():
                    desc = _("No description")
                level2 = model.append( level1, [str(pkg), desc ] )
        if update:
            label = "<b>%s</b>" % _("To be updated")
            level1 = model.append( None, [label, " "] )
            for pkg in update:
                level2 = model.append( level1, [str(pkg), pkg.description] )
        if remove:
            label = "<b>%s</b>" % _("To be removed")
            level1 = model.append( None, [label, " "] )
            for pkg in remove:
                level2 = model.append( level1, [str(pkg), pkg.description] )

    def destroy( self ):
        return self.dialog.destroy()

class ErrorDialog:
    def __init__( self, parent, title, text, longtext, modal ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "errDialog",domain="yumex" )
        self.dialog = self.xml.get_widget( "errDialog" )
        self.parent = parent
        if parent:
            self.dialog.set_transient_for( parent )
        #self.dialog.set_icon_name( 'gtk-dialog-error' )
        self.dialog.set_title( title )
        self.text = self.xml.get_widget( "errText" )
        self.longtext = self.xml.get_widget( "errTextView" )
        self.style_err = gtk.TextTag( "error" ) 
        self.style_err.set_property( "style", pango.STYLE_ITALIC )
        self.style_err.set_property( "foreground", "red" )
        self.style_err.set_property( "family", "Monospace" )
        self.style_err.set_property( "size_points", 8 )
        self.longtext.get_buffer().get_tag_table().add( self.style_err )
        
        if modal:
            self.dialog.set_modal( True )
        if text != "":
            self.set_text( text )
        if longtext != "" and longtext != None:
            self.set_long_text( longtext )
        
    def set_text( self, text ):
        self.text.set_markup( text )
    
    def set_long_text( self, longtext ):
        buffer = self.longtext.get_buffer()
        start, end = buffer.get_bounds()
        buffer.insert_with_tags( end, longtext, self.style_err )
        
    def run( self ):
        self.dialog.show_all()
        return self.dialog.run()

    def destroy( self ):
        return self.dialog.destroy()  

class infoDialog:
    def __init__( self, parent, title, text ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "msg",domain="yumex" )
        self.dialog = self.xml.get_widget( "msg" )
        self.parent = parent
        self.dialog.set_transient_for( parent )
        #self.dialog.set_icon_name( 'gtk-dialog-error' )
        self.dialog.set_title( title )
        self.text = self.xml.get_widget( "msgText" )
        self.dialog.set_modal( True )
        self.set_text( text )

    def set_text( self, text ):
        self.text.set_markup( "<span size='large'>%s</span>" % text )

    def run( self ):
        self.dialog.show_all()
        return self.dialog.run()

    def destroy( self ):
        return self.dialog.destroy() 


class EntryDialog:
    def __init__( self, parent, title, text ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "EntryDialog",domain="yumex" )
        self.dialog = self.xml.get_widget( "EntryDialog" )
        self.parent = parent
        #self.dialog.set_transient_for( parent )
        #self.dialog.set_icon_name( 'gtk-dialog-error' )
        self.dialog.set_title( title )
        self.text = self.xml.get_widget( "inputLabel" )
        self.entry = self.xml.get_widget( "inputEntry" )
        self.dialog.set_modal( True )
        self.text.set_text( text )

    def run( self ):
        self.dialog.show_all()
        rc = self.dialog.run()
        if rc == gtk.RESPONSE_OK:
            return self.entry.get_text()
        else:
            return None
    
    def destroy( self ):
        return self.dialog.destroy()  

class AboutDialog(gtk.Window):

    """ Class for a fancy "About" dialog. 
        Mostly ripped from the one in gDesklets 
    """

    def __init__(self, gfx,creditText,title="Spritz Package Manager"):

        self.__is_stopped = True
        self.__scroller_values = ()


        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_resizable(False)
        self.set_title(_("About %s") % title)
        self.connect("button-press-event", self.__on_close)
        self.connect("key-press-event", self.__on_close)
        self.connect("delete-event", self.__on_close)
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)

        fixed = gtk.Fixed()
        self.add(fixed)

        img = gtk.Image()
        img.set_from_file(gfx)
        fixed.put(img, 0, 0)

        width, height = img.size_request()

        scroller = gtk.Fixed()
        scroller.set_size_request(width, height - 32)
        fixed.put(scroller, 0, 32)

        text = ""
        for header, body in creditText:
            text += "<b>" + header + "</b>\n\n"
            text += "\n".join(body)
            text += "\n\n\n\n"
        text = "<big>" + text.strip() + "</big>"

        credits = gtk.Label(text)
        credits.set_use_markup(True)
        credits.set_justify(gtk.JUSTIFY_CENTER)

        lbl_width, lbl_height = credits.size_request()
        scroller.put(credits, (width - lbl_width) / 2, height)

        self.__scroller = scroller
        self.__credits = credits

        self.__scroller_values = (height - 32, -lbl_height,
                                  (width - lbl_width) / 2)


    def __scroll(self, ycoord):

        begin, end, xcoord = self.__scroller_values
        self.__scroller.move(self.__credits, xcoord, ycoord)
        ycoord -= 1

        if (ycoord < end):
            ycoord = begin

        if (not self.__is_stopped):
            gobject.timeout_add(50, self.__scroll, ycoord)

        return False


    def __on_close(self, *args):

        self.__is_stopped = True
        self.hide()
        return True


    def show(self):

        if (not self.__is_stopped):
            return

        self.show_all()

        self.__is_stopped = False
        begin, end, xcoord = self.__scroller_values
        gobject.timeout_add(0, self.__scroll, begin)


def inputBox( parent, title, text, input_text = None):
    dlg = EntryDialog( parent, title, text)
    if input_text:
        dlg.entry.set_text(input_text)
    rc = dlg.run()
    dlg.destroy()
    return rc

def errorMessage( parent, title, text, longtext=None, modal= True ):
     dlg = ErrorDialog( parent, title, text, longtext, modal )
     dlg.run()
     dlg.destroy()

def infoMessage( parent, title, text ):
    dlg = infoDialog( parent, title, text )
    rc = dlg.run()
    dlg.destroy()
    return not rc == gtk.RESPONSE_OK

def questionDialog(parent, msg, message_format = _("Hey!")):
    dlg = gtk.MessageDialog(parent=parent,
                            type=gtk.MESSAGE_QUESTION,
                            buttons=gtk.BUTTONS_YES_NO, message_format = message_format)
    dlg.set_title( _("Spritz Question") )
    dlg.format_secondary_markup(cleanMarkupSting(msg))
    rc = dlg.run()
    dlg.destroy()
    if rc == gtk.RESPONSE_YES:
        return True
    else:
        return False

def okDialog(parent, msg):
    dlg = gtk.MessageDialog(parent=parent,
                            type=gtk.MESSAGE_INFO,
                            buttons=gtk.BUTTONS_OK)
    dlg.set_markup(cleanMarkupSting(msg))
    dlg.set_title( _("Attention") )
    rc = dlg.run()
    dlg.destroy()
    

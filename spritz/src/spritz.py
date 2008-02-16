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

# Base Python Imports
import sys, os, pty
import logging
import traceback
import commands

# Entropy Imports
sys.path.insert(0,"../../libraries")
sys.path.insert(1,"../../client")
sys.path.insert(2,"/usr/lib/entropy/libraries")
sys.path.insert(3,"/usr/lib/entropy/client")
from entropyConstants import *
import exceptionTools
from packages import EntropyPackages
from entropyapi import EquoConnection,QueueExecutor

# GTK Imports
import gtk,gobject
from threading import Thread,Event
import thread
import exceptions
from etpgui.widgets import UI, Controller
from etpgui import *


# yumex imports
import filters
from gui import SpritzGUI
from dialogs import *
from misc import const, SpritzOptions, fakeoutfile, fakeinfile
from i18n import _
import time


class SpritzController(Controller):
    ''' This class contains all glade signal callbacks '''


    def __init__( self ):
        self.etpbase = EntropyPackages(EquoConnection)
        # Create and ui object contains the widgets.
        ui = UI( const.GLADE_FILE , 'main', 'yumex' )
        addrepo_ui = UI( const.GLADE_FILE , 'addRepoWin', 'yumex' )
        pkginfo_ui = UI( const.GLADE_FILE , 'pkgInfo', 'yumex' )
        # init the Controller Class to connect signals.
        Controller.__init__( self, ui, addrepo_ui, pkginfo_ui )

        self.clipboard = gtk.Clipboard()
        self.pty = pty.openpty()
        self.output = fakeoutfile(self.pty[1])
        self.input = fakeinfile(self.pty[1])
        #sys.stdout = self.output
        #sys.stderr = self.output
        #sys.stdin = self.input


    def quit(self, widget=None, event=None ):
        ''' Main destroy Handler '''
        gtkEventThread.doQuit()
        if self.isWorking:
            self.quitNow = True
            self.logger.critical(_('Quiting, please wait !!!!!!'))
            time.sleep(3)
            self.exitNow()
            return False
        else:
            self.exitNow()
            return False

    def exitNow(self):
        try:
            gtk.main_quit()       # Exit gtk
        except RuntimeError,e:
            pass
        sys.exit( 1 )         # Terminate Program

    def __getSelectedRepoIndex( self ):
        selection = self.repoView.view.get_selection()
        repodata = selection.get_selected()
        # get text
        if repodata[1] != None:
            repoid = self.repoView.get_repoid(repodata)
            # do it if it's enabled
            if repoid in etpRepositoriesOrder:
                idx = etpRepositoriesOrder.index(repoid)
                return idx, repoid, repodata
        return None, None, None

    def runEditor(self, filename, delete = False):
        cmd = ' '.join([self.fileEditor,filename])
        task = self.Equo.entropyTools.parallelTask(self.__runEditor, {'cmd': cmd, 'delete': delete,'file': filename})
        task.start()

    def __runEditor(self, data):
        os.system(data['cmd']+"&> /dev/null")
        delete = data['delete']
        if delete and os.path.isfile(data['file']):
            try:
                os.remove(data['file'])
            except OSError:
                pass

    def __get_Edit_filename(self):
        selection = self.filesView.view.get_selection()
        model, iterator = selection.get_selected()
        if model != None and iterator != None:
            identifier = model.get_value( iterator, 0 )
            destination = model.get_value( iterator, 2 )
            source = model.get_value( iterator, 1 )
            source = os.path.join(os.path.dirname(destination),source)
            return identifier, source, destination
        return 0,None,None

    def on_filesDelete_clicked( self, widget ):
        identifier, source, dest = self.__get_Edit_filename()
        if not identifier:
            return True
        self.Equo.FileUpdates.remove_file(identifier)
        self.filesView.populate(self.Equo.FileUpdates.scandata)

    def on_filesMerge_clicked( self, widget ):
        identifier, source, dest = self.__get_Edit_filename()
        if not identifier:
            return True
        self.Equo.FileUpdates.merge_file(identifier)
        self.filesView.populate(self.Equo.FileUpdates.scandata)

    def on_mergeFiles_clicked( self, widget ):
        self.Equo.FileUpdates.scanfs(dcache = True)
        keys = self.Equo.FileUpdates.scandata.keys()
        for key in keys:
            self.Equo.FileUpdates.merge_file(key)
            # it's cool watching it runtime
            self.filesView.populate(self.Equo.FileUpdates.scandata)

    def on_deleteFiles_clicked( self, widget ):
        self.Equo.FileUpdates.scanfs(dcache = True)
        keys = self.Equo.FileUpdates.scandata.keys()
        for key in keys:
            self.Equo.FileUpdates.remove_file(key)
            # it's cool watching it runtime
            self.filesView.populate(self.Equo.FileUpdates.scandata)

    def on_filesEdit_clicked( self, widget ):
        identifier, source, dest = self.__get_Edit_filename()
        if not identifier:
            return True
        self.runEditor(source)

    def on_filesViewChanges_clicked( self, widget ):
        identifier, source, dest = self.__get_Edit_filename()
        if not identifier:
            return True
        randomfile = self.Equo.entropyTools.getRandomTempFile()+".diff"
        diffcmd = "diff -Nu "+dest+" "+source+" > "+randomfile
        os.system(diffcmd)
        self.runEditor(randomfile, delete = True)

    def on_switchBranch_clicked( self, widget ):
        branch = inputBox(self.ui.main, _("Branch switching"), _("Enter a valid branch you want to switch to")+"     ", input_text = etpConst['branch'])
        branches = self.Equo.listAllAvailableBranches()
        if branch not in branches:
            okDialog( self.ui.main, _("The selected branch is not available.") )
        else:
            self.Equo.move_to_branch(branch)
            okDialog( self.ui.main, _("New branch is %s. It is suggested to synchronize repositories.") % (etpConst['branch'],) )

    def on_shiftUp_clicked( self, widget ):
        idx, repoid, iterdata = self.__getSelectedRepoIndex()
        if idx != None:
            path = iterdata[0].get_path(iterdata[1])[0]
            if path > 0 and idx > 0:
                idx -= 1
                self.Equo.shiftRepository(repoid, idx)
                # get next iter
                prev = iterdata[0].get_iter(path-1)
                self.repoView.store.swap(iterdata[1],prev)

    def on_shiftDown_clicked( self, widget ):
        idx, repoid, iterdata = self.__getSelectedRepoIndex()
        if idx != None:
            next = iterdata[0].iter_next(iterdata[1])
            if next:
                idx += 1
                self.Equo.shiftRepository(repoid, idx)
                self.repoView.store.swap(iterdata[1],next)

    def on_mirrorDown_clicked( self, widget ):
        selection = self.repoMirrorsView.view.get_selection()
        urldata = selection.get_selected()
        # get text
        if urldata[1] != None:
            next = urldata[0].iter_next(urldata[1])
            if next:
                self.repoMirrorsView.store.swap(urldata[1],next)

    def on_mirrorUp_clicked( self, widget ):
        selection = self.repoMirrorsView.view.get_selection()
        urldata = selection.get_selected()
        # get text
        if urldata[1] != None:
            path = urldata[0].get_path(urldata[1])[0]
            if path > 0:
                # get next iter
                prev = urldata[0].get_iter(path-1)
                self.repoMirrorsView.store.swap(urldata[1],prev)

    def on_repoMirrorAdd_clicked( self, widget ):
        text = inputBox(self.addrepo_ui.addRepoWin, _("Insert URL"), _("Enter a download mirror, HTTP or FTP")+"   ")
        # call liststore and tell to add
        if text:
            # validate url
            if not (text.startswith("http://") or text.startswith("ftp://")):
                okDialog( self.addrepo_ui.addRepoWin, _("You must enter either a HTTP or a FTP url.") )
            else:
                self.repoMirrorsView.add(text)

    def on_repoMirrorRemove_clicked( self, widget ):
        selection = self.repoMirrorsView.view.get_selection()
        urldata = selection.get_selected()
        if urldata[1] != None:
            self.repoMirrorsView.remove(urldata)

    def on_repoMirrorEdit_clicked( self, widget ):
        selection = self.repoMirrorsView.view.get_selection()
        urldata = selection.get_selected()
        # get text
        if urldata[1] != None:
            text = self.repoMirrorsView.get_text(urldata)
            self.repoMirrorsView.remove(urldata)
            text = inputBox(self.addrepo_ui.addRepoWin, _("Insert URL"), _("Enter a download mirror, HTTP or FTP")+"   ", input_text = text)
            # call liststore and tell to add
            self.repoMirrorsView.add(text)

    def on_addRepo_clicked( self, widget ):
        self.addrepo_ui.repoSubmit.show()
        self.addrepo_ui.repoSubmitEdit.hide()
        self.addrepo_ui.repoInsert.show()
        self.addrepo_ui.repoidEntry.set_editable(True)
        self.addrepo_ui.repodbcformatEntry.set_active(0)
        self.addrepo_ui.repoidEntry.set_text("")
        self.addrepo_ui.repoDescEntry.set_text("")
        self.addrepo_ui.repodbEntry.set_text("")
        self.addrepo_ui.addRepoWin.show()
        self.repoMirrorsView.populate()

    def __loadRepodata(self, repodata):
        self.addrepo_ui.repoidEntry.set_text(repodata['repoid'])
        self.addrepo_ui.repoDescEntry.set_text(repodata['description'])
        self.repoMirrorsView.store.clear()
        for x in repodata['packages']:
            self.repoMirrorsView.add(x)
        idx = 0
        # XXX hackish way fix it
        while idx < 100:
            self.addrepo_ui.repodbcformatEntry.set_active(idx)
            if repodata['dbcformat'] == self.addrepo_ui.repodbcformatEntry.get_active_text():
                break
            idx += 1
        self.addrepo_ui.repodbEntry.set_text(repodata['database'])

    def on_repoSubmitEdit_clicked( self, widget ):
        repodata = self.__getRepodata()
        errors = self.__validateRepoSubmit(repodata, edit = True)
        if errors:
            okDialog( self.addrepo_ui.addRepoWin, _("Wrong entries, errors: %s") % (', '.join(errors),) )
            return True
        else:
            self.Equo.removeRepository(repodata['repoid'])
            self.Equo.addRepository(repodata)
            self.setupRepoView()
            self.addrepo_ui.addRepoWin.hide()
            okDialog( self.ui.main, _("You should press the %s button now") % (_("Regenerate Cache")) )

    def __validateRepoSubmit(self, repodata, edit = False):
        errors = []
        if not repodata['repoid']:
            errors.append(_('No Repository Identifier'))
        if repodata['repoid'] and etpRepositories.has_key(repodata['repoid']):
            if not edit:
                errors.append(_('Duplicated Repository Identifier'))
        if not repodata['description']:
            repodata['description'] = "No description"
        if not repodata['packages']:
            errors.append(_("No download mirrors"))
        if not repodata['database'] or not (repodata['database'].endswith("http://") or (not repodata['database'].endswith("ftp://"))):
            errors.append(_("Database URL must be HTTP or FTP"))
        return errors

    def __getRepodata(self):
        repodata = {}
        repodata['repoid'] = self.addrepo_ui.repoidEntry.get_text()
        repodata['description'] = self.addrepo_ui.repoDescEntry.get_text()
        repodata['packages'] = self.repoMirrorsView.get_all()
        repodata['dbcformat'] = self.addrepo_ui.repodbcformatEntry.get_active_text()
        repodata['database'] = self.addrepo_ui.repodbEntry.get_text()
        return repodata

    def on_repoSubmit_clicked( self, widget ):
        repodata = self.__getRepodata()
        # validate
        errors = self.__validateRepoSubmit(repodata)
        if not errors:
            self.Equo.addRepository(repodata)
            self.setupRepoView()
            self.addrepo_ui.addRepoWin.hide()
            okDialog( self.ui.main, _("You should now press the %s button now") % (_("Update Repositories"),) )
        else:
            okDialog( self.addrepo_ui.addRepoWin, _("Wrong entries, errors: %s") % (', '.join(errors),) )

    def on_addRepoWin_delete_event(self, widget, path):
        return True

    def on_repoCancel_clicked( self, widget ):
        self.addrepo_ui.addRepoWin.hide()

    def on_repoInsert_clicked( self, widget ):
        text = inputBox(self.addrepo_ui.addRepoWin, _("Insert Repository"), _("Insert Repository identification string")+"   ")
        if text:
            if (text.startswith("repository|")) and (len(text.split("|")) == 5):
                # filling dict
                textdata = text.split("|")
                repodata = {}
                repodata['repoid'] = textdata[1]
                repodata['description'] = textdata[2]
                repodata['packages'] = textdata[3].split()
                repodata['database'] = textdata[4].split("#")[0]
                dbcformat = textdata[4].split("#")[-1]
                if dbcformat in etpConst['etpdatabasesupportedcformats']:
                    repodata['dbcformat'] = dbcformat
                else:
                    repodata['dbcformat'] = etpConst['etpdatabasesupportedcformats'][0]
                # fill window
                self.__loadRepodata(repodata)
            else:
                okDialog( self.addrepo_ui.addRepoWin, _("This Repository identification string is malformed") )

    def on_removeRepo_clicked( self, widget ):
        # get selected repo
        selection = self.repoView.view.get_selection()
        repodata = selection.get_selected()
        # get text
        if repodata[1] != None:
            repoid = self.repoView.get_repoid(repodata)
            if repoid == etpConst['officialrepositoryid']:
                okDialog( self.ui.main, _("You! Why do you want to remove the main repository ?"))
                return True
            self.Equo.removeRepository(repoid)
            self.setupRepoView()
            okDialog( self.ui.main, _("You must now either press the %s or the %s button") % (_("Regenerate Cache"),_("Update Repositories")) )

    def on_repoEdit_clicked( self, widget ):
        self.addrepo_ui.repoSubmit.hide()
        self.addrepo_ui.repoSubmitEdit.show()
        self.addrepo_ui.repoInsert.hide()
        self.addrepo_ui.repoidEntry.set_editable(False)
        # get selection
        selection = self.repoView.view.get_selection()
        repostuff = selection.get_selected()
        if repostuff[1] != None:
            repoid = self.repoView.get_repoid(repostuff)
            repodata = self.Equo.entropyTools.getRepositorySettings(repoid)
            self.__loadRepodata(repodata)
            self.addrepo_ui.addRepoWin.show()

    def on_terminal_clear_activate(self, widget):
        self.output.text_written = []
        self.console.reset()

    def on_terminal_copy_activate(self, widget):
        self.clipboard.clear()
        self.clipboard.set_text(''.join(self.output.text_written))

    def on_PageButton_changed( self, widget, page ):
        ''' Left Side Toolbar Handler'''
        if page == "filesconf":
            self.populateFilesUpdate()
        self.setNotebookPage(const.PAGES[page])

    def on_category_selected(self,widget):
        ''' Category Change Handler '''
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            category = model.get_value( iterator, 1 )
            if category != '':
                self.addCategoryPackages(category)
            else:
                self.pkgView.store.clear()


    def on_Category_changed(self,widget):
        ''' Category Type Change Handler'''
        ndx = self.ui.cbCategory.get_active()
        if ndx == 0: # None
           self.categoryOn = False
           self.ui.swCategory.hide()
           self.addPackages()
        else:
           self.categoryOn = True
           self.ui.swCategory.show()
           tub = const.PACKAGE_CATEGORY_DICT[ndx]
           (label,fn,attr,sortcat,splitcat) = tub
           self.addCategories(fn,attr,sortcat,splitcat)

    def on_pkgFilter_toggled(self,rb,action):
        ''' Package Type Selection Handler'''
        if rb.get_active(): # Only act on select, not deselect.
            rb.grab_add()
            self.lastPkgPB = action
            # Only show add/remove all when showing updates
            if action == 'updates':
                self.ui.pkgSelect.show()
                self.ui.pkgDeSelect.show()
            else:
                self.ui.pkgSelect.hide()
                self.ui.pkgDeSelect.hide()

            self.addPackages()
            rb.grab_remove()

    def on_repoRefresh_clicked(self,widget):
        repos = self.repoView.get_selected()
        if not repos:
            okDialog( self.ui.main, _("Please select at least one repository") )
            return
        self.setPage('output')
        self.logger.info( "Enabled repositories : %s" % ",".join(repos))
        self.updateRepositories(repos)
        self.setupSpritz()

    def on_cacheButton_clicked(self,widget):
        repos = self.repoView.get_selected()
        self.setPage('output')
        self.logger.info( "Cleaning cache")
        self.cleanEntropyCaches(alone = True)

    def on_repoDeSelect_clicked(self,widget):
        self.repoView.deselect_all()


    def on_queueDel_clicked( self, widget ):
        """ Delete from Queue Button Handler """
        self.queueView.deleteSelected()

    def on_queueQuickAdd_activate(self,widget):
        txt = widget.get_text()
        arglist = txt.split(' ')
        self.doQuickAdd(arglist[0],arglist[1:])

    def on_queueProcess_clicked( self, widget ):
        """ Process Queue Button Handler """
        if self.queue.total() == 0: # Check there are any packages in the queue
            self.setStatus(_('No packages in queue'))
            return

        rc = self.processPackageQueue(self.queue.packages)
        if rc:
            if rc == 'QUIT':
                self.quit()
            else:
                self.queue.clear()       # Clear package queue
                self.queueView.refresh() # Refresh Package Queue

    def on_queueSave_clicked( self, widget ):
        dialog = gtk.FileChooserDialog(title=None,action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                  buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK))
        homedir = os.getenv('HOME')
        if not homedir:
            homedir = "/tmp"
        dialog.set_current_folder(homedir)
        dialog.set_current_name('queue.spritz')
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            fn = dialog.get_filename()
        elif response == gtk.RESPONSE_CANCEL:
            fn = None
        dialog.destroy()
        if fn:
            self.logger.info("Saving queue to %s" % fn)
            pkgdata = self.queue.get()
            keys = pkgdata.keys()
            for key in keys:
                if pkgdata[key]:
                    pkgdata[key] = [str(x) for x in pkgdata[key]]
            self.Equo.dumpTools.dumpobj(fn,pkgdata,True)

    def on_queueOpen_clicked( self, widget ):
        dialog = gtk.FileChooserDialog(title=None,action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                  buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        homedir = os.getenv('HOME')
        if not homedir:
            homedir = "/tmp"
        dialog.set_current_folder(homedir)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            fn = dialog.get_filename()
        elif response == gtk.RESPONSE_CANCEL:
            fn = None
        dialog.destroy()
        if fn:
            self.logger.info("Loading queue from %s" % fn)
            try:
                pkgdata = self.Equo.dumpTools.loadobj(fn,True)
            except:
                return

            try:
                pkgdata_keys = pkgdata.keys()
            except:
                return
            packages = self.etpbase.getAllPackages()
            collected_items = []
            for key in pkgdata_keys:
                for pkg in pkgdata[key]:
                    found = False
                    for x in packages:
                        if (pkg == str(x)) and (x.action == key):
                            found = True
                            collected_items.append([key,x])
                            break
                    if not found:
                        okDialog( self.ui.main, _("Queue is too old. Cannot load.") )
                        return

            for pkgtuple in collected_items:
                key = pkgtuple[0]
                pkg = pkgtuple[1]
                pkg.queued = key
                self.queue.packages[key].append(pkg)

            self.queueView.refresh()

    def on_pkg_doubleclick( self, widget, iterator, path ):
        """ Handle selection of row in package view (Show Descriptions) """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            pkg = model.get_value( iterator, 0 )
            if pkg:
                self.loadPkgInfoMenu(pkg)

    def loadPkgInfoMenu( self, pkg ):

        # set left LABELS
        

        # set atom
        self.pkginfo_ui.pkgatomLabel.set_markup("<b><big>%s</big></b>" % (pkg.name,))
        repo = pkg.matched_atom[1]
        if repo == 0:
            # from installed
            self.pkginfo_ui.pkgatomSublabel.set_markup("<small>%s</small>" % (_("From your Operating System"),))
        else:
            self.pkginfo_ui.pkgatomSublabel.set_markup("<small>%s</small>" % (etpRepositories[repo]['description'],))

        self.pkginfo_ui.name.set_markup("<small>%s</small>" % (pkg.onlyname,))
        self.pkginfo_ui.category.set_markup("<small>%s</small>" % (pkg.cat,))
        self.pkginfo_ui.aversion.set_markup( "<small>%s: %s</small>" % (_("Version"),pkg.onlyver,) )
        tag = pkg.tag
        if not tag: tag = "None"
        self.pkginfo_ui.atag.set_markup( "<small>%s: %s</small>" % (_("Tag"),tag,) )
        self.pkginfo_ui.arevision.set_markup( "<small>%s: %s</small>" % (_("Revision"),pkg.revision,) )
        if repo != 0:
            # search if it's installed
            key, slot = pkg.keyslot
            result = self.Equo.clientDbconn.searchKeySlot(key, slot)
            if result:
                idpackage = result[0][0]
                version = self.Equo.clientDbconn.retrieveVersion(idpackage)
                revision = self.Equo.clientDbconn.retrieveRevision(idpackage)
                tag = self.Equo.clientDbconn.retrieveVersionTag(idpackage)
            else:
                version = _("Not installed")
                revision = version
                tag = version

            self.pkginfo_ui.iversion.set_markup( "<small>%s: %s</small>" % (_("Version"),version,) )
            if not tag: tag = "None"
            self.pkginfo_ui.itag.set_markup( "<small>%s: %s</small>" % (_("Tag"),tag,) )
            self.pkginfo_ui.irevision.set_markup( "<small>%s: %s</small>" % (_("Revision"),revision,) )

            self.pkginfo_ui.vboxinstalled.show()
        else:
            self.pkginfo_ui.vboxinstalled.hide()

        # slot, size
        self.pkginfo_ui.slot.set_markup("<small>%s</small>" % (pkg.slot,))
        self.pkginfo_ui.size.set_markup("<small>%s</small>" % (pkg.intelligentsizeFmt,))
        # download, checksum
        self.pkginfo_ui.download.set_markup("<small>%s</small>" % (pkg.binurl,))
        self.pkginfo_ui.checksum.set_markup("<small>%s</small>" % (pkg.digest,))

        self.pkginfo_ui.pkgInfo.show()

    def on_pkgInfoClose_clicked( self, widget ):
        self.pkginfo_ui.pkgInfo.hide()

    def on_pkgInfo_delete_event(self, widget, path):
        self.pkginfo_ui.pkgInfo.hide()
        return True

    def on_select_clicked(self,widget):
        ''' Package Add All button handler '''
        self.setBusy()
        self.pkgView.selectAll()
        self.unsetBusy()

    def on_deselect_clicked(self,widget):
        ''' Package Remove All button handler '''
        self.on_clear_clicked(widget)
        self.setBusy()
        self.pkgView.deselectAll()
        self.unsetBusy()

    def on_skipMirror_clicked(self,widget):
        if self.skipMirror:
            self.logger.info('skipmirror')
            self.skipMirrorNow = True

    def on_search_clicked(self,widget):
        ''' Search entry+button handler'''
        txt = self.ui.pkgFilter.get_text()
        flt = filters.yumexFilter.get('KeywordFilter')
        if txt != '':
            flt.activate()
            lst = txt.split(' ')
            self.logger.debug('Search Keyword : %s' % ','.join(lst))
            flt.setKeys(lst)
        else:
            flt.activate(False)
        action = self.lastPkgPB
        rb = self.packageRB[action]
        self.on_pkgFilter_toggled(rb,action)

    def on_clear_clicked(self,widget):
        ''' Search Clear button handler'''
        self.ui.pkgFilter.set_text("")
        self.on_search_clicked(None)

    def on_schRepo_toggled(self,rb):
        ''' Search Repo Checkbox handler'''
        if rb.get_active():
            self.ui.schRepoText.set_sensitive(True)
        else:
            self.ui.schRepoText.set_text("")
            self.ui.schRepoText.set_sensitive(False)
            self.on_schRepoText_activate(self.ui.schRepoText)

    def on_schSlot_toggled(self,rb):
        ''' Search Arch Checkbox handler'''
        if rb.get_active():
            self.ui.schSlotText.set_sensitive(True)
        else:
            self.ui.schSlotText.set_text("")
            self.ui.schSlotText.set_sensitive(False)
            self.on_schSlotText_activate(self.ui.schSlotText)

    def on_schRepoText_activate(self,entry):
        ''' Search Repo Entry handler'''
        txt = entry.get_text()
        flt = filters.yumexFilter.get('RepoFilter')
        if txt != '':
            flt.activate()
            lst = txt.split(',')
            self.logger.debug('Search Repo : %s' % ','.join(lst))
            flt.setFilterList(lst)
        else:
            flt.activate(False)
        action = self.lastPkgPB
        rb = self.packageRB[action]
        self.on_pkgFilter_toggled(rb,action)


    def on_schSlotText_activate(self,entry):
        ''' Search Arch Entry handler'''
        txt = entry.get_text()
        flt = filters.yumexFilter.get('SlotFilter')
        if txt != '':
            flt.activate()
            lst = txt.split(',')
            self.logger.debug('Search Slot : %s' % ','.join(lst))
            flt.setFilterList(lst)
        else:
            flt.activate(False)
        action = self.lastPkgPB
        rb = self.packageRB[action]
        self.on_pkgFilter_toggled(rb,action)

    def on_comps_cursor_changed(self, widget):
        self.setBusy()
        """ Handle selection of row in Comps Category  view  """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            id = model.get_value( iterator, 2 )
            isCategory = model.get_value( iterator, 4 )
            if isCategory:
                self.populateCategoryPackages(id)
        self.unsetBusy()

    def on_compsPkg_cursor_changed(self, widget):
        """ Handle selection of row in Comps Category  view  """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            pkg = model.get_value( iterator, 0 )
            if pkg:
                self.catDesc.clear()
                self.catDesc.write_line(pkg.description)


# Menu Handlers

    def on_FileQuit( self, widget ):
        self.quit()

    def on_HelpAbout( self, widget ):
        about = AboutDialog(const.PIXMAPS_PATH+'/spritz-about.png',const.CREDITS,self.settings.branding_title)
        about.show()

    def on_ToolsRepoCache( self, widget ):
        self.logger.info(_('Cleaning up all yum metadata'))

class SpritzApplication(SpritzController,SpritzGUI):

    def __init__(self):
        SpritzController.__init__( self )
        self.spritzOptions = SpritzOptions()
        self.spritzOptions.parseCmdOptions()
        self.Equo = EquoConnection
        SpritzGUI.__init__(self, self.Equo, self.etpbase)
        self.logger = logging.getLogger("yumex.main")
        # init flags
        self.skipMirror = False
        self.skipMirrorNow = False
        self.doProgress = False
        self.categoryOn = False
        self.quitNow = False
        self.isWorking = False
        if self.settings.debug:
            self.spritzOptions.dump()
            print self.spritzOptions.getArgs()
        self.logger.info(_('Entropy Config Setup'))
        self.spritzOptions.parseCmdOptions()
        self.catsView.etpbase = self.etpbase
        self.lastPkgPB = "updates"
        self.etpbase.setFilter(filters.yumexFilter.processFilters)
        self.treeViewCache = {}

        self.setupEditor()
        # Setup GUI
        self.setupGUI()
        self.setPage("packages")

        self.logger.info(_('GUI Setup Completed'))
        # setup Repositories
        self.setupRepoView()
        self.firstTime = True
        # calculate updates
        self.Equo.connect_to_gui(self.progress, self.progressLogWrite, self.output)
        self.setupSpritz()

        self.console.set_pty(self.pty[0])
        # setup pty

    def setupEditor(self):

        pathenv = os.getenv("PATH")
        if os.path.isfile("/etc/profile.env"):
            f = open("/etc/profile.env")
            env_file = f.readlines()
            for line in env_file:
                line = line.strip()
                if line.startswith("export PATH='"):
                    line = line[len("export PATH='"):]
                    line = line.rstrip("'")
                    for path in line.split(":"):
                        pathenv += ":"+path
                    break
        os.environ['PATH'] = pathenv

        self.fileEditor = '/usr/bin/xterm -e $EDITOR'
        de_session = os.getenv('DESKTOP_SESSION')
        path = os.getenv('PATH').split(":")
        if os.access("/usr/bin/xdg-open",os.X_OK):
            self.fileEditor = "/usr/bin/xdg-open"
        if de_session.find("kde") != -1:
            for item in path:
                itempath = os.path.join(item,'kwrite')
                itempath2 = os.path.join(item,'kedit')
                itempath3 = os.path.join(item,'kate')
                if os.access(itempath,os.X_OK):
                    self.fileEditor = itempath
                    break
                elif os.access(itempath2,os.X_OK):
                    self.fileEditor = itempath2
                    break
                elif os.access(itempath3,os.X_OK):
                    self.fileEditor = itempath3
                    break
        else:
            if os.access('/usr/bin/gedit',os.X_OK):
                self.fileEditor = '/usr/bin/gedit'

    def startWorking(self):
        self.isWorking = True
        busyCursor(self.ui.main)
        self.ui.progressVBox.grab_add()
        gtkEventThread.startProcessing()

    def endWorking(self):
        self.isWorking = False
        self.ui.progressVBox.grab_remove()
        normalCursor(self.ui.main)
        gtkEventThread.endProcessing()

    def setupSpritz(self):
        self.treeViewCache.clear()
        msg = _('Generating metadata. Please wait.')
        self.setStatus(msg)
        self.addPackages()
        # XXX: if we'll re-enable categories listing, uncomment this
        #self.progressLog(_('Building Category Lists'))
        self.populateCategories()
        #self.progressLog(_('Building Category Lists Completed'))
        msg = _('Ready')
        self.setStatus(msg)

    def cleanEntropyCaches(self, alone = False):
        if alone:
            self.progress.total.hide()
        self.Equo.generate_cache(depcache = True, configcache = False)
        # clear views
        self.etpbase.clearPackages()
        self.etpbase.clearCache()
        self.setupSpritz()
        if alone:
            self.progress.total.show()

    def populateFilesUpdate(self):
        # load filesUpdate interface and fill self.filesView
        cached = None
        try:
            cached = self.Equo.FileUpdates.load_cache()
        except exceptionTools.CacheCorruptionError:
            pass
        if cached == None:
            self.setBusy()
            cached = self.Equo.FileUpdates.scanfs()
            self.unsetBusy()
        if cached:
            self.filesView.populate(cached)

    def updateRepositories(self, repos):
        self.setPage('output')
        self.startWorking()

        # set steps
        progress_step = float(1)/(len(repos))
        step = progress_step
        myrange = []
        while progress_step < 1.0:
            myrange.append(step)
            progress_step += step
        myrange.append(step)

        self.progress.total.setup( myrange )
        self.progress.set_mainLabel(_('Initializing Repository module...'))
        forceUpdate = self.ui.forceRepoUpdate.get_active()

        try:
            repoConn = self.Equo.Repositories(repos, forceUpdate = forceUpdate)
        except exceptionTools.PermissionDenied:
            self.progressLog(_('You must run this application as root'), extra = "repositories")
            return 1
        except exceptionTools.MissingParameter:
            self.progressLog(_('No repositories specified in %s') % (etpConst['repositoriesconf'],), extra = "repositories")
            return 127
        except exceptionTools.OnlineMirrorError:
            self.progressLog(_('You are not connected to the Internet. You should.'), extra = "repositories")
            return 126
        except Exception, e:
            self.progressLog(_('Unhandled exception: %s') % (str(e),), extra = "repositories")
            return 2
        rc = repoConn.sync()
        if repoConn.syncErrors:
            self.progress.set_mainLabel(_('Errors updating repositories.'))
            self.progress.set_subLabel(_('Please check logs below for more info'))
        else:
            if repoConn.alreadyUpdated == 0:
                self.progress.set_mainLabel(_('Repositories updated successfully'))
            else:
                if len(repos) == repoConn.alreadyUpdated:
                    self.progress.set_mainLabel(_('All the repositories were already up to date.'))
                else:
                    self.progress.set_mainLabel(_('%s repositories were already up to date. Others have been updated.' % (str(repoConn.alreadyUpdated),)))
            if repoConn.newEquo:
                self.progress.set_extraLabel(_('app-admin/equo needs to be updated as soon as possible.'))

        initConfig_entropyConstants(etpSys['rootdir'])
        self.setupRepoView()
        self.endWorking()


    def setupRepoView(self):
        self.repoView.populate()

    def setBusy(self):
        busyCursor(self.ui.main)

    def unsetBusy(self):
        normalCursor(self.ui.main)

    def addPackages(self):

        def comeback(bootstrap):
            self.unsetBusy()
            if self.doProgress: self.progress.hide() #Hide Progress
            if bootstrap:
                self.setPage('packages')

        bootstrap = False
        if (self.Equo.get_world_update_cache(empty_deps = False) == None):
            bootstrap = True
            self.setPage('output')
        self.progress.total.hide()
        self.setBusy()

        if bootstrap:
            self.startWorking()
            time.sleep(1)
            self.endWorking()

        action = self.lastPkgPB
        if action == 'all':
            masks = ['installed','available']
        else:
            masks = [action]

        self.etpbase.clearPackages()
        allpkgs = []
        if self.doProgress: self.progress.total.next() # -> Get lists
        for flt in masks:
            msg = _('Calculating %s' ) % flt
            #self.progressLog(msg)
            self.setStatus(msg)
            pkgs = self.etpbase.getPackages(flt)
            #self.progressLog(_('Found %d %s') % (len(pkgs),flt))
            allpkgs.extend(pkgs)
            self.setStatus(_("Ready"))
        if self.doProgress: self.progress.total.next() # -> Sort Lists

        def mycmp(x,y):
            return cmp(x,y)
        my_hash = hash(tuple(action))
        if self.treeViewCache.has_key(my_hash):
            allpkgs = self.treeViewCache[my_hash]
        else:
            try:
                allpkgs = sorted(allpkgs,mycmp)
            except: # python 2.4 support
                allpkgs.sort()
            # store
            # FIXME: we need to keep caching disabled because searches won't work then
            #self.treeViewCache[my_hash] = allpkgs

        self.pkgView.store.clear()
        self.ui.viewPkg.set_model(None)
        for po in allpkgs:
            self.pkgView.store.append((po,str(po)))
        self.ui.viewPkg.set_model(self.pkgView.store)
        self.progress.total.show()

        self.treeViewPackages = my_hash

        comeback(bootstrap)

    def addCategoryPackages(self,cat = None):
        msg = _('Package View Population')
        self.setStatus(msg)
        self.setBusy()
        self.pkgView.store.clear()
        pkgs = self.yumbase.getPackagesByCategory(cat)
        if pkgs:
            pkgs.sort()
            self.ui.viewPkg.set_model(None)
            for po in pkgs:
                self.pkgView.store.append([po,str(po)])
            self.ui.viewPkg.set_model(self.pkgView.store)
            self.ui.viewPkg.set_search_column( 2 )
            msg = _('Package View Population Completed')
            self.setStatus(msg)
        self.unsetBusy()


    def addCategories(self, fn, para, sortkeys,splitkeys ):
        msg = _('Category View Population')
        self.setStatus(msg)
        self.setBusy()
        getterfn = getattr( self.etpbase, fn )
        if para != '':
            lst, keys = getterfn( self.lastPkgPB, para )
        else:
            lst, keys = getterfn( self.lastPkgPB )
        fkeys = [ key for key in keys if lst.has_key(key)]
        if sortkeys:
            fkeys.sort()
        if not splitkeys:
            self.catView.populate(fkeys)
        else:
            keydict = self.splitCategoryKeys(fkeys)
            self.catView.populate(keydict,True)
        self.etpbase.setCategoryPackages(lst)
        self.catView.view.set_cursor((0,))
        self.unsetBusy()
        msg = _('Category View Population Completed')
        self.setStatus(msg)

    def splitCategoryKeys(self,keys,sep='/'):
        tree = RPMGroupTree()
        for k in keys:
            lst = k.split(sep)
            tree.add(lst)
        return tree

    def getRecentTime(self,recentdays = 14):
        recentdays = float( recentdays )
        now = time.time()
        return now-( recentdays*const.DAY_IN_SECONDS )

    def processPackageQueue( self, pkgs, doAll=False):
        """ Workflow for processing package queue """
        self.setStatus( _( "Running tasks" ) )
        total = len( pkgs['i'] )+len( pkgs['u'] )+len( pkgs['r'] )
        state = True
        quit = False
        if total > 0:
            self.startWorking()
            self.progress.show()
            self.progress.set_mainLabel( _( "Processing Packages in queue" ) )

            queue = pkgs['i']+pkgs['u']
            install_queue = [x.matched_atom for x in queue]
            removal_queue = [x.matched_atom[0] for x in pkgs['r']]
            do_purge_cache = set([x.matched_atom[0] for x in pkgs['r'] if x.do_purge])
            if install_queue or removal_queue:
                controller = QueueExecutor(self)
                e,i = controller.run(install_queue[:], removal_queue[:], do_purge_cache)
                if e != 0:
                    okDialog( self.ui.main, _("Attention. An error occured when processing the queue.\nPlease have a look in the processing terminal.") )
                # XXX let it sleep a bit to allow all other threads to flush
                while gtk.events_pending():
                    time.sleep(0.1)
                time.sleep(20) # FIXME, still happens on a big queue
            self.progress.reset_progress()
            self.Equo.closeAllRepositoryDatabases()
            self.Equo.reopenClientDbconn()
            # regenerate packages information
            self.etpbase.clearPackages()
            self.etpbase.clearCache()
            self.setupSpritz()
            self.endWorking()
            self.Equo.FileUpdates.scanfs(dcache = False)
            if self.Equo.FileUpdates.scandata:
                if len(self.Equo.FileUpdates.scandata) > 0:
                    self.setPage('filesconf')
            #self.progress.hide()
            if quit:
                return "QUIT"
            return state
        else:
            self.setStatus( _( "No packages selected" ) )
            return state

    def get_confimation( self, task ):
        self.progress.hide( False )
        dlg = ConfimationDialog(self.ui.main, [], size )
        rc = dlg.run()
        dlg.destroy()
        self.progress.show()
        return rc == gtk.RESPONSE_OK

    def populateCategories(self):
        self.setBusy()
        self.etpbase.populateCategories()
        self.catsView.populate(self.etpbase.getCategories())
        self.unsetBusy()

    def populateCategoryPackages(self, cat):
        self.catDesc.clear()
        pkgs = self.etpbase.getPackagesByCategory(cat)
        self.catPackages.store.clear()
        self.ui.tvCatPackages.set_model(None)
        for po in pkgs:
            self.catPackages.store.append([po,str(po)])
        self.ui.tvCatPackages.set_model(self.catPackages.store)


class ProcessGtkEventsThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.__quit = False
        self.__active = Event()
        self.__active.clear()

    def run(self):
        while self.__quit == False:
            import time
            while not self.__active.isSet():
                self.__active.wait()
            time.sleep(0.1)
            while gtk.events_pending():      # process gtk events
                gtk.main_iteration()
            time.sleep(0.1)

    def doQuit(self):
        self.__quit = True
        self.__active.set()

    def startProcessing(self):
        self.__active.set()

    def endProcessing(self):
        self.__active.clear()

if __name__ == "__main__":
    try:
        gtkEventThread = ProcessGtkEventsThread()
        gtkEventThread.start()
        gtk.window_set_default_icon_from_file(const.PIXMAPS_PATH+"/spritz-icon.png")
        mainApp = SpritzApplication()
        gtk.main()
    except SystemExit, e:
        print "Quit by User"
        gtkEventThread.doQuit()
        sys.exit(1)
    except KeyboardInterrupt:
        print "Quit by User"
        gtkEventThread.doQuit()
        sys.exit(1)
    except: # catch other exception and write it to the logger.
        logger = logging.getLogger('yumex.main')
        etype = sys.exc_info()[0]
        evalue = sys.exc_info()[1]
        etb = traceback.extract_tb(sys.exc_info()[2])
        logger.error('Error Type: %s' % str(etype) )
        errmsg = 'Error Type: %s \n' % str(etype)
        logger.error('Error Value: ' + str(evalue))
        errmsg += 'Error Value: %s \n' % str(evalue)
        logger.error('Traceback: \n')
        for tub in etb:
            f,l,m,c = tub # file,lineno, function, codeline
            logger.error('  File : %s , line %s, in %s' % (f,str(l),m))
            errmsg += '  File : %s , line %s, in %s\n' % (f,str(l),m)
            logger.error('    %s ' % c)
            errmsg += '    %s \n' % c
        errorMessage(None, _( "Error" ), _( "Error in Yumex" ), errmsg )  
        gtkEventThread.doQuit()
        sys.exit(1)
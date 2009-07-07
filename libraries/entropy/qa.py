# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''
# pylint ~ok
import os
import sys
import subprocess
import tempfile

from entropy.const import etpConst, etpSys
from entropy.output import blue, darkgreen, red, darkred, bold, purple, brown
from entropy.exceptions import IncorrectParameter, PermissionDenied, \
    SystemDatabaseError
from entropy.i18n import _
from entropy.core import SystemSettings

class QAInterface:

    import entropy.tools as entropyTools
    from entropy.misc import Lifo
    def __init__(self, OutputInterface):

        self.Output = OutputInterface
        self.SystemSettings = SystemSettings()

        if not hasattr(self.Output, 'updateProgress'):
            mytxt = _("Output interface has no updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        elif not callable(self.Output.updateProgress):
            mytxt = _("Output interface has no updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

    def test_depends_linking(self, idpackages, dbconn, repo = None):

        repo = self.SystemSettings['repositories']['default_repository']

        scan_msg = blue(_("Now searching for broken depends"))
        self.Output.updateProgress(
            "[repo:%s] %s..." % (
                        darkgreen(repo),
                        scan_msg,
                    ),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        broken = False

        count = 0
        maxcount = len(idpackages)
        for idpackage in idpackages:
            count += 1
            atom = dbconn.retrieveAtom(idpackage)
            scan_msg = "%s, %s:" % (
                blue(_("scanning for broken depends")),
                darkgreen(atom),
            )
            self.Output.updateProgress(
                "[repo:%s] %s" % (
                    darkgreen(repo),
                    scan_msg,
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                back = True,
                count = (count, maxcount,)
            )
            mydepends = dbconn.retrieveDepends(idpackage)
            if not mydepends:
                continue
            for mydepend in mydepends:
                myatom = dbconn.retrieveAtom(mydepend)
                self.Output.updateProgress(
                    "[repo:%s] %s => %s" % (
                        darkgreen(repo),
                        darkgreen(atom),
                        darkred(myatom),
                    ),
                    importance = 0,
                    type = "info",
                    header = blue(" @@ "),
                    back = True,
                    count = (count, maxcount,)
                )
                mycontent = dbconn.retrieveContent(mydepend)
                mybreakages = self.content_test(mycontent)
                if not mybreakages:
                    continue
                broken = True
                self.Output.updateProgress(
                    "[repo:%s] %s %s => %s" % (
                        darkgreen(repo),
                        darkgreen(atom),
                        darkred(myatom),
                        bold(_("broken libraries detected")),
                    ),
                    importance = 1,
                    type = "warning",
                    header = purple(" @@ "),
                    count = (count, maxcount,)
                )
                for mylib in mybreakages:
                    self.Output.updateProgress(
                        "%s %s:" % (
                            darkgreen(mylib),
                            red(_("needs")),
                        ),
                        importance = 1,
                        type = "warning",
                        header = brown("   ## ")
                    )
                    for needed in mybreakages[mylib]:
                        self.Output.updateProgress(
                            "%s" % (
                                red(needed),
                            ),
                            importance = 1,
                            type = "warning",
                            header = purple("     # ")
                        )
        return broken

    def scan_missing_dependencies(self, idpackages, dbconn, ask = True,
            self_check = False, repo = None, black_list = None,
            black_list_adder = None):

        if repo == None:
            repo = self.SystemSettings['repositories']['default_repository']

        if not isinstance(black_list, set):
            black_list = set()

        taint = False
        scan_msg = blue(_("Now searching for missing RDEPENDs"))
        self.Output.updateProgress(
            "[repo:%s] %s..." % (
                        darkgreen(repo),
                        scan_msg,
                    ),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )
        scan_msg = blue(_("scanning for missing RDEPENDs"))
        count = 0
        maxcount = len(idpackages)
        for idpackage in idpackages:
            count += 1
            atom = dbconn.retrieveAtom(idpackage)
            if not atom:
                continue
            self.Output.updateProgress(
                "[repo:%s] %s: %s" % (
                            darkgreen(repo),
                            scan_msg,
                            darkgreen(atom),
                        ),
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                back = True,
                count = (count, maxcount,)
            )
            missing_extended, missing = self.get_missing_rdepends(dbconn,
                idpackage, self_check = self_check)
            missing -= black_list
            for item in missing_extended.keys():
                missing_extended[item] -= black_list
                if not missing_extended[item]:
                    del missing_extended[item]
            if (not missing) or (not missing_extended):
                continue
            self.Output.updateProgress(
                "[repo:%s] %s: %s %s:" % (
                            darkgreen(repo),
                            blue("package"),
                            darkgreen(atom),
                            blue(_("is missing the following dependencies")),
                        ),
                importance = 1,
                type = "info",
                header = red(" @@ "),
                count = (count, maxcount,)
            )
            for missing_data in missing_extended:
                self.Output.updateProgress(
                        "%s:" % (brown(unicode(missing_data)),),
                        importance = 0,
                        type = "info",
                        header = purple("   ## ")
                )
                for dependency in missing_extended[missing_data]:
                    self.Output.updateProgress(
                            "%s" % (darkred(dependency),),
                            importance = 0,
                            type = "info",
                            header = blue("     # ")
                    )
            if ask:
                rc_ask = self.Output.askQuestion(_("Do you want to add them?"))
                if rc_ask == "No":
                    continue
                rc_ask = self.Output.askQuestion(_("Selectively?"))
                if rc_ask == "Yes":
                    newmissing = set()
                    new_blacklist = set()
                    for dependency in missing:
                        self.Output.updateProgress(
                            "[repo:%s|%s] %s" % (
                                    darkgreen(repo),
                                    brown(atom),
                                    blue(dependency),
                            ),
                            importance = 0,
                            type = "info",
                            header = blue(" @@ ")
                        )
                        rc_ask = self.Output.askQuestion(_("Want to add?"))
                        if rc_ask == "Yes":
                            newmissing.add(dependency)
                        else:
                            rc_ask = self.Output.askQuestion(
                                _("Want to blacklist?"))
                            if rc_ask == "Yes":
                                new_blacklist.add(dependency)
                    if new_blacklist and (black_list_adder != None):
                        black_list_adder(new_blacklist, repo = repo)
                    missing = newmissing
            if missing:
                taint = True
                dbconn.insertDependencies(idpackage, missing)
                dbconn.commitChanges()
                self.Output.updateProgress(
                    "[repo:%s] %s: %s" % (
                        darkgreen(repo),
                        darkgreen(atom),
                        blue(_("missing dependencies added")),
                    ),
                    importance = 1,
                    type = "info",
                    header = red(" @@ "),
                    count = (count, maxcount,)
                )

        return taint

    def libraries_test(self, dbconn, broken_symbols = False,
        task_bombing_func = None):

        self.Output.updateProgress(
            blue(_("Libraries test")),
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )

        myroot = etpConst['systemroot'] + "/"
        if not etpConst['systemroot']:
            myroot = "/"

        # run ldconfig first
        subprocess.call("ldconfig -r %s &> /dev/null" % (myroot,), shell = True)
        # open /etc/ld.so.conf
        ld_conf = etpConst['systemroot'] + "/etc/ld.so.conf"

        if not os.path.isfile(ld_conf):
            self.Output.updateProgress(
                blue(_("Cannot find "))+red(ld_conf),
                importance = 1,
                type = "error",
                header = red(" @@ ")
            )
            return {}, set(), -1

        reverse_symlink_map = self.SystemSettings['system_rev_symlinks']
        broken_syms_list = self.SystemSettings['broken_syms']
        broken_libs_mask = self.SystemSettings['broken_libs_mask']

        import re

        broken_syms_list_regexp = []
        for broken_sym in broken_syms_list:
            reg_sym = re.compile(broken_sym)
            broken_syms_list_regexp.append(reg_sym)

        broken_libs_mask_regexp = []
        for broken_lib in broken_libs_mask:
            reg_lib = re.compile(broken_lib)
            broken_libs_mask_regexp.append(reg_lib)

        ldpaths = set(self.entropyTools.collect_linker_paths())
        ldpaths |= self.entropyTools.collect_paths()

        # some crappy packages put shit here too
        ldpaths.add("/usr/share")
        # always force /usr/libexec too
        ldpaths.add("/usr/libexec")

        # remove duplicated dirs (due to symlinks) to speed up scanning
        for real_dir in reverse_symlink_map.keys():
            syms = reverse_symlink_map[real_dir]
            for sym in syms:
                if sym in ldpaths:
                    ldpaths.discard(real_dir)
                    self.Output.updateProgress(
                        "%s: %s, %s: %s" % (
                            brown(_("discarding directory")),
                            purple(real_dir),
                            brown(_("because it's symlinked on")),
                            purple(sym),
                        ),
                        importance = 0,
                        type = "info",
                        header = darkgreen(" @@ ")
                    )
                    break

        executables = set()
        total = len(ldpaths)
        count = 0
        sys_root_len = len(etpConst['systemroot'])
        for ldpath in ldpaths:

            if callable(task_bombing_func):
                task_bombing_func()
            count += 1
            self.Output.updateProgress(
                blue("Tree: ")+red(etpConst['systemroot'] + ldpath),
                importance = 0,
                type = "info",
                count = (count,total),
                back = True,
                percent = True,
                header = "  "
            )
            ldpath = ldpath.encode(sys.getfilesystemencoding())
            mywalk_iter = os.walk(etpConst['systemroot'] + ldpath)

            def mywimf(dt):

                currentdir, subdirs, files = dt

                def mymf(item):
                    filepath = os.path.join(currentdir,item)
                    if not os.access(filepath, os.R_OK):
                        return 0
                    if not os.path.isfile(filepath):
                        return 0
                    if not self.entropyTools.is_elf_file(filepath):
                        return 0
                    return filepath[sys_root_len:]

                return set([x for x in map(mymf, files) if type(x) != int])

            for x in map(mywimf,mywalk_iter):
                executables |= x

        self.Output.updateProgress(
            blue(_("Collecting broken executables")),
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )
        t = red(_("Attention")) + ": " + \
            blue(_("don't worry about libraries that are shown here but not later."))
        self.Output.updateProgress(
            t,
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        plain_brokenexecs = set()
        total = len(executables)
        count = 0
        scan_txt = blue("%s ..." % (_("Scanning libraries"),))
        for executable in executables:

            # task bombing hook
            if callable(task_bombing_func):
                task_bombing_func()

            count += 1
            if (count % 10 == 0) or (count == total) or (count == 1):
                self.Output.updateProgress(
                    scan_txt,
                    importance = 0,
                    type = "info",
                    count = (count,total),
                    back = True,
                    percent = True,
                    header = "  "
                )

            myelfs = self.entropyTools.read_elf_dynamic_libraries(
                etpConst['systemroot'] + executable)

            def mymf2(mylib):
                return not self.resolve_dynamic_library(mylib, executable)

            mylibs = set(filter(mymf2, myelfs))

            # filter broken libraries
            if mylibs:

                mylib_filter = set()
                for mylib in mylibs:
                    mylib_matched = False
                    for reg_lib in broken_libs_mask_regexp:
                        if reg_lib.match(mylib):
                            mylib_matched = True
                            break
                    if mylib_matched: # filter out
                        mylib_filter.add(mylib)
                mylibs -= mylib_filter


            broken_sym_found = set()
            if broken_symbols and not mylibs:

                read_broken_syms = self.entropyTools.read_elf_broken_symbols(
                        etpConst['systemroot'] + executable)
                my_broken_syms = set()
                for read_broken_sym in read_broken_syms:
                    for reg_sym in broken_syms_list_regexp:
                        if reg_sym.match(read_broken_sym):
                            my_broken_syms.add(read_broken_sym)
                            break
                broken_sym_found.update(my_broken_syms)

            if not (mylibs or broken_sym_found):
                continue

            if mylibs:
                alllibs = blue(' :: ').join(sorted(mylibs))
                self.Output.updateProgress(
                    red(etpConst['systemroot']+executable)+" [ "+alllibs+" ]",
                    importance = 1,
                    type = "info",
                    percent = True,
                    count = (count,total),
                    header = "  "
                )
            elif broken_sym_found:

                allsyms = darkred(' :: ').join(
                    [brown(x) for x in list(broken_sym_found)])
                if len(allsyms) > 50:
                    allsyms = brown(_('various broken symbols'))

                self.Output.updateProgress(
                    red(etpConst['systemroot']+executable)+" { "+allsyms+" }",
                    importance = 1,
                    type = "info",
                    percent = True,
                    count = (count,total),
                    header = "  "
                )

            plain_brokenexecs.add(executable)

        del executables
        packagesMatched = {}

        if not etpSys['serverside']:

            # we are client side
            # this is hackish and must be fixed sooner or later
            # but for now, it works
            # Client class is singleton and is surely already
            # loaded when we get here
            from entropy.client.interfaces import Client
            client = Client()

            self.Output.updateProgress(
                blue(_("Matching broken libraries/executables")),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )
            matched = set()
            for brokenlib in plain_brokenexecs:
                idpackages = dbconn.searchBelongs(brokenlib)

                for idpackage in idpackages:

                    key, slot = dbconn.retrieveKeySlot(idpackage)
                    mymatch = client.atom_match(key, matchSlot = slot)
                    if mymatch[0] == -1:
                        matched.add(brokenlib)
                        continue

                    cmpstat = client.get_package_action(mymatch)
                    if cmpstat == 0:
                        continue
                    if not packagesMatched.has_key(brokenlib):
                        packagesMatched[brokenlib] = set()

                    packagesMatched[brokenlib].add(mymatch)
                    matched.add(brokenlib)

            plain_brokenexecs -= matched

        return packagesMatched, plain_brokenexecs, 0

    def content_test(self, mycontent):

        def is_contained(needed, content):
            for item in content:
                if os.path.basename(item) == needed:
                    return True
            return False

        mylibs = {}
        for myfile in mycontent:
            myfile = myfile.encode('raw_unicode_escape')
            if not os.access(myfile, os.R_OK):
                continue
            if not os.path.isfile(myfile):
                continue
            if not self.entropyTools.is_elf_file(myfile):
                continue
            mylibs[myfile] = self.entropyTools.read_elf_dynamic_libraries(
                myfile)

        broken_libs = {}
        for mylib in mylibs:
            for myneeded in mylibs[mylib]:
                # is this inside myself ?
                if is_contained(myneeded, mycontent):
                    continue
                found = self.resolve_dynamic_library(myneeded, mylib)
                if found:
                    continue
                if not broken_libs.has_key(mylib):
                    broken_libs[mylib] = set()
                broken_libs[mylib].add(myneeded)

        return broken_libs

    def resolve_dynamic_library(self, library, requiring_executable):

        def do_resolve(mypaths):
            found_path = None
            for mypath in mypaths:
                mypath = os.path.join(etpConst['systemroot']+mypath, library)
                if not os.access(mypath, os.R_OK):
                    continue
                if os.path.isdir(mypath):
                    continue
                if not self.entropyTools.is_elf_file(mypath):
                    continue
                found_path = mypath
                break
            return found_path

        mypaths = self.entropyTools.collect_linker_paths()
        found_path = do_resolve(mypaths)

        if not found_path:
            mypaths = self.entropyTools.read_elf_linker_paths(
                requiring_executable)
            found_path = do_resolve(mypaths)

        return found_path

    def get_missing_rdepends(self, dbconn, idpackage, self_check = False):

        rdepends = {}
        rdepends_plain = set()
        neededs = dbconn.retrieveNeeded(idpackage, extended = True)
        ldpaths = set(self.entropyTools.collect_linker_paths())
        deps_content = set()
        dependencies = self.get_deep_dependency_list(dbconn, idpackage,
            atoms = True)
        scope_cache = set()

        def update_depscontent(mycontent, dbconn, ldpaths):
            return set( \
                [x for x in mycontent if os.path.dirname(x) in ldpaths \
                and (dbconn.isNeededAvailable(os.path.basename(x)) > 0) ])

        def is_in_content(myneeded, content):
            for item in content:
                item = os.path.basename(item)
                if myneeded == item:
                    return True
            return False

        for dependency in dependencies:
            match = dbconn.atomMatch(dependency)
            if match[0] != -1:
                mycontent = dbconn.retrieveContent(match[0])
                deps_content |= update_depscontent(mycontent, dbconn, ldpaths)
                key, slot = dbconn.retrieveKeySlot(match[0])
                scope_cache.add((key, slot))

        key, slot = dbconn.retrieveKeySlot(idpackage)
        mycontent = dbconn.retrieveContent(idpackage)
        deps_content |= update_depscontent(mycontent, dbconn, ldpaths)
        scope_cache.add((key, slot))

        idpackages_cache = set()
        idpackage_map = {}
        idpackage_map_reverse = {}
        for needed, elfclass in neededs:
            data_solved = dbconn.resolveNeeded(needed, elfclass = elfclass,
                extended = True)
            data_size = len(data_solved)
            data_solved = set([x for x in data_solved if x[0] \
                not in idpackages_cache])
            if not data_solved or (data_size != len(data_solved)):
                continue

            if self_check:
                if is_in_content(needed, mycontent):
                    continue

            found = False
            for data in data_solved:
                if data[1] in deps_content:
                    found = True
                    break
            if not found:
                for data in data_solved:
                    r_idpackage = data[0]
                    key, slot = dbconn.retrieveKeySlot(r_idpackage)
                    if (key, slot) not in scope_cache:
                        if not dbconn.isSystemPackage(r_idpackage):
                            if not rdepends.has_key((needed, elfclass)):
                                rdepends[(needed, elfclass)] = set()
                            if not idpackage_map.has_key((needed, elfclass)):
                                idpackage_map[(needed, elfclass)] = set()
                            keyslot = "%s:%s" % (key, slot,)
                            obj = idpackage_map_reverse.setdefault(
                                keyslot, set())
                            obj.add((needed, elfclass,))
                            rdepends[(needed, elfclass)].add(keyslot)
                            idpackage_map[(needed, elfclass)].add(r_idpackage)
                            rdepends_plain.add(keyslot)
                        idpackages_cache.add(r_idpackage)

        # now reduce dependencies

        r_deplist = set()
        for key in idpackage_map:
            r_idpackages = idpackage_map.get(key)
            for r_idpackage in r_idpackages:
                r_deplist |= dbconn.retrieveDependencies(r_idpackage)

        r_keyslots = set()
        for r_dep in r_deplist:
            m_idpackage, m_rc = dbconn.atomMatch(r_dep)
            if m_rc != 0:
                continue
            keyslot = dbconn.retrieveKeySlotAggregated(m_idpackage)
            if keyslot in rdepends_plain:
                r_keyslots.add(keyslot)

        rdepends_plain -= r_keyslots
        for r_keyslot in r_keyslots:
            keys = [x for x in idpackage_map_reverse.get(keyslot, set()) if \
                x in rdepends]
            for key in keys:
                rdepends[key].discard(r_keyslot)
                if not rdepends[key]:
                    del rdepends[key]

        return rdepends, rdepends_plain

    def get_deep_dependency_list(self, dbconn, idpackage, atoms = False):

        mybuffer = self.Lifo()
        matchcache = set()
        depcache = set()
        mydeps = dbconn.retrieveDependencies(idpackage)
        for mydep in mydeps:
            mybuffer.push(mydep)
        try:
            mydep = mybuffer.pop()
        except ValueError:
            mydep = None # stack empty

        while mydep:

            if mydep in depcache:
                try:
                    mydep = mybuffer.pop()
                except ValueError:
                    break # stack empty
                continue

            my_idpackage, my_rc = dbconn.atomMatch(mydep)
            if atoms:
                matchcache.add(mydep)
            else:
                matchcache.add(my_idpackage)

            if my_idpackage != -1:
                owndeps = dbconn.retrieveDependencies(my_idpackage)
                for owndep in owndeps:
                    mybuffer.push(owndep)

            depcache.add(mydep)
            try:
                mydep = mybuffer.pop()
            except ValueError:
                break # stack empty

        # always discard -1 in set
        matchcache.discard(-1)
        return matchcache

    def __analyze_package_edb(self, pkg_path):

        from entropy.db import LocalRepository, dbapi2
        fd, tmp_path = tempfile.mkstemp()
        extract_path = self.entropyTools.extract_edb(pkg_path, tmp_path)
        if extract_path is None:
            os.remove(tmp_path)
            os.close(fd)
            return False # error!
        try:
            dbc = LocalRepository(
                readOnly = False,
                dbFile = tmp_path,
                clientDatabase = True,
                dbname = 'qa_testing',
                xcache = False,
                indexing = False,
                OutputInterface = self.Output,
                skipChecks = False
            )
        except dbapi2.Error:
            os.remove(tmp_path)
            os.close(fd)
            return False

        valid = True
        try:
            dbc.validateDatabase()
        except SystemDatabaseError:
            valid = False

        if valid:
            try:
                for idpackage in dbc.listAllIdpackages():
                    dbc.retrieveContent(idpackage, extended = True,
                        formatted = True, insert_formatted = True)
            except dbapi2.Error:
                valid = False

        dbc.closeDB()
        os.remove(tmp_path)
        os.close(fd)

        return valid

    def entropy_package_checks(self, package_path):
        qa_methods = [self.__analyze_package_edb]
        for method in qa_methods:
            qa_rc = method(package_path)
            if not qa_rc:
                return False
        return True


class ErrorReportInterface:

    import entropy.tools as entropyTools
    def __init__(self, post_url):
        from entropy.misc import MultipartPostHandler
        import urllib2
        self.url = post_url
        self.opener = urllib2.build_opener(MultipartPostHandler)
        self.generated = False
        self.params = {}

        sys_settings = SystemSettings()
        proxy_settings = sys_settings['system']['proxy']
        mydict = {}
        if proxy_settings['ftp']:
            mydict['ftp'] = proxy_settings['ftp']
        if proxy_settings['http']:
            mydict['http'] = proxy_settings['http']
        if mydict:
            mydict['username'] = proxy_settings['username']
            mydict['password'] = proxy_settings['password']
            self.entropyTools.add_proxy_opener(urllib2, mydict)
        else:
            # unset
            urllib2._opener = None

    def prepare(self, tb_text, name, email, report_data = "", description = ""):

        import sys
        from entropy.tools import getstatusoutput
        self.params['arch'] = etpConst['currentarch']
        self.params['stacktrace'] = tb_text
        self.params['name'] = name
        self.params['email'] = email
        self.params['version'] = etpConst['entropyversion']
        self.params['errordata'] = report_data
        self.params['description'] = description
        self.params['arguments'] = ' '.join(sys.argv)
        self.params['uid'] = etpConst['uid']
        self.params['system_version'] = "N/A"
        if os.access(etpConst['systemreleasefile'], os.R_OK):
            f_rel = open(etpConst['systemreleasefile'], "r")
            self.params['system_version'] = f_rel.readline().strip()
            f_rel.close()

        self.params['processes'] = getstatusoutput('ps auxf')[1]
        self.params['lspci'] = getstatusoutput('/usr/sbin/lspci')[1]
        self.params['dmesg'] = getstatusoutput('dmesg')[1]
        self.params['locale'] = getstatusoutput('locale -v')[1]

        self.generated = True

    # params is a dict, key(HTTP post item name): value
    def submit(self):
        if self.generated:
            result = self.opener.open(self.url, self.params).read()
            if result.strip() == "1":
                return True
            return False
        else:
            mytxt = _("Not prepared yet")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))

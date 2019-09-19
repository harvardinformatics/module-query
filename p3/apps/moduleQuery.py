#!/usr/bin/python
# encoding: utf-8
"""
module-query -- Command line query of the applications database

Command line tool that queries the applications database.  Intended to be used
like the module spider command, with a similar output.

Like module spider, if a query argument returns multiple builds, a grouped "application"
report is displayed.  If a single build is returned, the full details, including
module load and run time dependencies is displayed.


@author:     Aaron Kitzmiller
@copyright:  2019 The Presidents and Fellows of Harvard College. All rights reserved.
@license:    GPL v2.0
@contact:    aaron_kitzmiller@harvard.edu
@deffield    updated: Updated
"""
from __future__ import print_function
import sys
import re
import os, traceback, time
import json
from collections import defaultdict

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter

import MySQLdb
from textwrap import TextWrapper

__all__ = []
__version__ = 0.1
__date__ = "2015-09-01"
__updated__ = "2015-09-01"

DEBUG = os.environ.get("MODULE_QUERY_DEBUG", 0)
PROFILE = 0

SQL_DSN = {
    "host"      : os.environ.get("MODULE_QUERY_HOST", "rcdb-internal"),
    "db"        : os.environ.get("MODULE_QUERY_DB", "p3"),
    "user"      : os.environ.get("MODULE_QUERY_USER", "modulequery"),
    "passwd"    : os.environ.get("MODULE_QUERY_PASSWD"),
    "use_unicode" : True,
}
if DEBUG:
    sys.stderr.write("%s\n" % repr(SQL_DSN))
MAX_ATTEMPTS = 3
CONNECTION_WAIT = 2


def getTerminalSize():
    env = os.environ

    def ioctl_GWINSZ(fd):
        try:
            import fcntl, termios, struct, os
            cr = struct.unpack("hh", fcntl.ioctl(fd, termios.TIOCGWINSZ, "1234"))
        except Exception:
            return
        return cr
    cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
    if not cr:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            cr = ioctl_GWINSZ(fd)
            os.close(fd)
        except Exception:
            pass
    if not cr:
        cr = (env.get("LINES", 25), env.get("COLUMNS", 80))

    return int(cr[1])


def fetchBuildReports(search, build_stack_names, fulltext=False):
    """
    Uses SQL to fetch the matching build reports.  If
    fulltext is True, searches the build report text
    """
    if DEBUG:
        print('search {}, build_stack_names {}, fulltext {}'.format(search, ','.join(build_stack_names), str(fulltext)))

    term = '%{}%'.format(search)
    # Need (%s,%s,%s) for python 2 in clause
    format_strings = ','.join(['%s'] * len(build_stack_names))
    sql = """
        select
            br.*
        from
            build_report br
        where
            br.build_name like %s and
            br.build_stack_name in ({in_clause})
        order by
            app_name, br.build_order
    """.translate(None, "\n").format(in_clause=format_strings)

    if fulltext:
        sql = """
            select
                br.*
            from
                build_report br
            where
                br.report_text like %s and
                br.build_stack_name in ({in_clause})
            order by
                app_name, br.build_order
        """.translate(None, "\n").format(in_clause=format_strings)

    # Connection attempt is made.  After MAX_ATTEMPTS tries,
    connection = None
    connection_attempts = 0
    while connection is None and connection_attempts < MAX_ATTEMPTS:
        try:
            connection = MySQLdb.connect(**SQL_DSN)
        except Exception as e:
            if DEBUG:
                sys.stderr.write("Connection error %s\n%s\n" % (str(e), traceback.format_exc()))
            time.sleep(CONNECTION_WAIT)
            connection_attempts += 1
    if not connection:
        e = Exception()
        e.user_msg = 'Unable to connect to {}'.format(SQL_DSN["host"])
        raise e
    cursor = connection.cursor()

    wheres = [term]
    wheres.extend(build_stack_names)
    if DEBUG:
        print(str(wheres))
    cursor.execute(sql, wheres)
    desc = cursor.description
    buildreports = [dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()]
    return buildreports


def printDetailReport(buildreport, terminalsize):
    """
    Prints a detail report of a single build
    """
    if terminalsize == 0:
        terminalsize = 80

    try:
        br = json.loads(buildreport["report_text"], "utf-8")
        if DEBUG:
            print(repr(br))
    except Exception as e:
        e.user_msg = "Unable to parse the build report for this module.  Please report to rchelp."
        raise

    # Total width of terminal text
    width = terminalsize - 2

    # Margin on either side of long text
    textmargin = 6

    # Width to pass to TextWrapper
    textwidth = width - textmargin * 2

    # Border text
    border = "-" * width

    # Setup the text wrapper
    wrapper = TextWrapper(replace_whitespace=False, width=textwidth, initial_indent=" " * textmargin, subsequent_indent=" " * textmargin)
    descwrapper = TextWrapper(width=textwidth, initial_indent=" " * textmargin, subsequent_indent=" " * textmargin)

    # Get the app name
    app_name = br["title"]

    # Generate the dependencymessage if it exists
    dependencymessage = ""
    if br["run_dependencies"]:
        dependencymessage = """
    This module also loads:
{run_dependencies}
""".format(run_dependencies=wrapper.fill(" ".join(br["run_dependencies"])))

    # Generate the commentsmessage if it exists
    commentsmessage = ""
    if "comments" in br and br["comments"] and br["comments"].strip() != "":
        commentsmessage = """
    Build comments:
{comments}
""".format(comments=wrapper.fill(br["comments"]))

    # Build stack activation message
    buildstackactivationmessage = ""
    if "build_stack_activation" in br and br["build_stack_activation"]:
        buildstackactivationmessage = """
    {build_stack} activation:
{build_stack_activation}
""".format(build_stack=br["build_stack"], build_stack_activation=wrapper.fill(br["build_stack_activation"]))


    report = u"""
{border}
  {app_name} : {build_name}
{border}
    Build flavor: {build_stack}
    Description:
{descriptionlines}
{commentsmessage}
    This module can be loaded as follows:
      {moduleloadlines}
{dependencymessage}
{buildstackactivationmessage}

""".format(
        border=border,
        app_name=app_name,
        build_name=br["name"],
        descriptionlines=descwrapper.fill(br["description"]),
        moduleloadlines=br["activation"].replace("\n", "\n      "),
        dependencymessage=dependencymessage,
        commentsmessage=commentsmessage,
        build_stack=br["build_stack"],
        buildstackactivationmessage=buildstackactivationmessage,
    )
    print(report)


def printConsolidatedReport(buildreports, terminalsize):
    """
    Print a report for a set of builds for a particular application
    """
    if terminalsize == 0:
        terminalsize = 80

    # Total width of terminal text
    width = terminalsize - 2

    # Margin on either side of long text
    textmargin = 6
    # commentsmargin = 12

    # Width to pass to TextWrapper
    textwidth = width - textmargin * 2
    # commentswidth = width - commentsmargin

    # Border text
    border = "-" * width

    # Setup the text wrapper
    descwrapper = TextWrapper(width=textwidth, initial_indent=" " * textmargin, subsequent_indent=" " * textmargin)
    buildstackwrapper =  TextWrapper(width=textwidth, initial_indent=" " * textmargin, subsequent_indent=" " * 30)
    versionwrapper = TextWrapper(width=textwidth, initial_indent=" " * textmargin, subsequent_indent=" " * 58)

    apps = {}
    for buildreport in buildreports:
        try:
            br = json.loads(buildreport["report_text"])
            if DEBUG:
                print(repr(br))
        except Exception as e:
            e.user_msg = "Unable to parse the build report for this module.  Please report to rchelp."
            raise

        app_name = br["title"]
        if app_name not in apps:
            apps[app_name] = {}
            apps[app_name]["build_stacks"] = defaultdict(list)
        apps[app_name]["description"] = br["description"]
        moduletitle = br["name"]
        buildstack = br["build_stack"]

        buildcomments = ""
        if "comments" in br and br["comments"] and br["comments"].strip() != "":
            buildcomments = br["comments"]

        preferredbuild = ""
        preferredbuildexplanation = ""
        if br["preferred_build"]:
            preferredbuild = "* "
            preferredbuildexplanation = "* denotes preferred build."
        vstr = "{margin}{preferredbuild}{moduletitle:.<40} {buildcomments}".format(
            margin=" " * textmargin,
            moduletitle=moduletitle,
            buildcomments=buildcomments,
            preferredbuild=preferredbuild,
        )

        apps[app_name]["build_stacks"][br["build_stack"]].append(versionwrapper.fill(vstr))

    for app_name, details in apps.iteritems():
        build_stack_strs = []
        for build_stack, versionlines in details["build_stacks"].items():
            lines = [buildstackwrapper.fill(build_stack)]
            lines.extend(versionlines)
            build_stack_strs.append("\n".join(lines))

        report = u"""
{border}
  {app_name}
{border}
    Description:
{descriptionlines}

    Versions:
{versionlines}


    To find detailed information about a module, search the full name.

      module-query {example}

    You may need to specify the build "flavor" to get a single record

      module-query {example} --flavor '{exampleflavor}'

    {preferredbuildexplanation}


    """.format(
            border=border,
            app_name=app_name,
            descriptionlines=descwrapper.fill(details["description"]),
            versionlines="\n".join(build_stack_strs),
            example=moduletitle,
            exampleflavor=buildstack,
            preferredbuildexplanation=preferredbuildexplanation,
        )
        print(report)


def main(argv=None):
    """Command line options."""

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    program_name = os.path.basename(sys.argv[0])
    program_version = "v%s" % __version__
    program_build_date = str(__updated__)
    program_version_message = "%%(prog)s %s (%s)" % (program_version, program_build_date)
    program_shortdesc = "module-query -- Command line query of the applications database"
    program_license = """  %s


""" % (program_shortdesc)

    try:
        default_flavors = os.environ.get("FASRCSW_FLAVORS", "HeLmod CentOS 7,Easy Build,Singularity 3,Bioconda,Anaconda,x86_64 binary,Java")

        # Setup argument parser
        parser = ArgumentParser(description=program_license, formatter_class=RawDescriptionHelpFormatter)
        parser.add_argument("-v", "--verbose", dest="verbose", action="count", help="set verbosity level [default: %(default)s]")
        parser.add_argument("--flavors", dest="build_stacks", help="Comma separated list of application flavors [default: %(default)s]", default=default_flavors)
        parser.add_argument("--full-text", action="store_true", help="Search all text, including description.")
        parser.add_argument("build_name", metavar="BUILD", help="Build name.  May be partial.")

        # Process arguments
        args = parser.parse_args()
        build_stack_names = re.split(r'\s*,\s*', args.build_stacks)

        verbose = args.verbose

        if verbose > 0:
            print("Verbose mode on")

        build_name = args.build_name

        if verbose > 0:
            print("Searching for %s" % build_name)

        buildreports = fetchBuildReports(build_name, build_stack_names, args.full_text)

        if len(buildreports) == 0:
            sys.stderr.write("\nUnable to find a match for '%s' \nsearch was limited to build flavors %s\n\n" % (args.build_name, ', '.join(build_stack_names)))
            return 1

        # Do the full monty for a single match
        if len(buildreports) == 1:
            printDetailReport(buildreports[0], getTerminalSize())
        else:
            printConsolidatedReport(buildreports, getTerminalSize())

        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        if hasattr(e, "user_msg") and not DEBUG:
            sys.stderr.write(program_name + ": " + e.user_msg + "\n")
        else:
            sys.stderr.write(program_name + ": " + str(e) + "\n" + traceback.format_exc())
        sys.stderr.write("  for help use --help\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())

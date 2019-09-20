#!/usr/bin/python
# encoding: utf-8
"""
check-activation Tests the activation column of a Build record by trying to activate

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




def fetchBuildActivation(search, build_stack_names):
    """
    Uses SQL to fetch the matching build reports.  If
    fulltext is True, searches the build report text
    """
    if DEBUG:
        print('search {}, build_stack_names {}'.format(search, ','.join(build_stack_names)))

    term = '%{}%'.format(search)
    # Need (%s,%s,%s) for python 2 in clause
    format_strings = ','.join(['%s'] * len(build_stack_names))
    sql = """
        select
            b.name, b.activation
        from
            build b
                inner join build_stack bs on bs.id = b.build_stack_id
        where
            b.name like %s and
            bs.name in ({in_clause})
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
    builds = [dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()]
    return builds


def main():
    """Command line options."""

    argv = sys.argv

    program_name = os.path.basename(sys.argv[0])
    program_shortdesc = "check-activation -- Retrieve the activation code for builds and ensure that it returns 0"
    program_license = """  %s


""" % (program_shortdesc)

    try:
        default_flavors = os.environ.get("FASRCSW_FLAVORS", "HeLmod CentOS 7,Easy Build,Singularity 3,Bioconda,Anaconda,x86_64 binary,Java")

        # Setup argument parser
        parser = ArgumentParser(description=program_license, formatter_class=RawDescriptionHelpFormatter)
        parser.add_argument("--flavors", dest="build_stacks", help="Comma separated list of application flavors [default: %(default)s]", default=default_flavors)
        parser.add_argument("-v", dest="verbose", action="store_true", help="Get more output.")
        parser.add_argument("search", metavar="SEARCH", help="Build name search text.  Leave empty to get all of the builds for the application flavors")

        # Process arguments
        args = parser.parse_args()
        build_stack_names = re.split(r'\s*,\s*', args.build_stacks)
        search = args.search
        verbose = args.verbose

        builds = fetchBuildActivation(search, build_stack_names)

        if len(builds) == 0:
            sys.stderr.write("\nUnable to find a match for '%s' \nsearch was limited to build flavors %s\n\n" % (search, ', '.join(build_stack_names)))
            return 1

        verbosestr = " 2> /dev/null 1> /dev/null"
        if verbose:
            verbosestr = ""
        for build in builds:
            result = 'Fail'
            sys.stdout.write("Attempting {} for build {}... ".format(build["activation"], build["name"]))
            if os.system("module purge && {} {}".format(build["activation"], verbosestr)) == 0:
                result = 'Success'
            sys.stdout.write("{}\n".format(result))
        # Final module purge
        os.system("module purge")
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

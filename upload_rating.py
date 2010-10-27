"""
This is a rating (for the PALFA survey) that keeps track 
of which .pfd files are uploaded to Cornell. The value
stored is 1 if the file is successfully uploaded.

The upload to Cornell is performed as a side-effect.

Patrick Lazarus, July 22, 2010
"""
import types
import os.path
import subprocess

import pymssql

import rating
import config

USERNAME = "mtan"

if config.survey != "PALFA":
    raise ImportError("This rating is designed for use with PALFA survey only!")

def connect():
    # creates a connection to common DB
    connection = pymssql.connect(host=config.common_host, 
                                 user=config.common_usrname,
                                 password=config.common_pw, 
                                 database=config.common_database)
    cursor = connection.cursor()
    return cursor, connection


def upload_pfd(cursor, conn, cand_id, pfdfn):
    if type(cand_id) not in [types.IntType, types.LongType]:
        print "type(cand_id):", type(cand_id)
        print "cand_id:", cand_id
        raise ValueError("cand_id must be of type integer.")
    if not os.path.exists(pfdfn):
        raise ValueError("pfdfn doesn't point to an existing file: %s" % pfdfn)
    query = "EXEC spPDMCandPlotLoader " \
            "@pdm_cand_id=%d, " \
            "@pdm_plot_type='pfd binary', " \
            "@filename='%s', " \
            "@filedata=0x%s" \
            % (cand_id, os.path.split(pfdfn)[1], open(pfdfn, 'rb').read().encode('hex'))
    cursor.execute(query)
    conn.commit()
    result = cursor.fetchone()
    if not result:
        raise UploadError("Plot upload failed!")


class UploadError(Exception):
    pass


class UploadRating(rating.DatabaseRater):
    def __init__(self, DBconn):
        rating.DatabaseRater.__init__(self, DBconn, version=0,
                name="Upload Rating",
                description="Is .pfd file uploaded to Cornell? " \
                            "Uploads file as side-effect.",
                with_files=True)
        self.cursor, self.conn = connect()

    def __del__(self):
        self.conn.close()

    def rate_candidate(self, hdr, candidate, pfd, cache=None):
        cand_id = candidate['cornell_pdm_cand_id']
        if cand_id is None:
            raise UploadError("Candidate must be uploaded to Cornell " \
                              "before .pfd file can be uploaded.")
        upload_pfd(self.cursor, self.conn, cand_id, pfd.pfd_filename)
        return 1


def share_pfd(pfdfn):
    """Send pfd file to mcgill using a system call to rsync.
    """
    if not os.path.exists(pfdfn):
        raise ValueError("pfdfn doesn't point to an existing file: %s" % pfdfn)
    cmd = "rsync -u pfdfn %s@miarka.physics.mcgill.ca:/data/alfa/PALFA/pfds/%s/%s" % \
                    (USERNAME, config.institution, os.path.split(pfdfn)[-1])
    retcode = subprocess.call(cmd, shell=True)
    if retcode != 0:
        raise ShareError("Rsync of pfd file (%s) failed!" % pfdfn)


class ShareError(Exception):
    pass


class SharePfdRating(rating.DatabaseRater):
    def __init__(self, DBconn):
        import subprocess
        rating.DatabaseRater.__init__(self, DBconn, version=0,
                name="Share PFD Rating",
                description="Copy .pfd file to McGill as a side-effect.",
                with_files=True)
        self.cursor, self.conn = connect()

    def __del__(self):
        self.conn.close()

    def rate_candidate(self, hdr, candidate, pfd, cache=None):
        cand_id = candidate['cornell_pdm_cand_id']
        if cand_id is None:
            raise ShareError("Candidate must be uploaded to Cornell " \
                              "before .pfd file should be shared.")
        share_pfd(pfd.pfd_filename)
        return 1

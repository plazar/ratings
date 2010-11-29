#!/usr/bin/env python

"""
Upload pfd files to Cornell.

Patrick Lazarus, November 25, 2010
"""

import rating

def main():
    import upload_rating
    D = rating.usual_database()
    rating.run(D, [upload_rating.UploadRating(D)])

if __name__ == '__main__':
    main()

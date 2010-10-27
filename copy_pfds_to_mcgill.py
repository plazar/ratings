!#/usr/bin/env python

"""
Copy pfd files to McGill.

Patrick Lazarus, Oct. 25, 2010
"""

import rating

def main()
    import upload_rating
    D = rating.usual_database()
    rating.run(D, [upload_rating.SharePfdRating(D)])

if __name__ == '__main__':
    main()

#!/usr/bin/env python
"""
composite_rating_report.py

Create a report consisting of a series of diagnostics for
a composite rating.

Patrick Lazarus, Oct 26, 2009
"""

import optparse
import sys
import textwrap
import re

import matplotlib.pyplot as plt

import colour
import rating_utils

NUMBINS_DEFAULT = 1000

def get_all_rating_types():
    """Return available ratings from database.
    Each rating is describe using a dictionary.
    All dictionaries are stored in a list.
    """
    return rating_utils.get_data("SELECT * FROM rating_types;", dictcursor=True)


def get_rating_types(rating_ids):
    """Return dictionary describing rating_types with
    rating_ids. Dictionaries are stored in a list.

    rating_ids is a list of integers.
    """
    return rating_utils.get_data("SELECT * FROM rating_types " \
				 "WHERE rating_id IN (%s)" % \
				 ','.join([str(id) for id in rating_ids]), \
				 dictcursor=True)
    

def format_rating(rating_type, complete=False):
    """Return formatted string describing rating type
    given a dictionary of information about the rating
    type.
    """
    formatted = colour.cstring("Rating", bold=1) + ": " + \
		colour.cstring("%(name)s" % rating_type, underline=1) + " " + \
		"v%(version)d\n\t(ID: %(rating_id)d)" % rating_type
    if complete:
	paragraphs = rating_type['description'].split('\n')
	description = '\n'.join([textwrap.fill(p.strip(), width=60, \
				initial_indent='\t', subsequent_indent='\t') \
				for p in paragraphs])
	rating_type['description'] = description
	formatted += "\n%(description)s" % rating_type
    return formatted


def get_tables(prepped_string):
    """Return a list of MySQL tables to use.
    """
    tables = []
    if 'pdm_candidates.' in prepped_string:
	tables.append('pdm_candidates')
    if 'headers.' in prepped_string:
	tables.append('headers')
    for match in re.findall(r'(rat[0-9]*).', prepped_string):
	tables.append(match)

    return sorted(list(set(tables)))


def prep_composite_rating(string):
    """Return a string of the composite rating to be used
    in MySQL.

    This step is essentially a search and replace for:
    c{field} => c.field
    h{field} => h.field
    r{#} => rat#.value
    """
    # replace candidate table fields
    string = re.sub(r"c\{([^}]*)\}", r"pdm_candidates.\1", string)
    # replace header table fields
    string = re.sub(r"h\{([^}]*)\}", r"headers.\1", string)
    # replace ratings
    string = re.sub(r"r\{([0-9]*)\}", r"rat\1.value", string)
    return string
    

def build_query(prepped_string, where="1", no_test=False, classifications=[]):
    """Build and return MySQL query that will compute
    the composite rating described by prepped_string.

    'where' determines what candidates to use. Default is to use all cands.
    'no_test' determines if test pulsars should not be returned.
    'classifications' determines what human rankings should be returned.
    """
    # Get list of tables to use
    rating_tables = get_tables(prepped_string)
    where_tables = get_tables(where)
  
    tables = sorted(list(set(where_tables+rating_tables)))
    
    if no_test:
	if 'headers' not in tables:
	    tables.append('headers')
	    tables.sort()
    
    if len(classifications) > 0:
	if 'pdm_classifications' not in tables:
	    tables.append('pdm_classifications')
	    tables.sort()
    
    query = "SELECT %s AS composite_rating FROM pdm_candidates " % prepped_string
    for table in tables:
	if table == 'headers':
	    query += " LEFT JOIN headers ON "
	    query += " headers.header_id = pdm_candidates.header_id "
	elif table == 'pdm_classifications':
	    pdm_class_type_id = rating_utils.get_default_pdm_class_type_id()
	    query += " LEFT JOIN pdm_classifications ON "
	    query += " pdm_candidates.pdm_cand_id = pdm_classifications.pdm_cand_id AND"
	    query += " pdm_classifications.pdm_class_type_id = %d AND " % pdm_class_type_id
	    query += " pdm_classifications.who = 'PL' "
	elif table.startswith('rat'):
	    query += " LEFT JOIN ratings AS %s ON " % table
	    query += " %s.pdm_cand_id = pdm_candidates.pdm_cand_id AND " % table
	    query += " %s.rating_id = %s " % (table, table[3:])
   
    query += "WHERE %s " % where
   
    if no_test:
	query += " AND headers.source_name LIKE 'G%' "
    if len(classifications) > 0:
	query += " AND pdm_classifications.rank IN (%s) " % \
		    ','.join([str(cl) for cl in classifications])
    query += " HAVING composite_rating IS NOT NULL"
    
    return query 
   

def produce_report(prepped_string, where="1", numbins=NUMBINS_DEFAULT, \
		    norm=False, log=False):
    """Produce a series of diagnostic plots given 
    the composite rating descibed in 'prepped_string'.

    'where' is a MySQL where clause to limit the candidates used.
    'numbins' is the number of bins to use in histograms
    'norm' is boolean. Determines if area under histograms should
	    be normalized to 1.
    'log' is boolean. Determines if vertical axis is log (base 10).
    """
    fig = plt.figure()

    # Plot all ratings in black
    query = build_query(prepped_string, where=where)
    ratings = rating_utils.get_data(query)
    if len(ratings):
	all_hist = plt.hist(ratings, numbins, edgecolor='k', histtype='step', \
		label="All Cands (%d)" % len(ratings), normed=norm)
    
    # Plot bad ratings (RFI, Noise) in red
    query = build_query(prepped_string, where=where, classifications=[4,5])
    ratings = rating_utils.get_data(query)
    if len(ratings):
	bad_hist = plt.hist(ratings, numbins, edgecolor='r', histtype='step', \
		label="RFI/Noise (%d)" % len(ratings), normed=norm)

    # Plot pulsars (known, harmonic) in green
    query = build_query(prepped_string, where=where, classifications=[6,7])
    ratings = rating_utils.get_data(query)
    if len(ratings):
	psr_hist = plt.hist(ratings, numbins, edgecolor='g', histtype='step', \
		label="Known/Harmonic (%d)" % len(ratings), normed=norm)
    
    # Plot good ratings (class 1, 2, 3) in blue
    query = build_query(prepped_string, where=where, classifications=[1,2,3])
    ratings = rating_utils.get_data(query)
    if len(ratings):
	good_hist = plt.hist(ratings, numbins, edgecolor='c', histtype='step', \
		label="Class 1/2/3 (%d)" % len(ratings), normed=norm)

    # Label plot
    plt.title(prepped_string)
    plt.xlabel("Composite rating value")
    plt.ylabel("Number")
    
    # legend
    leg = plt.legend(loc='best')
    leg.get_frame().set_alpha(0.5)
    
    # set vertical axis to log
    if log:
	ymin, ymax = plt.ylim()
	plt.ylim(0.1, ymax)
	plt.yscale('log')
    
    def onpress(event):
	if event.key in ('q', 'Q'):
	    sys.exit(0)
    
    fig.canvas.mpl_connect('key_press_event', onpress)
    
    plt.show()
   

def main():
    if len(args) < 1:
	sys.stderr.write("No rating string provided! Exiting...\n")
	sys.exit(1)
    rating_string = ' '.join(args)
    print "Input composite rating string: ", rating_string
    
    prepped_string = prep_composite_rating(rating_string)
    print "Prepped composite rating string:", prepped_string
    rating_tables = get_tables(prepped_string)
   
    where_clause = prep_composite_rating(options.where_clause)
    print "Where clause:", where_clause
    where_tables = get_tables(where_clause)
  
    tables = sorted(list(set(where_tables+rating_tables)))
    print "MySQL DB tables to use:", ', '.join(tables)

    query = build_query(prepped_string, where=where_clause)
    print "MySQL query to compute composite rating:"
    print textwrap.fill(query, width=72, initial_indent='\t', subsequent_indent='\t')

    produce_report(prepped_string, numbins=options.numbins, \
			where=where_clause, norm=options.norm, \
			log=options.log)


if __name__=='__main__':
    parser = optparse.OptionParser(usage="%prog [options] composite-rating", \
			    description="Create a report consisting of a series " \
					"of diagnostics for a composite rating", \
			    version="%prog v0.1 (by Patrick Lazarus)", \
			    prog="composite_rating_report.py")
    parser.add_option('-l', '--list-ratings', dest='list_ratings', \
			    action='store_true', help="List ratings available and exit.", \
			    default=False)
    parser.add_option('-d', '--describe-rating', dest='describe_rating', \
			    type='int', help="Describe rating with given ID and exit.", \
			    default=None)
    parser.add_option('-w', '--where', dest='where_clause', help="Where clause " \
			    "to be executed in MySQL db to limit candidates " \
			    "selected. (Default: Use all candidates.)", default="1")
    parser.add_option('-b', '--numbins', dest='numbins', type='int', \
			    help="Number of bins for composite rating " \
			    "histogram. (Default: 1000)", \
			    default=NUMBINS_DEFAULT)
    parser.add_option('-n', '--norm', dest='norm', action='store_true', \
			    help="Normalize each histogram so area under " \
			    "the curve is 1. (Default: Don't normalize)", 
			    default=False)
    parser.add_option('--log', dest='log', action='store_true', \
			    help="Use a log vertical axis. (Default: "\
			    "No log axis.)", default=False)
    options, args = parser.parse_args()
    
    if options.list_ratings:
	# List ratings and exit
	rating_types = get_all_rating_types()
	for rt in rating_types:
	    print format_rating(rt, complete=False)
	sys.exit(0)
	
    if options.describe_rating is not None:
	# Describe rating and exit
	rt = get_rating_types([options.describe_rating])[0]
	print format_rating(rt, complete=True)
	sys.exit(0)
    
    main()

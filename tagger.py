#!/usr/bin/python

"""
A python script to tag comic archives
"""

"""
Copyright 2012  Anthony Beville

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

	http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import sys
import getopt
import json
import xml
from pprint import pprint 
from PyQt4 import QtCore, QtGui
import signal
import os
import math
import urllib2, urllib 

from settings import ComicTaggerSettings

from taggerwindow import TaggerWindow
from options import Options, MetaDataStyle
from comicarchive import ComicArchive

from comicvinetalker import ComicVineTalker
from comicinfoxml import ComicInfoXml
from comicbookinfo import ComicBookInfo
from imagehasher import ImageHasher
import utils

#-----------------------------
def cliProcedure( opts, settings ):

	ca = ComicArchive(opts.filename)
	if not ca.seemsToBeAComicArchive():
		print "Sorry, but "+ opts.filename + "  is not a comic archive!"
		return
	
	cover_image_data = ca.getCoverPage()
	#cover_hash = ImageHasher( data=cover_image_data ).average_hash() 
	#print "Cover hash = ",cover_hash

	cover_hash = ImageHasher( data=cover_image_data ).average_hash2() 
	#print "Cover hash = ",cover_hash

	#cover_hash = ImageHasher( data=cover_image_data , width=32, height=32 ).perceptual_hash() 

	# see if the archive has any useful meta data for searching with
	if ca.hasCIX():
		internal_metadata = ca.readCIX()
	elif ca.hasCBI():
		internal_metadata = ca.readCBI()
	else:
		internal_metadata = ca.readCBI()

	# try to get some metadata from filename
	md_from_filename = ca.metadataFromFilename()
	
	# now figure out what we have to search with
	search_series = internal_metadata.series
	search_issue_number = internal_metadata.issueNumber
	search_year = internal_metadata.publicationYear
	search_month = internal_metadata.publicationMonth
	
	if search_series is None:
		search_series = md_from_filename.series
	
	if search_issue_number is None:
		search_issue_number = md_from_filename.issueNumber
		
	if search_year is None:
		search_year = md_from_filename.publicationYear
		
	# we need, at minimum, a series and issue number
	if search_series is None or search_issue_number is None:
		print "Not enough info for a search!"
		return

	print ( "Going to search for:" )
	print ( "Series: ", search_series )
	print ( "Issue : ", search_issue_number ) 
	if search_year is not None:
		print ( "Year :  ", search_year ) 
	if search_month is not None:
		print ( "Month : ", search_month )
	
	
	comicVine = ComicVineTalker( settings.cv_api_key )

	print ( "Searching for " + search_series + "...")

	cv_search_results = comicVine.searchForSeries( search_series )

	print "Found " + str(len(cv_search_results)) + " initial results"
	
	series_shortlist = []
	
	print "Removing results with too long names"
	for item in cv_search_results:
		#assume that our search name is close to the actual name, say within 8 characters
		if len( item['name']) < len( search_series ) + 8:
			series_shortlist.append(item)
	
	# if we don't think it's an issue number 1, remove any series' that are one-shots
	if search_issue_number != '1':
		print "Removing one-shots"
		series_shortlist[:] = [x for x in series_shortlist if not x['count_of_issues'] == 1]	

	print "Finally, searching in " + str(len(series_shortlist)) +" series" 
	
	# now sort the list by name length
	series_shortlist.sort(key=lambda x: len(x['name']), reverse=False)
	
	# Now we've got a list of series that we can dig into, 
	# and look for matching issue number, date, and cover image
	
	
	for series in series_shortlist:
		#print series['id'], series['name'], series['start_year'], series['count_of_issues']
		print "Fetching info for  ID: {0} {1} ({2}) ...".format(
		               series['id'], 
		               series['name'], 
		               series['start_year'])
		
		cv_series_results = comicVine.fetchVolumeData( series['id'] )
		issue_list = cv_series_results['issues']
		for issue in issue_list:
			
			# format the issue number string nicely, since it's usually something like "2.00"
			num_f = float(issue['issue_number'])
			num_s = str( int(math.floor(num_f)) )
			if math.floor(num_f) != num_f:
				num_s = str( num_f )			

			# look for a matching issue number
			if num_s == search_issue_number:
				# found a matching issue number!  now get the issue data 
				img_url = comicVine.fetchIssueCoverURL( issue['id'] )
				#TODO get the URL, and calc hash!!
				url_image_data = urllib.urlopen(img_url).read()
				#url_image_hash = ImageHasher( data=url_image_data ).average_hash() 
				url_image_hash = ImageHasher( data=url_image_data,   ).average_hash2() 
				#url_image_hash = ImageHasher( data=url_image_data, width=32, height=32  ).perceptual_hash() 
				print u"-----> ID: {0}  #{1} ({2}) Hash: {3}  Distance: {4}\n-------> url:{5}".format(
				                             issue['id'], num_s, issue['name'],
				                             url_image_hash, 
				                             ImageHasher.hamming_distance(cover_hash, url_image_hash),
				                             img_url)
				
				
				break
	
	"""
	#error checking here:  did we get any results?

	# we will eventualy  want user interaction to choose the appropriate result, but for now, assume the first one
	series_id = cv_search_results[0]['id'] 

	print( "-->Auto-selecting volume ID:", cv_search_results[0]['id'] )
	print(" ") 

	# now get the particular issue data
	metadata = comicVine.fetchIssueData( series_id, opts.issue_number )

	#pprint( cv_volume_data, indent=4 )

	ca = ComicArchive(opts.filename)
	ca.writeMetadata( metadata, opts.data_style )

	#debugging
	ComicBookInfo().writeToExternalFile( "test.json" )
	ComicBookInfo().writeToExternalFile( "test.xml" )
	"""
#-----------------------------

def main():
	opts = Options()
	opts.parseCmdLineArgs()
	settings = ComicTaggerSettings()
	
	# make sure unrar program is in the path for the UnRAR class
	utils.addtopath(os.path.dirname(settings.unrar_exe_path))
	
	signal.signal(signal.SIGINT, signal.SIG_DFL)
	
	if opts.no_gui:

		cliProcedure( opts, settings )
		
	else:

		app = QtGui.QApplication(sys.argv)
		tagger_window = TaggerWindow( opts, settings )
		tagger_window.show()
		sys.exit(app.exec_())

if __name__ == "__main__":
    main()
    
    
    
    
    
This script reads an ecodms-export and imports the documents to paperless-ngx

This script is crap. hacky, untested crap. I wrote it just for a single import for me - but then I gost asked by friends if I may share it. 

To use this script, create an export in ecodms (version 18.09 in my case) with a search string
like "docid >= 0". This will export all of your documents in a zip file with an xml-file "export.xml"

Please be aware that currently you can not import self defined metadata - only correspondents and tags are being imported.
Feel free to alter this code to include Metadata in the title - in my case I use my field "bemerkung" as title.

Please configure your environment (place of the ecodms export and paperless instance) in the first lines of the script.

Please take this script as inspiration - it was build exactly for my use case and it does not include 
any sanity checks or precautions. Please make a backup of your paperless instance....

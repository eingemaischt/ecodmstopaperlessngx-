from xml.dom import minidom
import pathlib
from pprint import pprint
import requests
from requests.auth import HTTPBasicAuth
import logging
import http.client as http_client
import json

# To use this script, create an export in ecodms (version 18.09 in my case) with a search string
# like "docid >= 0". This will export all of your documents in a zip file with an xml-file "export.xml"

# Please be aware that currently you can not import self defined metadata - only correspondents and tags are being imported.
# Feel free to alter this code to include Metadata in the title - in my case I use my field "bemerkung" as title.


# Where is your ecodms export saved?
ecodmsfolder = "~/ecodms/offline_export"
archiveFolder = ecodmsfolder + "/archive/"
exportXMLFile = archiveFolder + "export.xml"

# Configure your paperless URL and credentials
paperlessurl = "http://xxx.yyy.zzz.hhh:8000"
paperlessuser = "importer"
paperlesspassword = "xxx"
paperlesscert = False #Set to False if no ssl verification is needed, true if "real" cert is used or path to a cert for manual check

# Filetypes that can be put into paperless directly - in this case the original file instead of 
# the pdf representation is chosen. Please update to your needs, I included only the extensions 
# I had files with
supportedFiletyped = [".pdf", ".jpg", ".tif", ".odt", ".docx", ".doc"]

# You must initialize logging, otherwise you'll not see debug output.
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

#http_client.HTTPConnection.debuglevel = 1 # Full Request logging

# TODO: recognized if a file is "trashed" (atm even the trashed files are being imported)

def getVersionMetadata(version):
    tags = []
    correspondent = ""
    created = ""
    bemerkung = ""
    dokumentenart = ""
    dateinameOrig = ""
    dateiname = ""
    try:
        #Betrifft was a custom field in ecodms which defines whom of my family the document is related to
        betrifft = version.getElementsByTagName('betrifft')[0].firstChild.nodeValue
        if betrifft == 'Philipp':
            tags.append('Philipp')
    except:
        pass
    try:
        if version.getElementsByTagName('hauptordner')[0].firstChild.nodeValue not in tags:
            tags.append(version.getElementsByTagName('hauptordner')[0].firstChild.nodeValue)
    except:
        pass
    try:
        if version.getElementsByTagName('ordner')[0].firstChild.nodeValue not in tags:
            tags.append(version.getElementsByTagName('ordner')[0].firstChild.nodeValue)
    except:
        pass
    try:
        extkeyvalue = version.getElementsByTagName('ordner-extkey')[0].firstChild.nodeValue
        for key in extkeyvalue.split(","):
            if key.strip() not in tags:
                tags.append(key.strip())
    except:
        pass
    try:
        correspondent = version.getElementsByTagName('gegenüber')[0].firstChild.nodeValue
    except:
        pass     
    try:
        created = version.getElementsByTagName('datum')[0].firstChild.nodeValue
    except:
        pass   
    try:
        dokumentenart = version.getElementsByTagName('dokumentenart')[0].firstChild.nodeValue
    except:
        pass  
    try:
        bemerkung = version.getElementsByTagName('bemerkung')[0].firstChild.nodeValue
    except:
        pass 

    #null is the value for folder or extkey if nothing is filled in
    if 'null' in tags:
        tags.remove('null')

    metadata = {
        'tags' : tags,
        'correspondent' : correspondent,
        'created' : created,
        'bemerkung' : bemerkung,
        'document_type': dokumentenart
    }
    return metadata
    
def getFileInformation(document):
    files = document.getElementsByTagName('files')
    filename = archiveFolder + files[0].attributes['filePath'].value
    origFilename = files[0].attributes['origname'].value
    id = files[0].attributes['id'].value
    # Now we set the backup file information. Let's see if there are better suitable versions
    fileVersion = files[0].getElementsByTagName('fileVersion')
    if len(fileVersion) > 0:
        maxVersionId = 0
        maxVersion = 0
        for fV in fileVersion:
            if int(fV.attributes['version'].value) > maxVersionId:
                maxVersion = fV
                maxVersionId = int(fV.attributes['version'].value)
        if maxVersionId > 0:
            if pathlib.Path(fV.attributes['origname'].value).suffix.lower() in supportedFiletyped:
                origFilename = fV.attributes['origname'].value
                filename = archiveFolder + fV.attributes['filePath'].value
            else:
                #origFilename = fV.getElementsByTagName('pdfFile')[0].attributes['origName'].value
                #filename = archiveFolder + fV.getElementsByTagName('pdfFile')[0].attributes['filePath'].value
                #The Backup files often don't exist....
                pass
    fileInformation = {
        'id': id,
        'filename' : filename,
        'origFilename' : origFilename,
    }
    return fileInformation

def createAndEnsureTags(importData):
    #Get all known tags
    r = requests.get(
        paperlessurl + "/api/tags/",
        verify=paperlesscert,
        auth=(paperlessuser, paperlesspassword),
    )
    results = r.json()["results"]
    while r.json()["next"] != None:
        r = requests.get(
            r.json()["next"],
            verify=paperlesscert,
            auth=(paperlessuser, paperlesspassword),
        )
        results = results + r.json()["results"]

    pltags = {}
    for t in results:
        pltags[t["name"]] = t["id"]

    for doc in importData:
        newtags = []
        for tag in importData[doc]["tags"]:
            if tag in pltags:
                newtags.append(str(pltags[tag]))
            else:
                r = requests.post(
                    paperlessurl + "/api/tags/",
                    verify=paperlesscert,
                    auth=(paperlessuser, paperlesspassword),
                    data={
                        "name": tag
                    }
                )
                if r.status_code == 400:
                    print(f"Tag {tag} was not created successfully")
                    print(r.content)
                newtags.append(str(r.json()["id"])) 
                pltags[tag] = str(r.json()["id"])
        importData[doc]["tags"] = newtags

def createAndEnsureCorrespondents(importData):
    #Get all known correspondents
    r = requests.get(
        paperlessurl + "/api/correspondents/",
        verify=paperlesscert,
        auth=(paperlessuser, paperlesspassword),
    )
    results = r.json()["results"]
    while r.json()["next"] != None:
        r = requests.get(
            r.json()["next"],
            verify=paperlesscert,
            auth=(paperlessuser, paperlesspassword),
        )
        results = results + r.json()["results"]
    
    plcorrespondents = {}
    for c in results:
        plcorrespondents[c["name"]] = c["id"]

    for doc in importData:
        if importData[doc]["correspondent"] == "":
            continue
        if importData[doc]["correspondent"] in plcorrespondents:
            importData[doc]["correspondent"] = str(plcorrespondents[importData[doc]["correspondent"]])
        else:
            r = requests.post(
                paperlessurl + "/api/correspondents/",
                verify=paperlesscert,
                auth=(paperlessuser, paperlesspassword),
                data={
                    "name": importData[doc]["correspondent"]
                }
            )
            if r.status_code == 400:
                print(f"Correspondent {importData[doc]['correspondent']} was not created successfully")
                print(r.text)
            plcorrespondents[importData[doc]["correspondent"]] = paperlessurl + "/api/correspodents/" + str(r.json()["id"])
            importData[doc]["correspondent"] = paperlessurl + "/api/correspodents/" + str(r.json()["id"])   

def createAndEnsureDocumentTypes(importData):
    #Get all known correspondents
    r = requests.get(
        paperlessurl + "/api/document_types/",
        verify=paperlesscert,
        auth=(paperlessuser, paperlesspassword),
    )
    results = r.json()["results"]
    while r.json()["next"] != None:
        r = requests.get(
            r.json()["next"],
            verify=paperlesscert,
            auth=(paperlessuser, paperlesspassword),
        )
        results = results + r.json()["results"]
    
    pldoctypes = {}
    for c in results:
        pldoctypes[c["name"]] = c["id"]

    for doc in importData:
        print(importData[doc])
        if importData[doc]["document_type"] == "":
            continue
        if importData[doc]["document_type"] in pldoctypes:
            print(f'Set {pldoctypes[importData[doc]["document_type"]]} for {importData[doc]["document_type"]}')
            importData[doc]["document_type"] = str(pldoctypes[importData[doc]["document_type"]])
        else:
            r = requests.post(
                paperlessurl + "/api/document_types/",
                verify=paperlesscert,
                auth=(paperlessuser, paperlesspassword),
                data={
                    "name": importData[doc]["document_type"]
                }
            )
            if r.status_code == 400:
                print(f"Document type {importData[doc]['document_type']} was not created successfully")
                print(r.text)
            pldoctypes[importData[doc]["document_type"]] = str(r.json()["id"])
            importData[doc]["document_type"] = str(r.json()["id"])      

def postPaperless(doc):
    posturl = paperlessurl + "/api/documents/post_document/"
    multipartFields = {}
    if doc['bemerkung'] != "" and doc['bemerkung'] != "null":
        multipartFields["title"] = doc['bemerkung']
    if doc['correspondent'] != "" and doc['correspondent'] != "null":
        multipartFields["correspondent"] = doc['correspondent']
    multipartFields["tags"] = doc["tags"]
    if doc['document_type'] != "" and doc['document_type'] != "null":
        multipartFields["document_type"] = doc['document_type']
    if doc['created'] != "" and doc['created'] != "null":
        multipartFields["created"] = doc['created']

    print(multipartFields)

    r = requests.post(
        posturl,
        verify = paperlesscert,
        auth=(paperlessuser, paperlesspassword),
        data=multipartFields, 
        files={'document': (doc['origFilename'], open(doc['filename'], 'rb')) }
    )
    print(r.text)
    if r.status_code == 400:
        print(f"Doc {doc} was not created successfully. multipartFiels: {multipartFields}")
        print(r.text)
    #created: The date at which this document was created.
    #archive_serial_number: The identifier of this document in a physical document archive.
    

def main():
    importData = {}
    with minidom.parse(exportXMLFile) as xml:
        documents = xml.getElementsByTagName('document')
        for d in documents:
            # Den neuesten Versionsdatensatz heraus finden und getVersionMetadata machen
            # 
            fileInformation = getFileInformation(d)
            versions = d.getElementsByTagName('Version')
            newestVersion = versions[0]
            for v in versions:
                if float(v.getElementsByTagName('revision')[0].firstChild.nodeValue) > float(newestVersion.getElementsByTagName('revision')[0].firstChild.nodeValue):
                    newestVersion = v
            metaInformation = getVersionMetadata(newestVersion)
            importData[fileInformation['id']] = fileInformation | metaInformation

    createAndEnsureTags(importData)
    createAndEnsureCorrespondents(importData)
    createAndEnsureDocumentTypes(importData)

    for id in importData:
        print(f"Post data of {id}")
        postPaperless(importData[id])
            

if __name__ == "__main__":
    main()

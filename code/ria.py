#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import csv
import os
import sys
import socket
import boto3
from urllib.request import urlretrieve
import uuid
import shutil
from decimal import Decimal
import json
from threading import Thread
import io
from botocore.client import Config
from PIL import Image
from io import BytesIO
import base64
from PIL.ExifTags import TAGS


# In[ ]:


# In SageMaker update boto3
#!conda upgrade -y boto3

#import boto3
#print(boto3.__version__)


# In[ ]:


class RiaHelper:
    @staticmethod
    def getS3PresignedUrl(awsRegion, bucketName, imageName, expirationTime):
        s3 = boto3.client('s3', region_name=awsRegion, config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))

        #print("Signing Request: Region: {}, Bucket: {}, imageName: {}, expiration: {} ".format(awsRegion, bucketName, imageName, expirationTime))

        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': bucketName,
                'Key': imageName
            },
            ExpiresIn=expirationTime
        )

        #print("Signed URL: " + url)
        return url

    @staticmethod
    def uploadFileToS3(localFile, awsRegion, bucketName, s3FileName):
        s3 = boto3.resource('s3', region_name=awsRegion)
        s3.meta.client.upload_file(localFile, bucketName, s3FileName)

    @staticmethod
    def writeToS3(content, awsRegion, bucketName, s3FileName):
        s3 = boto3.resource('s3', region_name=awsRegion)
        object = s3.Object(bucketName, s3FileName)
        object.put(Body=content)

    @staticmethod
    def readFromS3(awsRegion, bucketName, s3FileName):
        s3 = boto3.resource('s3', region_name=awsRegion)
        obj = s3.Object(bucketName, s3FileName)
        return obj.get()['Body'].read().decode('utf-8')

    @staticmethod
    def writeToS3WithOptions(byteArray, awsRegion, bucketName, s3FileName, permissions, contentType):
        s3client = boto3.client('s3', region_name=awsRegion)
        response = s3client.put_object(
            ACL= permissions,
            Body=byteArray,
            Bucket=bucketName,
            ContentType=contentType,
            Key=s3FileName
        )


# In[ ]:


class RiaInput:

    def __init__(self, bucketName):
        ''' Constructor. '''
        self.bucketName = bucketName
        self.imagesDirectory = ""
        self.outputDirectory = ""
        self.concurrencyControl = 100
        self.maxPages = 10
        self.maxItemsPerPage = 1000
        self.minimumConfidence = 50
        self.exportCSV = True
        self.collectionId = ""
        self.s3PresignedExpirationTime = 604800

    def printAll(self):
        print("AWS Region: {}".format(self.awsRegion))
        print("Input Bucket: {}\nInput Directory: {}\nOutput Bucket: {}\nOutput Directory: {}".format(
                self.bucketName, self.imagesDirectory, self.outputBucketName, self.outputDirectory ))
        print("Minimum Confidence: {}".format(self.minimumConfidence))
        print("Concurrency: {}\nMax Pages: {}\nMax Items Per Page: {}\nMinimum Confidence: {}".format(
            self.concurrencyControl, self.maxPages, self.maxItemsPerPage, self.minimumConfidence))
        print("S3 PreSigned Expiration Time: {}".format(self.s3PresignedExpirationTime))
        print("Rekognition Collection ID: {}".format(self.collectionId))
        print("Generate CSV Output: {}".format(self.exportCSV))

    def printForUser(self):
        print("AWS Region: {}".format(self.awsRegion))
        print("Input Bucket: {}\nInput Directory: {}\nOutput Bucket: {}\nOutput Directory: {}".format(
                self.bucketName, self.imagesDirectory, self.outputBucketName, self.outputDirectory ))
        print("Minimum Confidence: {}".format(self.minimumConfidence))
        #print("Concurrency: {}\nMax Pages: {}\nMax Items Per Page: {}\nMinimum Confidence: {}".format(
        #    self.concurrencyControl, self.maxPages, self.maxItemsPerPage, self.minimumConfidence))
        print("S3 PreSigned Expiration Time: {}".format(self.s3PresignedExpirationTime))
        print("Rekognition Collection ID: {}".format(self.collectionId))
        print("Generate CSV Output: {}".format(self.exportCSV))


# In[ ]:


class LabelsProcessor(Thread):

    def __init__(self, imageName, inputParameters, dataObject):
        ''' Constructor. '''
        Thread.__init__(self)
        self.imageName = imageName
        self.inputParameters = inputParameters
        self.dataObject = dataObject

    def run(self):
        try:
            rekognition = boto3.client('rekognition', region_name=self.inputParameters.awsRegion)
            labels = rekognition.detect_labels(
                Image={
                    'S3Object': {
                        'Bucket': self.inputParameters.bucketName,
                        'Name': self.imageName,
                    }
                },
                MinConfidence = self.inputParameters.minimumConfidence
            )

            self.dataObject['Labels'] = labels
        except Exception as e:
            #print("Failed to process labels for {}. Error: {}.".format(self.imageName, e))
            self.dataObject['Labels'] = { 'Error' : "{}".format(e)}


# In[ ]:


class ModerationLabelsProcessor(Thread):

    def __init__(self, imageName, inputParameters, dataObject):
        ''' Constructor. '''
        Thread.__init__(self)
        self.imageName = imageName
        self.inputParameters = inputParameters
        self.dataObject = dataObject

    def run(self):
        try:
            rekognition = boto3.client('rekognition', region_name=self.inputParameters.awsRegion)
            moderationLabels = rekognition.detect_moderation_labels(
                Image={
                    'S3Object': {
                        'Bucket': self.inputParameters.bucketName,
                        'Name': self.imageName,
                    }
                },
                MinConfidence = self.inputParameters.minimumConfidence
            )

            self.dataObject['ModerationLabels'] = moderationLabels
        except Exception as e:
            #print("Failed to process moderation labels for {}. Error: {}.".format(self.imageName, e))
            self.dataObject['ModerationLabels'] = { 'Error' : "{}".format(e)}


# In[ ]:


class CelebritiesProcessor(Thread):

    def __init__(self, imageName, inputParameters, dataObject):
        ''' Constructor. '''
        Thread.__init__(self)
        self.imageName = imageName
        self.inputParameters = inputParameters
        self.dataObject = dataObject

    def run(self):
        try:
            rekognition = boto3.client('rekognition', region_name=self.inputParameters.awsRegion)
            celebrities = rekognition.recognize_celebrities(
                Image={
                    'S3Object': {
                        'Bucket': self.inputParameters.bucketName,
                        'Name': self.imageName,
                    }
                }
            )

            self.dataObject['Celebrities'] = celebrities
        except Exception as e:
            #print("Failed to process celebrities for {}. Error: {}.".format(self.imageName, e))
            self.dataObject['Celebrities'] = { 'Error' : "{}".format(e)}


# In[ ]:


class TextProcessor(Thread):

    def __init__(self, imageName, inputParameters, dataObject):
        ''' Constructor. '''
        Thread.__init__(self)
        self.imageName = imageName
        self.inputParameters = inputParameters
        self.dataObject = dataObject

    def run(self):
        try:
            rekognition = boto3.client('rekognition', region_name=self.inputParameters.awsRegion)
            text = rekognition.detect_text(
                Image={
                    'S3Object': {
                        'Bucket': self.inputParameters.bucketName,
                        'Name': self.imageName,
                    }
                }
            )

            self.dataObject['Text']  = text
        except Exception as e:
            #print("Failed to process text for {}. Error: {}.".format(self.imageName, e))
            self.dataObject['Text'] = { 'Error' : "{}".format(e)}


# In[ ]:


class FaceProcessor(Thread):

    def __init__(self, imageName, inputParameters, dataObject):
        ''' Constructor. '''
        Thread.__init__(self)
        self.imageName = imageName
        self.inputParameters = inputParameters
        self.dataObject = dataObject

    def run(self):
        try:
            rekognition = boto3.client('rekognition', region_name=self.inputParameters.awsRegion)
            faces = rekognition.detect_faces(
                Image={
                    'S3Object': {
                        'Bucket': self.inputParameters.bucketName,
                        'Name': self.imageName,
                    }
                },
                Attributes=['ALL']
            )

            self.dataObject['Faces'] = faces
        except Exception as e:
            #print("Failed to process faces for {}. Error: {}.".format(self.imageName, e))
            self.dataObject['Faces'] = { 'Error' : "{}".format(e)}


# In[ ]:


class FaceSearchProcessor(Thread):

    def __init__(self, imageName, imageBinary, inputParameters, dataObject):
        ''' Constructor. '''
        Thread.__init__(self)
        self.imageName = imageName
        self.imageBinary = imageBinary
        self.inputParameters = inputParameters
        self.dataObject = dataObject
        self.s3 = boto3.resource('s3', region_name=self.inputParameters.awsRegion)

    def detectFaces(self):
        rekognition = boto3.client('rekognition', region_name=self.inputParameters.awsRegion)
        detectFacesResponse = rekognition.detect_faces(
            Image={
                'S3Object': {
                    'Bucket': self.inputParameters.bucketName,
                    'Name': self.imageName
                    }
                },
            Attributes=['DEFAULT'])
        return detectFacesResponse

    def getFaceCrop(self, box):

        x1 = int(box['Left'] * self.width)-15
        y1 = int(box['Top'] * self.height)-15
        x2 = int(box['Left'] * self.width + box['Width'] * self.width)+15
        y2 = int(box['Top'] * self.height + box['Height']  * self.height)+15
        if x1 < 0 : x1=0
        if y1 < 0 : y1=0
        if x2 < 0 : x2=self.width
        if y2 < 0 : y2=self.height

        coordinates = (x1,y1,x2,y2)

        image_crop = self.imageBinary.crop(coordinates)
        stream2 = BytesIO()

        iformat = "JPEG"
        if(self.imageName.lower().endswith("png")):
            iformat = "PNG"

        image_crop.save(stream2,format=iformat)
        #display(Image.open(stream2))
        image_region_binary = stream2.getvalue()
        stream2.close()

        return image_region_binary

    def recognizeFace(self, faceCrop):
        rekognition = boto3.client('rekognition', region_name=self.inputParameters.awsRegion)
        searchFacesResponse = rekognition.search_faces_by_image(
            CollectionId=self.inputParameters.collectionId,
            Image={
                'Bytes': faceCrop
                },
            MaxFaces=3,
            FaceMatchThreshold=85
        )

        return searchFacesResponse

    def recognizeAllFaces(self):

        detectedFaces = self.detectFaces()

        detectedFaceCount = 0
        recognizedFaces = []
        unrecognizedFaces = []

        if('FaceDetails' in detectedFaces and len(detectedFaces['FaceDetails']) > 0):

            detectedFaceCount = len(detectedFaces['FaceDetails'])

            #Download image to memory
            #obj = self.s3.Object(self.inputParameters.bucketName, self.imageName)
            #imageFile = obj.get()['Body'].read()
            #imageBinary = Image.open(io.BytesIO(imageFile))
            self.width, self.height = self.imageBinary.size

            for detectedFace in detectedFaces['FaceDetails']:
                faceCrop = self.getFaceCrop(detectedFace['BoundingBox'])

                recognizedFace = {}
                faceRecognized = False
                failureMessage = ""

                try:
                    recognizedFace = self.recognizeFace(faceCrop)
                    if('FaceMatches' in recognizedFace and len(recognizedFace['FaceMatches'])>0):
                        faceRecognized = True
                except Exception as e:
                    failureMessage = "Facial recognition failed. Error: {}".format(e)
                    pass

                if(faceRecognized):
                    recognizedFaces.append({ 'BoundingBox' : detectedFace['BoundingBox'],
                                            'FaceMatches' : recognizedFace  })
                else:
                    if failureMessage:
                        unrecognizedFaces.append({ 'BoundingBox' : detectedFace['BoundingBox'],
                                    'Error' : failureMessage  })
                    else:
                        unrecognizedFaces.append({ 'BoundingBox' : detectedFace['BoundingBox'],
                                    'FaceSearchResponse' : recognizedFace  })

        return (detectedFaceCount, recognizedFaces, unrecognizedFaces)


    def run(self):
        try:
            dfc, rf, urf = self.recognizeAllFaces()
            self.dataObject['FaceSearch'] = {'TotalFaces' : dfc, 'RecognizedFaces' : rf, 'UnRecognizedFaces' : urf}
            #display(self.dataObject['FaceSearch'])
        except Exception as e:
            #print("Failed to process faces search for {}. Error: {}.".format(self.imageName, e))
            self.dataObject['FaceSearch'] = { 'Error' : "{}".format(e)}


# In[ ]:


class ImageProcessor(Thread):

    def __init__(self, imageName, inputParameters, output):
        ''' Constructor. '''
        Thread.__init__(self)
        self.imageName = imageName
        self.inputParameters = inputParameters
        self.output = output

    def getImageInformation(self):
        s3 = boto3.resource('s3', region_name=self.inputParameters.awsRegion)
        obj = s3.Object(self.inputParameters.bucketName, self.imageName)
        imageFile = obj.get()['Body'].read()
        imageBinary = Image.open(io.BytesIO(imageFile))
        imageOrientation = -1
        try:
            info = imageBinary._getexif()
            for tag, value in info.items():
                key = TAGS.get(tag, tag)
                if key == "Orientation":
                    imageOrientation = int(value)
                    break
        except:
            pass

        return imageBinary, imageOrientation

    def run(self):

        imageBinary, imageOrientation = self.getImageInformation()

        ado = { 'ImageName' : self.imageName, 'ImageOrientation' : imageOrientation }

        ado['ImagePreSignedUrl'] = RiaHelper.getS3PresignedUrl(self.inputParameters.awsRegion,
                            self.inputParameters.bucketName, self.imageName,
                            self.inputParameters.s3PresignedExpirationTime)

        lp = LabelsProcessor(self.imageName, self.inputParameters, ado)
        mlp = ModerationLabelsProcessor(self.imageName, self.inputParameters, ado)
        clp = CelebritiesProcessor(self.imageName, self.inputParameters, ado)
        tp = TextProcessor(self.imageName, self.inputParameters, ado)
        fp = FaceProcessor(self.imageName, self.inputParameters, ado)
        if self.inputParameters.collectionId:
            fsp = FaceSearchProcessor(self.imageName, imageBinary, self.inputParameters, ado)

        lp.start()
        mlp.start()
        clp.start()
        tp.start()
        fp.start()
        if self.inputParameters.collectionId:
            fsp.start()

        lp.join()
        mlp.join()
        clp.join()
        tp.join()
        fp.join()
        if self.inputParameters.collectionId:
            fsp.join()

        self.output.append(ado)


# In[ ]:


class ImageAnalyzer:

    def __init__(self, inputParameters, output):
        ''' Constructor. '''
        self.inputParameters = inputParameters
        self.output = output

    def processBatch(self, threads):
        for thr in threads:
            thr.start()

        for thr in threads:
            thr.join()

    def analyzeImages(self, listObjectsResponse, currentPage):

        threads = []

        i = 1
        for img in listObjectsResponse['Contents']:
            imageName = img['Key']
            inlower = imageName.lower()
            if(inlower.endswith('png') or inlower.endswith('jpg') or inlower.endswith('jpeg')):
                ip = ImageProcessor(imageName, self.inputParameters, self.output)
                threads.append(ip)

                if(i % self.inputParameters.concurrencyControl == 0):
                    self.processBatch(threads)
                    print("Processed batch {} of {} image(s) of page {}.".format(
                        int(i/self.inputParameters.concurrencyControl), self.inputParameters.concurrencyControl, currentPage))
                    threads.clear()

                i = i + 1

                if(i > self.inputParameters.maxItemsPerPage):
                    break

        if(threads):
            self.processBatch(threads)
            print("Processed batch {} of {} image(s) of page {}.".format(int(i/self.inputParameters.concurrencyControl)+1, len(threads), currentPage))

        print("Processed page {}".format(currentPage))

    def start(self):
        currentPage = 1
        hasMoreContent = True
        continuationToken = None

        s3client = boto3.client('s3', region_name=self.inputParameters.awsRegion)

        while(hasMoreContent and currentPage <= self.inputParameters.maxPages):
            if(continuationToken):
                listObjectsResponse = s3client.list_objects_v2(
                    Bucket=self.inputParameters.bucketName,
                    Prefix=self.inputParameters.imagesDirectory,
                    ContinuationToken=continuationToken)
            else:
                listObjectsResponse = s3client.list_objects_v2(
                    Bucket=self.inputParameters.bucketName,
                    Prefix=self.inputParameters.imagesDirectory)

            if(listObjectsResponse['IsTruncated']):
                continuationToken = listObjectsResponse['NextContinuationToken']
            else:
                hasMoreContent = False

            print("Processing page {}...".format(currentPage))

            self.analyzeImages(listObjectsResponse, currentPage)

            currentPage = currentPage + 1


# In[ ]:


class JSONGenerator:

    def __init__(self, inputParameters, output):
        ''' Constructor. '''
        self.inputParameters = inputParameters
        self.output = output

    def start(self):
        RiaHelper.writeToS3(json.dumps(self.output), self.inputParameters.awsRegion,
                    self.inputParameters.outputBucketName, self.inputParameters.jsonFileNameWithPrefix)

        return RiaHelper.getS3PresignedUrl(self.inputParameters.awsRegion,
                                        self.inputParameters.outputBucketName,
                                        self.inputParameters.jsonFileNameWithPrefix,
                                        self.inputParameters.s3PresignedExpirationTime)


# In[ ]:


class CSVGenerator:

    def __init__(self, inputParameters, output):
        ''' Constructor. '''
        self.inputParameters = inputParameters
        self.output = output

    def writeRow(self, writer, imageName, imageUrl, apiName, itemId, subItemId, itemValue, itemConfidenceScore):
        csvo = {}
        csvo['ImageName'] = imageName
        csvo['ImagePreSignedUrl'] = imageUrl
        csvo['API'] = apiName
        csvo['ItemID'] = itemId
        csvo['SubItemID'] = subItemId
        csvo['Value'] = itemValue
        if(itemConfidenceScore):
            csvo['Confidence'] = itemConfidenceScore
        writer.writerow(csvo)

    def generateLabelsCSV(self, imageName, imageUrl, writer, o):

        i = 1
        apiName = "Labels"

        for l in o['Labels']['Labels']:

            itemId = "Label{}".format(i)

            self.writeRow(writer, imageName, imageUrl, apiName, itemId, "Label{}-Name".format(i), l['Name'], l['Confidence'])

            j = 1
            for ei in l['Instances']:
                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                         "Label{}-Instance{}-BoundingBox".format(i, j), ei['BoundingBox'], ei['Confidence'])
                j = j + 1

            j = 1
            for ei in l['Parents']:
                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                         "Label{}-Parent{}".format(i, j), ei['Name'], None)
                j = j + 1

            i = i + 1

    def generateModerationLabelsCSV(self, imageName, imageUrl, writer, o):
        i = 1
        apiName = "ModerationLabels"

        for l in o['ModerationLabels']['ModerationLabels']:

            itemId = "ModerationLabel{}".format(i)

            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                     "ModerationLabel{}-Name".format(i), l['Name'], l['Confidence'])

            if l['ParentName']:
                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                     "ModerationLabel{}-Parent".format(i), l['ParentName'], None)

            i = i + 1

    def generateTextCSV(self, imageName, imageUrl, writer, o):

        ln = 1
        wn = 1

        apiName = "Text"

        for t in o['Text']['TextDetections']:

            itemTitle = "Line"
            inumber = ln
            if(t['Type'] == 'WORD'):
                itemTitle = "Word"
                inumber = wn

            itemId = "{}{}".format(itemTitle, inumber)


            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                     "{}{}-ID".format(itemTitle, inumber), t['Id'], None)

            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                     "{}{}-Text".format(itemTitle, inumber), t['DetectedText'], t['Confidence'])

            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                     "{}{}-BoundingBox".format(itemTitle, inumber), t['Geometry']['BoundingBox'], None)

            if('ParentId' in t):
                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                     "{}{}-ParentId".format(itemTitle, inumber), t['ParentId'], None)

            if(t['Type'] == 'WORD'):
                wn = wn + 1
            else:
                ln = ln + 1

    def generateCelebritiesCSV(self, imageName, imageUrl, writer, o):

        i = 1
        apiName = "Celebrity"

        for cl in o['Celebrities']['CelebrityFaces']:

            itemId = "Celebrity{}".format(i)

            self.writeRow(writer, imageName, imageUrl, apiName, itemId, "Celebrity{}-ID".format(i), cl['Id'], None)
            self.writeRow(writer, imageName, imageUrl, apiName, itemId, "Celebrity{}-Name".format(i), cl['Name'], cl['MatchConfidence'])
            self.writeRow(writer, imageName, imageUrl, apiName, itemId, "Celebrity{}-Urls".format(i), ','.join(cl['Urls']), None)

            if('Face' in cl):
                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                         "Celebrity{}-Face-BoundingBox".format(i), cl['Face']['BoundingBox'], cl['Face']['Confidence'])

                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                         "Celebrity{}-Face-Pose-Pitch".format(i), cl['Face']['Pose']['Pitch'], None)
                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                         "Celebrity{}-Face-Pose-Roll".format(i), cl['Face']['Pose']['Roll'], None)
                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                         "Celebrity{}-Face-Pose-Yaw".format(i), cl['Face']['Pose']['Yaw'], None)

                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                         "Celebrity{}-Face-Quality-Brightness".format(i), cl['Face']['Quality']['Brightness'], None)

                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                         "Celebrity{}-Face-Quality-Sharpness".format(i), cl['Face']['Quality']['Sharpness'], None)

                j = 1
                for lm in cl['Face']['Landmarks']:
                    self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                        "Celebrity{}-Face-Lankmark-{}".format(i, j), lm['Type'], None)

                    self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                        "Celebrity{}-Face-Lankmark-{}-X".format(i, j), lm['X'], None)

                    self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                        "Celebrity{}-Face-Lankmark-{}-Y".format(i, j), lm['Y'], None)

                    j = j + 1
            i = i +1

    def generateFacesCSV(self, imageName, imageUrl, writer, o):

        i = 1
        apiName = "Face"

        for fd in o['Faces']['FaceDetails']:

            itemId = "Face{}".format(i)

            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                     "Face{}-BoundingBox".format(i), fd['BoundingBox'], fd['Confidence'])

            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-MinAge".format(i), fd['AgeRange']['Low'], None)

            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-MaxAge".format(i), fd['AgeRange']['High'], None)

            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-Beard".format(i), fd['Beard']['Value'], fd['Beard']['Confidence'])
            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-Eyeglasses".format(i), fd['Eyeglasses']['Value'], fd['Eyeglasses']['Confidence'])
            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-EyesOpen".format(i), fd['EyesOpen']['Value'], fd['EyesOpen']['Confidence'])
            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-Gender".format(i), fd['Gender']['Value'], fd['Gender']['Confidence'])
            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-MouthOpen".format(i), fd['MouthOpen']['Value'], fd['MouthOpen']['Confidence'])
            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-Mustache".format(i), fd['Mustache']['Value'], fd['Mustache']['Confidence'])
            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-Smile".format(i), fd['Smile']['Value'], fd['Smile']['Confidence'])
            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-Sunglasses".format(i), fd['Sunglasses']['Value'], fd['Sunglasses']['Confidence'])

            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-Pose-Pitch".format(i), fd['Pose']['Pitch'], None)
            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-Pose-Roll".format(i), fd['Pose']['Roll'], None)
            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-Pose-Yaw".format(i), fd['Pose']['Yaw'], None)

            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-Quality-Brightness".format(i), fd['Quality']['Brightness'], None)
            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "Face{}-Quality-Sharpness".format(i), fd['Quality']['Sharpness'], None)


            j = 1
            for lm in fd['Landmarks']:
                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                    "Face{}-Lankmark-{}".format(i, j), lm['Type'], None)

                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                    "Face{}-Lankmark-{}-X".format(i, j), lm['X'], None)

                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                    "Face{}-Lankmark-{}-Y".format(i, j), lm['Y'], None)

                j = j + 1

            j = 1
            for em in fd['Emotions']:
                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                    "Face{}-Emotion-{}".format(i, j), em['Type'], em['Confidence'])

                j = j + 1


            i = i +1

#                            if('FaceMatches' in recognizedFace and len(recognizedFace['FaceMatches'])>0):
#                    recognizedFaces.append({ 'BoundingBox' : detectedFace['BoundingBox'],
#                                            'FaceMatches' : recognizedFace  })
#                else:
#                    unrecognizedFaces.append({ 'BoundingBox' : detectedFace['BoundingBox'],
#                                            'FaceMatches' : recognizedFace  })
 #self.dataObject['FaceSearch'] = {'TotalFaces' : dfc, 'RecognizedFaces' : rf, 'UnRecognizedFaces' : urf}

    def generateFacesSearchCSV(self, imageName, imageUrl, writer, o):

        i = 1
        apiName = "FaceSearch"

        for rf in o['FaceSearch']['RecognizedFaces']:

            itemId = "FaceSearch{}".format(i)

            self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                "FaceSearch{}-Recognized-BoundingBox".format(i), rf['BoundingBox'], None)

            j = 1
            for fm in rf['FaceMatches']['FaceMatches']:
                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                    "FaceSearch{}-FaceMatch{}-BoundingBox".format(i,j),
                              fm['Face']['BoundingBox'], fm['Face']['Confidence'])

                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                    "FaceSearch{}-FaceMatch{}-ExternalImageId".format(i,j), fm['Face']['ExternalImageId'], None)

                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                    "FaceSearch{}-FaceMatch{}-FaceId".format(i,j), fm['Face']['FaceId'], None)

                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                    "FaceSearch{}-FaceMatch{}-ImageId".format(i,j), fm['Face']['ImageId'], None)

                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                    "FaceSearch{}-FaceMatch{}-Similarity".format(i,j), fm['Similarity'], None)

                j = j + 1

            i = i + 1

        i = 1
        if('UnRecognizedFaces' in o['FaceSearch'] and o['FaceSearch']['UnRecognizedFaces']):
            for rf in o['FaceSearch']['UnRecognizedFaces']:

                itemId = "FaceSearch{}".format(i)

                self.writeRow(writer, imageName, imageUrl, apiName, itemId,
                    "FaceSearch{}-UnRecognized-BoundingBox".format(i), rf['BoundingBox'], None)

                i = i + 1


    def start(self):
        csv_file = io.StringIO()
        fieldnames = ['ImageName', 'ImagePreSignedUrl', 'API', 'ItemID', 'SubItemID', 'Value', 'Confidence']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for o in self.output:
            if('Labels' in o and 'Labels' in o['Labels']):
                self.generateLabelsCSV(o['ImageName'], o['ImagePreSignedUrl'], writer, o)

            if('ModerationLabels' in o and 'ModerationLabels' in o['ModerationLabels']):
                self.generateModerationLabelsCSV(o['ImageName'], o['ImagePreSignedUrl'], writer, o)

            if('Faces' in o and 'FaceDetails' in o['Faces']):
                self.generateFacesCSV(o['ImageName'], o['ImagePreSignedUrl'], writer, o)

            if('FaceSearch' in o and 'RecognizedFaces' in o['FaceSearch']):
                self.generateFacesSearchCSV(o['ImageName'], o['ImagePreSignedUrl'], writer, o)

            if('Text' in o and 'TextDetections' in o['Text']):
                self.generateTextCSV(o['ImageName'], o['ImagePreSignedUrl'], writer, o)

            if('Celebrities' in o and 'CelebrityFaces' in o['Celebrities']):
                self.generateCelebritiesCSV(o['ImageName'], o['ImagePreSignedUrl'], writer, o)

        RiaHelper.writeToS3WithOptions(csv_file.getvalue(), self.inputParameters.awsRegion,
                            self.inputParameters.outputBucketName,
                            self.inputParameters.csvFileNameWithPrefix,
                            'private', 'text/csv; charset=utf-8')

        return RiaHelper.getS3PresignedUrl(self.inputParameters.awsRegion,
                                self.inputParameters.outputBucketName,
                                self.inputParameters.csvFileNameWithPrefix,
                                self.inputParameters.s3PresignedExpirationTime)


# In[ ]:


def getHtmlTemplateString():
    return """
<!DOCTYPE html>
<html lang="en">

<head>
  <title>Rekognition Image Analysis</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.1.3/css/bootstrap.min.css">
  <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.14.3/umd/popper.min.js"></script>
  <script src="https://maxcdn.bootstrapcdn.com/bootstrap/4.1.3/js/bootstrap.min.js"></script>
  <script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
  <script src="ria-data.js"></script>
  <style>
    html,body {
    height: 95%;
    }
  .topHeader
    {
      background-color: #232f3e;
      padding: 10px;
      border-bottom: solid 1px #cacaca;
      color: white
    }
    .imgCell{
      width: 1200px;
    }
    .links{
      max-height: 100%;
      overflow-y: scroll;
    }
    .labels{
      margin: 5px;
      padding: 10px;
    }
    .lblButton{
      margin-top: 10px;
    }
    .mdbox{
      font-weight: bold;
    }
    .chartModalBox{
      width: 1000px;
      height: 2200px;
    }
  </style>
</head>

<body>
  <div class="container-fluid h-100">
    <!--Top Header-->
    <div class="row topHeader">
      <div class="col-md-6">
        <h4>Amazon Rekognition Image Analysis</h4>
      </div>
      <div class="col-md-6 text-right">

        <!--<div class="btn-group">
          <button class="btn btn-secondary dropdown-toggle" type="button" id="dropdownMenuButton" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
            Metadata Stats
          </button>
          <div class="dropdown-menu" aria-labelledby="dropdownMenuButton">
            <a class="dropdown-item" href="javascript:renderStats('Labels')">Labels Stats</a>
            <a class="dropdown-item" href="javascript:renderStats('ModerationLabels')">Moderation Labels Stats</a>
            <a class="dropdown-item" href="javascript:renderStats('Celebrities')">Celebrities Stats</a>
            <a class="dropdown-item" href="javascript:renderStats('Text')">Text Stats</a>
            <a class="dropdown-item" href="javascript:renderStats('Faces')">Faces Stats</a>
          </div>
        </div>-->
        <div class="btn-group">
          <button class="btn btn-secondary dropdown-toggle" type="button" id="dropdownMenuButton" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
            Export
          </button>
          <div class="dropdown-menu" aria-labelledby="dropdownMenuButton">
            <a class="dropdown-item" href="ria-json.json">JSON</a>
            <div class="dropdown-divider"></div>
            <a class="dropdown-item" href="ria-csv.csv">CSV</a>
          </div>
        </div>
      </div>
    </div>
    <div class="row h-100">
      <div class="col-sm-3 links">
        <br>
        <div class="row alert alert-secondary ml-1 mr-1">
          <div class="col-sm-8">
            <div id='list-title'></div>
          </div>
          <div class="col-sm-4 text-right">
            <div class="btn-group">
              <button class="btn btn-secondary dropdown-toggle" type="button" id="dropdownMenuButton" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                Filter
              </button>
              <div class="dropdown-menu" aria-labelledby="dropdownMenuButton">
                <a class="dropdown-item" href="javascript:renderAppWithFilter('ModerationLabels')">Images with Moderation Labels</a>
                <a class="dropdown-item" href="javascript:renderAppWithFilter('Faces')">Images with Faces</a>
                <a class="dropdown-item" href="javascript:renderAppWithFilter('Text')">Images with Text</a>
                <a class="dropdown-item" href="javascript:renderAppWithFilter('Celebrities')">Images with Celebrities</a>
                <div class="dropdown-divider"></div>
                <a class="dropdown-item" href="javascript:renderApp();">Show All Images</a>
              </div>
            </div>
          </div>
        </div>
        <div id='image-links'></div>
      </div>
      <div class="col-sm-9 links">
        <br>
        <div class="row alert alert-secondary ml-1 mr-1">
          <div class="col-sm-6">
            <div id='image-title'></div>
          </div>
          <div class="col-sm-6 text-right">
            <div class="form-check form-check-inline">
              Bounding Box:&nbsp;&nbsp;
              <input class="form-check-input" type="checkbox" checked value="Objects" onclick="refreshRenderedItem();" id="chkLabels">
              <label class="form-check-label" for="chkLabels">
                Labels
              </label>
              &nbsp;
              <input class="form-check-input" type="checkbox" checked value="" onclick="refreshRenderedItem();" id="chkFaces">
              <label class="form-check-label" for="chkFaces">
                Faces
              </label>
              <!--&nbsp;
            <input class="form-check-input" type="checkbox" checked value="" onclick="refreshRenderedItem();" id="chkText">
            <label class="form-check-label" for="chkText">
              Text (Pink)
            </label>-->
              &nbsp;
              <input class="form-check-input" type="checkbox" checked value="" onclick="refreshRenderedItem();" id="chkCelebrities">
              <label class="form-check-label" for="chkCelebrities">
                Celebrities
              </label>
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col-sm">
            <div id='image-container'></div>
          </div>
        </div>
        <div class="row">
          <div class="col-sm links">
            <div id='image-metadata'></div>
          </div>
        </div>
      </div>
    </div>
    <div class="row">
      <!-- Modal -->
      <div id="statsWindow" class="modal fade" tabindex="-1" role="dialog" aria-labelledby="exampleModalLongTitle" aria-hidden="true">
        <div class="modal-dialog">
          <div class="modal-content chartModalBox">
            <div class="modal-header">
              <h5 class="modal-title" id="exampleModalLongTitle">Metadata Stats</h5>
              <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                <span aria-hidden="true">&times;</span>
              </button>
            </div>
            <div class="modal-body">
              <div id="chart-body"></div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <script>
    imagesDic = {}

    var chart;

    function drawChart() {
      chartData = []

      for (let key in statDic) {
        if (statDic.hasOwnProperty(key)) {
          chartData.push([key, statDic[key]])
        }
      }

      chartData.sort(function(first, second) {
        return second[1] - first[1];
      });

      chartData = chartData.slice(0, 50)

      var ctitle = ""
      if (window.chartDataType === 'Labels') {
        chartData.unshift(['Labels', 'Count']);
        ctitle = "Top Labels"
      } else if (window.chartDataType === 'ModerationLabels') {
        chartData.unshift(['Moderation Labels', 'Count']);
        ctitle = "Top Moderation Labels"
      } else if (window.chartDataType === 'Celebrities') {
        chartData.unshift(['Celebrities', 'Count']);
        ctitle = "Top Celebrities"
      } else if (window.chartDataType === 'Text') {
        chartData.unshift(['Text', 'Count']);
        ctitle = "Top Text"
      } else if (window.chartDataType === 'Faces') {
        chartData.unshift(['Face Emotions', 'Count']);
        ctitle = "Top Face Emotions"
      }

      var data = new google.visualization.arrayToDataTable(chartData);

      var options = {
        title: window.chartDataType + 'Stats',
        width: 900,
        height: window.chartHeight - 100,
        legend: {
          position: 'none'
        },
        chart: {
          title: ctitle,
          subtitle: 'by count'
        },
        bars: 'horizontal', // Required for Material Bar Charts.
        axes: {
          x: {
            0: {
              side: 'top',
              label: 'Count'
            } // Top x-axis.
          }
        },
        bar: {
          groupWidth: "100%"
        }
      };

      chart = new google.charts.Bar(document.getElementById('top_x_div'));
      chart.draw(data, options);
    };

    function renderStats(filter) {
      window.statDic = {}
      window.chartDataType = filter
      for (ei in images) {
        let list;
        if (filter === 'Labels') {
          if (images[ei].Labels && images[ei].Labels.Labels)
            list = images[ei].Labels.Labels
        } else if (filter === 'ModerationLabels') {
          if (images[ei].ModerationLabels && images[ei].ModerationLabels.ModerationLabels)
            list = images[ei].ModerationLabels.ModerationLabels
        } else if (filter === 'Celebrities') {
          if (images[ei].Celebrities && images[ei].Celebrities.CelebrityFaces)
            list = images[ei].Celebrities.CelebrityFaces
        } else if (filter === 'Text') {
          if (images[ei].Text && images[ei].Text.TextDetections)
            list = images[ei].Text.TextDetections
        } else if (filter === 'Faces') {
          if (images[ei].Faces && images[ei].Faces.FaceDetails)
            list = images[ei].Faces.FaceDetails
        }


        if (filter === 'Faces') {
          for (ef in list) {
            for (ee in list[ef].Emotions) {
              if (statDic[list[ef].Emotions[ee].Type])
                statDic[list[ef].Emotions[ee].Type] = statDic[list[ef].Emotions[ee].Type] + 1
              else
                statDic[list[ef].Emotions[ee].Type] = 1
            }
          }
        } else {
          for (el in list) {
            let lblName;
            if (filter === 'Labels')
              lblName = list[el].Name
            else if (filter === 'ModerationLabels')
              lblName = list[el].Name
            else if (filter === 'Celebrities')
              lblName = list[el].Name
            else if (filter === 'Text') {
              if (list[el].Type === 'LINE')
                lblName = list[el].DetectedText
            }

            if (statDic[lblName])
              statDic[lblName] = statDic[lblName] + 1
            else
              statDic[lblName] = 1
          }
        }
      }

      let icount = Object.keys(statDic).length
      let chartHeight = 2000
      if (icount < 25)
        chartHeight = icount * 50
      if (chartHeight < 400)
        chartHeight = 400

      //$("#chart-body").html("")
      if (!window.chartHeight)
        $("#chart-body").html('<br><br><div id="top_x_div" style="width: 900px; height: ' + chartHeight + 'px;"></div>');

      window.chartHeight = chartHeight

      $('#statsWindow').modal('show')

      //$("#image-metadata").html("");
      //$("#image-links").html("");

      google.charts.load('current', {
        'packages': ['bar']
      });
      google.charts.setOnLoadCallback(drawChart);
    }

    function renderLabels(iid, bbs) {

      let rs = '<div class="alert alert-secondary mdbox">Labels (' + imagesDic[iid].Labels.Labels.length + ')</div>';

      if ($('#chkLabels').is(":checked")) {
        for (eo in imagesDic[iid].Labels.Labels) {
          for (ei in imagesDic[iid].Labels.Labels[eo].Instances) {
            imagesDic[iid].Labels.Labels[eo].Instances[ei].BoundingBox.BoxColor = '#007a99'
            imagesDic[iid].Labels.Labels[eo].Instances[ei].BoundingBox.Title = imagesDic[iid].Labels.Labels[eo].Name
            bbs.push(imagesDic[iid].Labels.Labels[eo].Instances[ei].BoundingBox)
          }
        }
      }

      let items = imagesDic[iid].Labels.Labels;

      if (items) {
        for (ei in items) {
          rs += '<button type="button" class="btn btn-primary lblButton">' + items[ei].Name + '&nbsp;&nbsp;&nbsp;<span class="badge badge-light">' + items[ei].Confidence.toFixed(2) +
            '</span><span class="sr-only">unread messages</span></button>&nbsp;&nbsp;'
        }
      }
      return rs;
    }

    function renderModerationLabels(iid) {
      let rs = '<br><br><div class="alert alert-secondary mdbox">Moderation Labels (' + imagesDic[iid].ModerationLabels.ModerationLabels.length + ')</div>';
      let items = imagesDic[iid].ModerationLabels.ModerationLabels;
      if (items) {
        for (ei in items) {
          rs += '<button type="button" class="btn btn-primary lblButton">' + items[ei].Name + '&nbsp;&nbsp;&nbsp;<span class="badge badge-light">' + items[ei].Confidence.toFixed(2) +
            '</span><span class="sr-only">unread messages</span></button>&nbsp;&nbsp;'
        }
      }
      return rs;
    }

    function getFaceRecognized(iid, bb){
      isFaceRecognized = false;

      if(imagesDic[iid].FaceSearch && imagesDic[iid].FaceSearch.RecognizedFaces && imagesDic[iid].FaceSearch.RecognizedFaces.length > 0){
        for (erf in imagesDic[iid].FaceSearch.RecognizedFaces){
          if(imagesDic[iid].FaceSearch.RecognizedFaces[erf].BoundingBox.Height === bb.Height &&
             imagesDic[iid].FaceSearch.RecognizedFaces[erf].BoundingBox.Width === bb.Width &&
             imagesDic[iid].FaceSearch.RecognizedFaces[erf].BoundingBox.Left === bb.Left &&
             imagesDic[iid].FaceSearch.RecognizedFaces[erf].BoundingBox.Top === bb.Top){

              if(imagesDic[iid].FaceSearch.RecognizedFaces[erf].FaceMatches
                && imagesDic[iid].FaceSearch.RecognizedFaces[erf].FaceMatches.FaceMatches
                && imagesDic[iid].FaceSearch.RecognizedFaces[erf].FaceMatches.FaceMatches.length > 0){

                  bb.FaceEID = imagesDic[iid].FaceSearch.RecognizedFaces[erf].FaceMatches.FaceMatches[0].Face.ExternalImageId
                  bb.FaceSimilarity = imagesDic[iid].FaceSearch.RecognizedFaces[erf].FaceMatches.FaceMatches[0].Similarity
                  isFaceRecognized = true;
                  break;
              }
            }
        }
      }
      return isFaceRecognized;
    }


    function renderFaces(iid, bbs) {
      let rs = '<br><br><div class="alert alert-secondary mdbox">Faces (' + imagesDic[iid].Faces.FaceDetails.length + ')</div>';

      if ($('#chkFaces').is(":checked")) {
        for (ef in imagesDic[iid].Faces.FaceDetails) {
          imagesDic[iid].Faces.FaceDetails[ef].BoundingBox.BoxColor = '#ff8000'
          if(getFaceRecognized(iid, imagesDic[iid].Faces.FaceDetails[ef].BoundingBox)){
            imagesDic[iid].Faces.FaceDetails[ef].BoundingBox.Title = "eid: " + imagesDic[iid].Faces.FaceDetails[ef].BoundingBox.FaceEID + " ( " + imagesDic[iid].Faces.FaceDetails[ef].BoundingBox.FaceSimilarity.toFixed(2) +  " )"
          }
          bbs.push(imagesDic[iid].Faces.FaceDetails[ef].BoundingBox)
        }
      }

      let items = imagesDic[iid].Faces.FaceDetails;

      if (items) {
        fi = 1
        for (ei in items) {

          if(items[ei].BoundingBox.FaceEID){
            rs += '<button type="button" class="btn btn-primary lblButton">EID: ' + items[ei].BoundingBox.FaceEID + '&nbsp;&nbsp;&nbsp;<span class="badge badge-light">' + items[ei].BoundingBox.FaceSimilarity.toFixed(2) +
              '</span><span class="sr-only">unread messages</span></button>&nbsp;&nbsp;'
          }

          rs += '<button type="button" class="btn btn-primary lblButton">' + items[ei].Gender.Value + '&nbsp;&nbsp;&nbsp;<span class="badge badge-light">' + items[ei].Gender.Confidence.toFixed(2) +
            '</span><span class="sr-only">unread messages</span></button>&nbsp;&nbsp;'
          rs += '<button type="button" class="btn btn-primary lblButton">Age' + '&nbsp;&nbsp;&nbsp;<span class="badge badge-light">' + items[ei].AgeRange.Low + "-" + items[ei].AgeRange.High +
            '</span><span class="sr-only">unread messages</span></button>&nbsp;&nbsp;'
          for (emo in items[ei].Emotions) {
            rs += '<button type="button" class="btn btn-primary lblButton">' + items[ei].Emotions[emo].Type + '&nbsp;&nbsp;&nbsp;<span class="badge badge-light">' + items[ei].Emotions[emo].Confidence.toFixed(2) +
              '</span><span class="sr-only">unread messages</span></button>&nbsp;&nbsp;'
          }
          if(fi < items.length){
            rs += "<br>"
          }
          fi++;
        }
      }
      return rs;
    }

    function renderTexts(iid, bbs) {

      let rs = ""
      /*if($('#chkText').is(":checked")){
        for(el in imagesDic[iid].Text.TextDetections){
          if(imagesDic[iid].Text.TextDetections[el].Type === 'LINE'){
            imagesDic[iid].Text.TextDetections[el].Geometry.BoundingBox.BoxColor = 'pink'
            bbs.push(imagesDic[iid].Text.TextDetections[el].Geometry.BoundingBox)
          }
        }
      }*/

      let items = imagesDic[iid].Text.TextDetections;
      let i = 0
      if (items) {
        for (ei in items) {
          if (items[ei].Type === 'LINE') {
            rs += '<button type="button" class="btn btn-primary lblButton">' + items[ei].DetectedText + '&nbsp;&nbsp;&nbsp;<span class="badge badge-light">' + items[ei].Confidence.toFixed(2) +
              '</span><span class="sr-only">unread messages</span></button>&nbsp;&nbsp;'
            i++;
          }
        }
      }

      return '<br><br><div class="alert alert-secondary mdbox">Text (' + i + ')</div>' + rs;
    }

    function renderCelebrities(iid, bbs) {
      let rs = '<br><br><div class="alert alert-secondary mdbox">Celebrities (' + imagesDic[iid].Celebrities.CelebrityFaces.length + ')</div>';

      if ($('#chkCelebrities').is(":checked")) {
        for (ec in imagesDic[iid].Celebrities.CelebrityFaces) {
          imagesDic[iid].Celebrities.CelebrityFaces[ec].Face.BoundingBox.BoxColor = '#cc0099'
          imagesDic[iid].Celebrities.CelebrityFaces[ec].Face.BoundingBox.Title = imagesDic[iid].Celebrities.CelebrityFaces[ec].Name
          bbs.push(imagesDic[iid].Celebrities.CelebrityFaces[ec].Face.BoundingBox)
        }
      }

      let items = imagesDic[iid].Celebrities.CelebrityFaces;

      if (items) {
        for (ei in items) {
          rs += '<button type="button" class="btn btn-primary lblButton">' + items[ei].Name + '&nbsp;&nbsp;&nbsp;<span class="badge badge-light">' + items[ei].MatchConfidence.toFixed(2) +
            '</span><span class="sr-only">unread messages</span></button>&nbsp;&nbsp;'
        }
      }
      return rs;
    }

    function renderStraightImage(imageSource, boundingBoxes) {

      var canvas = document.getElementById('myCanvas');
      var context = canvas.getContext('2d');

      var imageObj = new Image();

      imageObj.onload = function() {

        context.clearRect(0,0,canvas.width,canvas.height);

        scaleFactor = 1
        maxWidth = 1200

        if (imageObj.width > maxWidth) {
          pc = 0.9
          while (pc > 0.1) {
            if (imageObj.width * pc < maxWidth) {
              scaleFactor = pc
              break;
            }
            pc -= 0.1;
          }
        }

        canvas.width = imageObj.width * scaleFactor;
        canvas.height = imageObj.height * scaleFactor;

        context.drawImage(imageObj, 0, 0, imageObj.width * scaleFactor, imageObj.height * scaleFactor);

        if (boundingBoxes) {
          for (bb in boundingBoxes) {
            boundingBox = boundingBoxes[bb]
            context.beginPath();
            context.rect(boundingBox.Left * imageObj.width * scaleFactor, boundingBox.Top * imageObj.height * scaleFactor, imageObj.width * scaleFactor * boundingBox.Width, imageObj.height * scaleFactor * boundingBox.Height);
            if (boundingBox.BoxColor == '#007a99')
              context.lineWidth = 2;
            else if (boundingBox.BoxColor == '#ff8000')
              context.lineWidth = 2;
            else
              context.lineWidth = 2;
            context.strokeStyle = boundingBox.BoxColor;
            context.stroke();
            if (boundingBox.Title) {
              context.font = "9pt Arial";
              context.fillStyle = "#fff";
              //let textheight = context.measureText(boundingBox.Title).height;
              context.fillText(boundingBox.Title, boundingBox.Left * imageObj.width * scaleFactor + 3, boundingBox.Top * imageObj.height * scaleFactor + 15);
            }
          }
        }
      };
      imageObj.src = imageSource
    }

    function renderRotatedImage(imageSource, imageOrientation, boundingBoxes){
      console.log("rotated image...")
      console.log(imageOrientation)
      var canvas = document.getElementById('myCanvas');
      var context = canvas.getContext('2d');

      var imageObj = new Image();

      imageObj.onload = function() {
        context.clearRect(0,0,canvas.width,canvas.height);

        console.log("w:" + imageObj.width)
        console.log("H:" + imageObj.height)

        boxWidth = imageObj.width
        boxHeight = imageObj.height
        rotationAngle = 0

        if(imageOrientation == 6){
          rotationAngle = 90;
          //boxWidth = imageObj.height
          //boxHeight = imageObj.width
        }
        else if(imageOrientation == 3){
          rotationAngle = 180;
        }
        else if(imageOrientation == 8){
          rotationAngle = 270;
          //boxWidth = imageObj.height
          //boxHeight = imageObj.width
        }

        scaleFactor = 1
        maxWidth = 1300
        if(maxWidth > imageObj.width){
          maxWidth = imageObj.width
        }

        if (boxWidth > maxWidth) {
          pc = 0.9
          while (pc > 0.1) {
            if (boxWidth * pc < maxWidth) {
              scaleFactor = pc
              break;
            }
            pc -= 0.1;
          }
        }

        boxWidth = Math.round(boxWidth*scaleFactor)
        boxHeight = Math.round(boxHeight*scaleFactor)

        if(rotationAngle == 90 || rotationAngle == 270){
          canvas.width = boxHeight;
          canvas.height = boxWidth;
        }
        else {
          canvas.width = boxWidth;
          canvas.height = boxHeight;
        }

        if(rotationAngle !== 0){
          context.translate(canvas.width/2,canvas.height/2);
          context.rotate(rotationAngle*Math.PI/180);
        }

        if(rotationAngle == 90 || rotationAngle == 270){
          //context.drawImage(imageObj, -boxHeight/2, -boxWidth/2, boxHeight, boxWidth);
          context.drawImage(imageObj, -boxWidth/2, -boxHeight/2, boxWidth, boxHeight);
        }
        else {
            context.drawImage(imageObj, -boxWidth/2, -boxHeight/2, boxWidth, boxHeight);
        }

        context.rotate(-1*rotationAngle*Math.PI/180);
        context.translate(-canvas.width/2, -canvas.height/2);

        if (boundingBoxes) {
          for (bb in boundingBoxes) {
            boundingBox = boundingBoxes[bb]
            context.beginPath();

            if(rotationAngle == 90 || rotationAngle == 270){
              context.rect(boundingBox.Left * boxHeight, boundingBox.Top * boxWidth, boxHeight * boundingBox.Width, boxWidth * boundingBox.Height);
            }
            else {
                context.rect(boundingBox.Left * boxWidth, boundingBox.Top * boxHeight, boxWidth * boundingBox.Width, boxHeight * boundingBox.Height);
            }

            if (boundingBox.BoxColor == '#007a99')
              context.lineWidth = 2;
            else if (boundingBox.BoxColor == '#ff8000')
              context.lineWidth = 2;
            else
              context.lineWidth = 2;
            context.strokeStyle = boundingBox.BoxColor;
            context.stroke();
            if (boundingBox.Title) {
              context.font = "9pt Arial";
              context.fillStyle = "#fff";
              if(rotationAngle == 90 || rotationAngle == 270){
                context.fillText(boundingBox.Title, boundingBox.Left * boxHeight + 3, boundingBox.Top * boxWidth + 15);
              }
              else {
                  context.fillText(boundingBox.Title, boundingBox.Left * boxWidth + 3, boundingBox.Top * boxHeight + 15);
              }
            }
          }
        }
      };
      imageObj.src = imageSource
    }

    function renderImage(imageSource, imageOrientation, boundingBoxes) {

      if(imageOrientation === -1 || imageOrientation === 1)
        renderStraightImage(imageSource, boundingBoxes)
      else
        renderRotatedImage(imageSource, imageOrientation, boundingBoxes)
    }

    function renderDirectUrl(iid) {
      let iorigin = window.location.origin;
      let ipathname = window.location.pathname
      //let urlParams = new URLSearchParams(window.location.search);
      //let qs = ""
      //var keys = urlParams.keys();
      //for (key of keys) {
      //  if (key.toLowerCase() !== 'iid') {
      //    qs += key + "=" + urlParams.get(key) + "&"
      //  }
      //}
      let qs = "iid=" + encodeURIComponent(iid)

      let iurl = iorigin + ipathname + "?" + qs

      return '<br><br><div class="alert alert-secondary mdbox">Direct URL</div><a target="_blank" href="' + iurl + '">' + iurl + '</a>';
    }

    function showImage(iid, doPartialRefresh) {

      console.log(imagesDic[iid])

      bbs = []

      if (imagesDic[iid].ImageName && imagesDic[iid].ImagePreSignedUrl) {
        if (!doPartialRefresh)
          $("#image-title").html('<h5>' + imagesDic[iid].ImageName + '</h5>')
        $("#image-container").html('<a target="_blank" href="' + imagesDic[iid].ImagePreSignedUrl + '"><canvas id="myCanvas" width="800" height="500"></canvas></a><hr>');
      }

      let imdview = ""

      if (imagesDic[iid].Labels && imagesDic[iid].Labels.Labels && imagesDic[iid].Labels.Labels.length > 0) {
        imdview += renderLabels(iid, bbs)
      }

      if (imagesDic[iid].ModerationLabels && imagesDic[iid].ModerationLabels.ModerationLabels && imagesDic[iid].ModerationLabels.ModerationLabels.length > 0) {
        imdview += renderModerationLabels(iid)
      }

      if (imagesDic[iid].Faces && imagesDic[iid].Faces.FaceDetails && imagesDic[iid].Faces.FaceDetails.length > 0) {
        imdview += renderFaces(iid, bbs)
      }

      if (imagesDic[iid].Text && imagesDic[iid].Text.TextDetections && imagesDic[iid].Text.TextDetections.length > 0) {
        imdview += renderTexts(iid, bbs)
      }

      if (imagesDic[iid].Celebrities && imagesDic[iid].Celebrities.CelebrityFaces && imagesDic[iid].Celebrities.CelebrityFaces.length > 0) {
        imdview += renderCelebrities(iid, bbs)
      }

      imdview += renderDirectUrl(iid)

      imageOrientation = -1
      if(imagesDic[iid].ImageOrientation)
        imageOrientation = imagesDic[iid].ImageOrientation

      renderImage(imagesDic[iid].ImagePreSignedUrl, imageOrientation, bbs)

      window.selectedItem = iid

      if (!doPartialRefresh)
        $("#image-metadata").html(imdview);
    }

    function refreshRenderedItem() {
      if (window.selectedItem)
        showImage(window.selectedItem, true)
    }

    function makeListHighligtable() {
      $('#listui a').click(function(e) {
        e.preventDefault()

        $that = $(this);

        $that.parent().find('a').removeClass('active');
        $that.addClass('active');
      });
    }

    function renderUI(selectItem, filter) {

      let icount = Object.keys(imagesDic).length
      llistTitle = "All Images"
      if (filter == 'ModerationLabels')
        llistTitle = "Images with Moderation Labels"
      else if (filter == 'ModerationLabels')
        llistTitle = "Images with Moderation Labels"
      else if (filter == 'Celebrities')
        llistTitle = "Images with Celebrities"
      else if (filter == 'Text')
        llistTitle = "Images with Text"
      else if (filter == 'Faces')
        llistTitle = "Images with Faces"
      llistTitle = '<h5 class="mt-1">' + llistTitle + ' (' + icount + ')</h5>'
      let llist = '<div id="listui" class="list-group">'
      for (let key in imagesDic) {
        if (imagesDic.hasOwnProperty(key)) {
          let btnhtml = '<a href="#" class="list-group-item list-group-item-action btn-primary" onclick=' + "'showImage(" + '"' + imagesDic[key].ImageName + '"' + ")'>" + imagesDic[key].ImageName + '</a>'
          if (selectItem && key === selectItem)
            btnhtml = '<a href="#" class="list-group-item list-group-item-action btn-primary active" onclick=' + "'showImage(" + '"' + imagesDic[key].ImageName + '"' + ")'>" + imagesDic[key].ImageName + '</a>'
          llist += btnhtml
        }
      }
      llist += '</div>'

      $("#image-title").html("");
      $("#image-container").html("");
      $("#image-metadata").html("");
      $("#list-title").html(llistTitle);
      $("#image-links").html(llist);

      makeListHighligtable();

      if (selectItem) {
        showImage(selectItem);
      }
    }

    function renderAppWithFilter(filter) {
      imagesDic = {}
      var selectItem;
      var ii = 0
      var includeItem;
      for (ei in images) {
        includeItem = false;

        if (filter === 'ModerationLabels') {
          if (images[ei].ModerationLabels && images[ei].ModerationLabels.ModerationLabels && images[ei].ModerationLabels.ModerationLabels.length > 0)
            includeItem = true;
        } else if (filter === 'Celebrities') {
          if (images[ei].Celebrities && images[ei].Celebrities.CelebrityFaces && images[ei].Celebrities.CelebrityFaces.length > 0)
            includeItem = true;
        } else if (filter === 'Text') {
          if (images[ei].Text && images[ei].Text.TextDetections && images[ei].Text.TextDetections.length > 0)
            includeItem = true;
        } else if (filter === 'Faces') {
          if (images[ei].Faces && images[ei].Faces.FaceDetails && images[ei].Faces.FaceDetails.length > 0)
            includeItem = true;
        }

        if (includeItem) {
          if (ii === 0)
            selectItem = images[ei].ImageName

          imagesDic[images[ei].ImageName] = images[ei]

          ii++
        }
      }

      renderUI(selectItem, filter);
    }

    function renderApp(qsiid) {
      imagesDic = {}
      var selectItem;

      for (ei in images) {
        imagesDic[images[ei].ImageName] = images[ei]
      }

      if (qsiid && qsiid in imagesDic) {
        selectItem = qsiid;
      } else if (images.length > 0) {
        selectItem = images[0].ImageName
      }

      renderUI(selectItem, 'AllImages');
    }

    function startApp() {
      let urlParams = new URLSearchParams(window.location.search);
      let qsiid = urlParams.get('iid');
      if (qsiid) {
        qsiid = decodeURI(qsiid)
      }
      renderApp(qsiid);
    }

    startApp();
  </script>
</body>

</html>
"""


# In[ ]:


class HTMLGenerator:

    def __init__(self, inputParameters, output):
        ''' Constructor. '''
        self.inputParameters = inputParameters
        self.output = output

    def generateDataFile(self):
        riadata = "images = " + json.dumps(self.output)
        RiaHelper.writeToS3WithOptions(riadata, self.inputParameters.awsRegion,
                                        self.inputParameters.outputBucketName,
                                        self.inputParameters.dataFileNameWithPrefix,
                                        'private', 'text/javascript; charset=utf-8')
        return RiaHelper.getS3PresignedUrl(self.inputParameters.awsRegion,
                                            self.inputParameters.outputBucketName,
                                            self.inputParameters.dataFileNameWithPrefix,
                                            self.inputParameters.s3PresignedExpirationTime)

    def start(self, csvFileUrl, jsonFileUrl):

        dataFileUrl = self.generateDataFile()

        htmlpage = getHtmlTemplateString()
        htmlpage = htmlpage.replace('ria-data.js', dataFileUrl)
        htmlpage = htmlpage.replace('ria-json.json', jsonFileUrl)

        if(self.inputParameters.exportCSV):
            htmlpage = htmlpage.replace('<a class="dropdown-item" href="ria-csv.csv">CSV</a>',
                '<a class="dropdown-item" href="{}">CSV</a>'.format(csvFileUrl))
        else:
            htmlpage = htmlpage.replace('<a class="dropdown-item" href="ria-csv.csv">CSV</a>', '')

        RiaHelper.writeToS3WithOptions(htmlpage, self.inputParameters.awsRegion,
                self.inputParameters.outputBucketName, self.inputParameters.htmlFileNameWithPrefix,
                'public-read', 'text/html; charset=utf-8')

        s3FilePrefix = "https://s3.amazonaws.com"
        if(not self.inputParameters.awsRegion == 'us-east-1'):
            s3FilePrefix = "https://s3-{}.amazonaws.com".format(self.inputParameters.awsRegion)

        return "{}/{}/{}".format(s3FilePrefix,
                         self.inputParameters.outputBucketName,
                         self.inputParameters.htmlFileNameWithPrefix)


# In[ ]:


class OutputGenerator:

    def __init__(self, inputParameters, output):
        ''' Constructor. '''
        self.inputParameters = inputParameters
        self.output = output

    def start(self):

        jsonFileUrl = ""
        try:
            print("Generating JSON...")
            jsonGenerator = JSONGenerator(self.inputParameters, self.output)
            jsonFileUrl = jsonGenerator.start()
            print("Generated JSON")
        except Exception as e:
            print("Failed to generate json file. Error: {}.".format(e))

        csvFileUrl = ""
        if(self.inputParameters.exportCSV):
            try:
                print("Generating CSV...")
                csvGenerator = CSVGenerator(self.inputParameters, self.output)
                csvFileUrl = csvGenerator.start()
                print("Generated CSV")
            except Exception as e:
                print("Failed to generate csv file. Error: {}.".format(e))

        htmlFileUrl = ""
        dataFileUrl = ""
        try:
            print("Generating Html...")
            htmlGenerator = HTMLGenerator(self.inputParameters, self.output)
            htmlFileUrl = htmlGenerator.start(csvFileUrl, jsonFileUrl)
            print("Generated Html")
        except Exception as e:
            print("Failed to generate html file. Error: {}.".format(e))

        return htmlFileUrl


# In[ ]:


def postProcessingMessage(output):
    total = len(output)
    successful = 0
    failed = 0

    for ei in output:
        if((not 'Labels' in ei or ('Labels' in ei and 'Error' in ei['Labels'])) or
           (not 'ModerationLabels' in ei or ('ModerationLabels' in ei and 'Error' in ei['ModerationLabels'])) or
           (not 'Celebrities' in ei or ('Celebrities' in ei and 'Error' in ei['Celebrities'])) or
           (not 'Faces' in ei or ('Faces' in ei and 'Error' in ei['Faces'])) or
           (not 'Text' in ei or ('Text' in ei and 'Error' in ei['Text']))
           #or ('FaceSearch' in ei and 'Error' in ei['FaceSearch'])
          ):
            failed = failed + 1

    if(total > 0):
        successful = total - failed

    print("Total images: {}".format(total))
    print("Analyzed: {}".format(successful))
    print("Failed: {}".format(failed))
    if(failed):
        print("To see details about failures, launch ria generated web app and see log in the browser console.")


# In[ ]:


def validateInput(event, ips):

    if('imagesDirectory' in event):
        ips.imagesDirectory = event['imagesDirectory']
        if(ips.imagesDirectory and not ips.imagesDirectory.endswith("/")):
            ips.imagesDirectory = ips.imagesDirectory + "/"

    if('outputBucketName' in event):
        ips.outputBucketName = event['outputBucketName']
    else:
        ips.outputBucketName = event['bucketName']

    if('outputDirectory' in event):
        ips.outputDirectory = event['outputDirectory']
        if(ips.outputDirectory and not ips.outputDirectory.endswith("/")):
            ips.outputDirectory = ips.outputDirectory + "/"

    if('concurrencyControl' in event):
        ips.concurrencyControl = event['concurrencyControl']
    if('maxPages' in event):
        ips.maxPages = event['maxPages']
    if('maxItemsPerPage' in event):
        ips.maxItemsPerPage = event['maxItemsPerPage']

    if('minimumConfidence' in event):
        ips.minimumConfidence = event['minimumConfidence']
        if(ips.minimumConfidence < 0 or ips.minimumConfidence > 100):
            ips.minimumConfidence = 50

    if('exportCSV' in event):
        ips.exportCSV = event['exportCSV']
    if('collectionId' in event):
        ips.collectionId = event['collectionId']

    if('s3PresignedExpirationTime' in event):
        ips.s3PresignedExpirationTime = event['s3PresignedExpirationTime']
        if(ips.s3PresignedExpirationTime < 0 or ips.s3PresignedExpirationTime > 604800):
            ips.s3PresignedExpirationTime = 604800

    client = boto3.client('s3')

    response = client.get_bucket_location(
        Bucket=ips.bucketName)
    inputRegion = response['LocationConstraint']

    response = client.get_bucket_location(
        Bucket=ips.outputBucketName)
    outputRegion = response['LocationConstraint']

    if(inputRegion != outputRegion):
        raise Exception("Input and output S3 buckets are in different regions.\n{} is in {} while {} is in {}".format(
                        ips.bucketName, inputRegion, ips.outputBucketName, outputRegion))

    ips.awsRegion = inputRegion
    if(not ips.awsRegion):
        ips.awsRegion = 'us-east-1'

    uid = str(uuid.uuid1())
    ips.tempFolderName = "{}/".format(uid)
    ips.jsonFileName = '{}-ria-json.json'.format(uid)
    ips.jsonFileNameWithPrefix = '{}{}-ria-json.json'.format(ips.outputDirectory, uid)
    ips.csvFileName = '{}-ria-csv.csv'.format(uid)
    ips.csvFileNameWithPrefix = '{}{}-ria-csv.csv'.format(ips.outputDirectory, uid)
    ips.dataFileName = '{}-ria-data.js'.format(uid)
    ips.dataFileNameWithPrefix = '{}{}-ria-data.js'.format(ips.outputDirectory, uid)
    ips.htmlFileName = '{}-ria-html.html'.format(uid)
    ips.htmlFileNameWithPrefix = '{}{}-ria-html.html'.format(ips.outputDirectory, uid)




# In[ ]:


def lambda_handler(event, context):

    ips = RiaInput(event['bucketName'])
    validateInput(event, ips)

    output = []

    # Create temp folder
    #if not os.path.exists(self.inputParameters.tempFolderName):
    #    os.makedir(self.inputParameters.tempFolderName)

    print("\nStarting RIA\n================================")
    ips.printForUser()

    print("\nAnalyzing images\n=================================")
    ia = ImageAnalyzer(ips, output)
    ia.start()

    print("\nAnalyzed Images\n=================================")
    postProcessingMessage(output)

    print("\nGenerating output\n=================================")
    og = OutputGenerator(ips, output)
    htmlFileUrl = og.start()
    print("\nGenerated Web App @\n=================================")
    print(htmlFileUrl)
    print("\n")

    #Delete temp folder
    #if os.path.exists(self.inputParameters.tempFolderName):
    #    shutil.rmtree(self.inputParameters.tempFolderName)

    return {
        "statusCode": 200,
        "body": json.dumps({'OutputHtmlUrl' : htmlFileUrl})
    }

# In[ ]:


def runFromCli():

    event = {}

    isInputValid = False

    try:
        i = 0
        while(i < len(sys.argv)):
            if(sys.argv[i] == '--input-bucket'):
                event['bucketName'] = sys.argv[i+1]
                i = i + 1
            if(sys.argv[i] == '--input-directory'):
                event['imagesDirectory'] = sys.argv[i+1]
                i = i + 1
            if(sys.argv[i] == '--output-bucket'):
                event['outputBucketName'] = sys.argv[i+1]
                i = i + 1
            if(sys.argv[i] == '--output-directory'):
                event['outputDirectory'] = sys.argv[i+1]
                i = i + 1
            if(sys.argv[i] == '--collection-id'):
                event['collectionId'] = sys.argv[i+1]
                i = i + 1
            if(sys.argv[i] == '--min-confidence'):
                event['minimumConfidence'] = int(sys.argv[i+1])
                i = i + 1
            if(sys.argv[i] == '--s3-expiration-time'):
                event['s3PresignedExpirationTime'] = int(sys.argv[i+1])
                i = i + 1
            if(sys.argv[i] == '--no-csv'):
                event['exportCSV'] = False

            i = i + 1

        if(not 'bucketName' in event):
            raise Exception("")

        isInputValid = True
    except Exception as e:
        print('Invalid input. Follow one the formats below. input-bucket is required, whereas all other parameters are optional.')
        print('- python3 ria.py --input-bucket your-bucket')
        print('- python3 ria.py --input-bucket your-bucket --input-directory your-input-directory --output-bucket your-bucket --output-directory your-output-directory --min-confidence 50 --collection-id your-collection --s3-expiration-time 3600 --no-csv')

    if(isInputValid):
        lambda_handler(event, None)


# In[ ]:


try:
    runFromCli()
except Exception as e:
    print("Something went wrong:\n====================================================\n{}".format(e))


# In[ ]:

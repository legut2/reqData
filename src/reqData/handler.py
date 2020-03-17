import boto3
import json
import uuid
import datetime
import os # needed for environ vars

# Pricing dependencies below
from ebaysdk.exception import ConnectionError
from ebaysdk.finding import Connection
from bs4 import BeautifulSoup
import sys
import bisect
from collections import OrderedDict

# Secrets manager import
from botocore.exceptions import ClientError

print('Loading function')
dynamo = boto3.client('dynamodb')

def respond(err, res=None, data=None, id=None):
    # attaches UUID and sales DATA
    
    res['Data'] = data
    res['UUID'] = id
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(res),
        'headers': {
            'X-Requested-With': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,x-requested-with',
            'Access-Control-Allow-Headers': '',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST,GET,OPTIONS',
            'Content-Type': 'application/json',
        },
    }


def handler(event, context):
    '''Demonstrates a simple HTTP endpoint using API Gateway. You have full
    access to the request and response payload, including headers and
    status code.

    To scan a DynamoDB table, make a GET request with the TableName as a
    query string parameter. To put, update, or delete an item, make a POST,
    PUT, or DELETE request respectively, passing in the payload to the
    DynamoDB API as a JSON body.
    '''
    #print("Received event: " + json.dumps(event, indent=2))
    # Log the event argument for debugging and for use in local development
    print("---EVENT---")
    print(json.dumps(event))
    # print("---CONTEXT---")
    # print(json.dumps(vars(context)))
    operations = {
        'DELETE': lambda dynamo, x: dynamo.delete_item(**x),
        'GET': lambda dynamo, x: dynamo.query(**x),
        'POST': lambda dynamo, x: dynamo.put_item(**x),
        'PUT': lambda dynamo, x: dynamo.update_item(**x),
    }
    #MEH CODE FOR NEXT 3 lines
    operation = event['httpMethod']
    bodyDict = json.loads(event['body'])
    bodyDict['Item']['KeywordsQueryId'] = {
        "S": str(uuid.uuid4())
    }
    bodyDict['Item']['TimeStamp'] = {
        "S": str(datetime.datetime.now())
    }
    print(bodyDict['Item']['Keywords']['S'])
    print(bodyDict['Item']['Condition']['N'])
    if operation in operations:
        payload = event['queryStringParameters'] if operation == 'GET' else bodyDict
        p = price(bodyDict['Item']['Keywords']['S'],bodyDict['Item']['Condition']['N'],bodyDict['Item']['SEO']['N'])
        payload['Item']['Data'] = {
            "S": p
        }
        return respond(None, operations[operation](dynamo, payload),p,bodyDict['Item']['KeywordsQueryId']['S'])
    else:
        return respond(ValueError('Unsupported method (or malformed request - check for empty values) "{}"'.format(operation)))

# Pricing logic below
        
ItemsSoldWithCondInRegion = { 
            'keywords': 'dell optiplex 790',
            'outputSelector': 'GalleryInfoContainer',
            'itemFilter': [
                {'name': 'Condition', 'value': 3000},
                {'name': 'SoldItemsOnly', 'value': True},
                # {'name': 'ListingType', 'value': 'FixedPrice'},
                {'name': 'LocatedIn', 'value': 'US'},     
            ]
}

ItemsActiveWithCondInReqion = { 
            'keywords': 'dell optiplex 790',
            'outputSelector': 'GalleryInfoContainer',
            'itemFilter': [
                {'name': 'Condition', 'value': 3000},
                # {'name': 'ListingType', 'value': 'FixedPrice'},
                {'name': 'LocatedIn', 'value': 'US'},     
                ]
}


def price(keywords, condit, seo):
    ID_APP = str(os.environ['EBAY_APP_ID'])                                        # NEEDS TO BE CHANGED TO SECRET IN FUTURE AND NEW APP ID GENERATED

    ItemsSoldWithCondInRegion['keywords'] = keywords

    ItemsSoldWithCondInRegion['itemFilter'][0]['value'] = int(condit)
    ItemsActiveWithCondInReqion['itemFilter'][0]['value'] = int(condit)

    ItemsActiveWithCondInReqion['keywords'] = keywords

    if (int(seo) == 0)
        try:
            api = Connection(appid=ID_APP, config_file=None)
            responseAct = api.execute('findItemsAdvanced', ItemsActiveWithCondInReqion)
            responseSold = api.execute('findCompletedItems', ItemsSoldWithCondInRegion)

            #active response assertions
            assert(responseAct.reply.ack == 'Success')
            assert(type(responseAct.reply.timestamp) == datetime.datetime)
            if int(responseAct.reply.paginationOutput.totalEntries) <= 0:
                return json.dumps({
                    "S": "None"
                })
            assert(type(responseAct.reply.searchResult.item) == list)

            #sold response assertions
            assert(responseSold.reply.ack == 'Success')
            assert(type(responseSold.reply.timestamp) == datetime.datetime)
            #no data for sales return
            if int(responseSold.reply.paginationOutput.totalEntries) <= 0:
                return json.dumps({
                    "S": "None"
                })
            assert(type(responseSold.reply.searchResult.item) == list)

            items = responseSold.reply.searchResult.item
            #Basic count of sample
            sampleSize = len(responseSold.reply.searchResult.item)

            #check to make sure they're dictionaries
            assert(type(responseAct.dict()) == dict)
            assert(type(responseSold.dict()) == dict)

            #Check to see if the total number of entries is greater than 0
            if int(responseSold.reply.paginationOutput.totalEntries) > 0:
                taggedPrices = []
                soupComp = BeautifulSoup(responseSold.content,'lxml')
                print(soupComp.prettify())
                taggedPrices = soupComp.find_all('convertedcurrentprice')
                # itemXMLS = soupComp.findAll('item')
                shippingInfos = soupComp.findAll('shippinginfo')
                urls = soupComp.findAll('viewitemurl')
                galleryurls = soupComp.findAll('galleryurl')
                # largePicUrls = soupComp.findAll('pictureurllarge')
                # imgCont = soupComp.findAll('galleryInfoContainer')
                titles = soupComp.findAll('title')

            # priceList = sortData(taggedPrices, items, taggedShippingPrices, itemXMLS, sampleSize)
            priceStruct = {}
            print(sampleSize)
            # print(len(itemXMLS))
            # print(len(taggedPrices))
            # print(len(items))
            for i in range(len(items)):
                # ,str(shippingInfos[i])
                priceStruct[i] = (float(taggedPrices[i].get_text()),shippingInfos[i].get_text(),str(galleryurls[i].get_text()),items[i].itemId,str(titles[i].get_text()),str(urls[i].get_text()))
            # pricingData = OrderedDict(sorted(priceStruct.items(), key=lambda t: t[1])) #this sorts by price
            totalSoldEntries = float(responseSold.reply.paginationOutput.totalEntries)
            totalActiveEntries = float(responseAct.reply.paginationOutput.totalEntries)

            ninetyDaySellThru = totalSoldEntries/totalActiveEntries
            jsonResponse = {}
            if int(condit) == 3000:
                cond = "Used"
            elif int(condit) == 1000:
                cond = "New"

            jsonResponse["totalSold"] = str(totalSoldEntries)
            jsonResponse["totalActive"] = str(totalActiveEntries)
            jsonResponse["forecasted_ebay_market_sell_through_chance_in_90_days"] = str(round(ninetyDaySellThru*100,2))
            jsonResponse["sample_size"] = sampleSize
            jsonResponse["pricing_data"] = json.dumps(priceStruct) #return priceStruct to sort by price and uncomment orderedDict function at line ~167
            jsonResponse["condition_of_items_in_sample"] = cond
            jsonResponse["keywords"] = keywords
            # jsonResponse["imageUrlContainer"] = imgCont
            return json.dumps({
                "S": json.dumps(jsonResponse)
                })
        except ConnectionError as e:
            print(e)
            print(e.response.dict())
            return json.dumps({
                "S": json.dumps(e.response.dict())
                })
        return json.dumps({
                "S": "Uh oh error"
                })
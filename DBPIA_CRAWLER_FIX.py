from random import randint
from time import sleep
import sys, requests, xmltodict, json, datetime, re ,math
import json
from bs4 import BeautifulSoup
import random
import time
from pymongo import MongoClient
from bson.objectid import ObjectId


'''
 @MongoDB 접속 URI / DB명
'''
client = MongoClient('mongodb://203.255.92.141:27017', authSource='admin')
db = client.DBPIA
pubDB = client.PUBLIC
Author = db.Author
Status = pubDB.DBPIA_CRAWLER
sl_start = 5.0

'''
 @DBPIA ID를 이용해서 소속 수집 Crawling 개발 (BeautifulSoup 활용) 
'''
while True:
    soup = ""
    i = ""
    try:
        for doc in Author.find({"hasInst" : False}).batch_size(1):

            print("DBPIA Inst. Crawler :", doc['name'], doc['_id'])
            i = int( doc['_id'])
            #url 변동 되면 해당 부분 수정 필요 
            url = 'https://www.dbpia.co.kr/author/authorDetail?ancId={}'.format(i)
            conn = requests.get(url, timeout=60).text
            soup = BeautifulSoup(conn, 'html.parser')
            
            #Parsing 태그 정보 (변경 시 수정 필요)
            division_extract = soup.select('dd')
            # content_extract = soup.select('strong')
            name_extract = soup.select('h2')
            test_extract = name_extract[0].text.strip().split("\n")
            print(test_extract)
            # if len(test_extract) < 8:
            #     Author.delete_one({"_id": i})
            #     Status.find_one_and_update({"_id":4865},{"$inc":{"total":-1}})
            #     continue 

            division = division_extract[3].text.strip()
            department = division_extract[4].text.strip()
            new_name = test_extract[0].strip()
            if '논문수' == new_name:
                Author.delete_one({"_id": doc['_id']})
                Status.find_one_and_update({"_id":4865},{"$inc":{"total":-1}})
                continue 

            if division == '-' and department == '-':
            
                inst = ''
            elif department=='-':
                department=''
            
                inst = division + department
            else:  
                inst = division +  ' ' + department

            papers_count = test_extract[3].strip("논문수 ")
            # period = content_extract[4].text.strip()
            used_count = test_extract[5].strip("이용수 ")
            if len(test_extract) < 8:
                citation_count = 0
            else:
                citation_count = test_extract[7].strip("피인용수 ")

            
            # Author.update_one({"_id":doc['_id']},{'$set':{"plusName" :new_name,  "inst": inst , "hasInst" : True , "papers_count" : papers_count , "used_count": used_count,'citation_count': citation_count}})
            # Status.find_one_and_update({"_id":4865},{"$inc":{"crawled":1}})
            # requests.session().close()
            # print("DBPIA Inst. Crawler :", doc['name'], ", Crawled, [inst , (paper, used, citation count)] : {} , ({}, {}, {})".format(inst.strip(), papers_count.strip(), used_count.strip(), citation_count))
            # sleep(random.uniform(sl_start, sl_start + 5.0))

        # Status.find_one_and_update({"_id":4865},{"$set":{"status":0}})
        # print("Inst All Crawled")
        # break

    except Exception as e :
        sl_start = sl_start * 1.1
        

        # try :
        #     if '불편' in soup.select('.tit')[0].text:
        #         Author.update_one({"_id":doc['_id']},{'$set':{"plusName" :'',  "inst": '' , "hasInst" : True , "papers_count" : 0 , "used_count": 0,'citation_count': 0}})
        #         Status.find_one_and_update({"_id":4865},{"$inc":{"crawled":1}})
        #         print('error no id')
        # except Exception as e : 
        #     Author.delete_one({"_id": doc['_id']})
        #     Status.find_one_and_update({"_id":4865},{"$inc":{"total":-1}})
        #     print('Another Error', e)
        print("Inst 예외", e)
        print("Sleep Time Increased by ", sl_start)
        sleep(random.uniform(sl_start, sl_start+5.0))

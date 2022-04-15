import requests, xmltodict, datetime, openpyxl, asyncio, functools
import sys, os, re, math, logging, time, json, xlrd, retry, pprint
from selenium.common.exceptions import ElementNotVisibleException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.alert import Alert
from multiprocessing import Process, Value, Array
from multiprocessing.managers import BaseManager
from selenium.webdriver.common.keys import Keys
from pyvirtualdisplay import Display
from collections import OrderedDict
from urllib.request import urlopen
from ParsingHelper_WOS import Parser
from pymongo import MongoClient
from kafka import KafkaProducer
from selenium import webdriver
from bs4 import BeautifulSoup
from langdetect import detect
from threading import Thread
from random import randint
from json import dumps
from time import sleep
import logging as log
import csv
import random


class WOS_crawler:
    '''
    @ Method Name     : __init__
    @ Method explain  : WOS 크롤링 파라미터
    @ query_keyword   : 검색 연산처리(AND OR NOT) 된 키워드
    @ crawl_end       : 크롤링이 끝나면 = 1 // 끝나지 않으면 = 0 (프로세스 수 == crawl_end 수)
    @ parse_end       : 파싱이 끝나면 = 1 // 끝나지 않으면 = 0
    @ parse_data      : 파싱된 데이터 수
    @ num_data        : 웹 사이트로부터 다운로드 받은 수
    @ keyword         : 검색 기워드
    @ keyId           : 검색 키 아이디
    @ year            : 검색 년도
    @ total_data      : 총 데이터 수
    @ path            : 다운로드 저장 경로
    @ isPartial       : 부분적으로 크롤링 했다면(실패로 인한 스킵이 있었다면) (1 = True / 0 = False)
    @ is_not_active   : HTTP code확인(403 error) (1 = True / 0 = False) <-- 한번에 많은 데이터를 다운로드 받거나 기계적 접근이 감지 되면 차단당함
    @ korea_option    : 한국 논문만 볼 수 있는 옵션 (0 = True / 1 = False)
    @ chrome_failed   : 크롬 드라이버 정상 작동 확인 (1 = True / 0 = False)
    '''
    def __init__(self,query_keyword, crawl_end, parse_end, parse_data, num_data, keyword, keyId, year, total_data, path, isPartial, is_not_active, korea_option, chrome_failed, url, etc_path):
        self.query_keyword = query_keyword
        self.crawl_end = crawl_end
        self.parse_end = parse_end
        self.num_parse = parse_data
        self.num_data = num_data
        self.keyword = keyword
        self.keyId = keyId
        self.year = year                     # 몇년도 부터 검색할지
        self.total_data = total_data
        self.path = path
        self.isPartial = isPartial
        self.is_not_active = is_not_active
        self.korea_option = korea_option     # 한국 옵션을 받아온다.(0이 트루인듯)
        self.chrome_failed = chrome_failed
        self.url = url

        self.options = webdriver.ChromeOptions()
        self.options_box = ['--disable-dev-shm-usage',"lang=ko_KR",'--no-sandbox',
        'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36']
        for i in range(0,4):
            self.options.add_argument(self.options_box[i])
        self.options.add_experimental_option("prefs", {"profile.default_content_settings.popups": 0,
                         "download.default_directory": self.path,
                         "download.prompt_for_download" : False,
                         "profile.default_content_setting_values.automatic_downloads": 1,
                         "directory_upgrade": True})
        self.driver = webdriver.Chrome(executable_path = etc_path + "/chromedriver", options = self.options)
           
        self.korea_search = ''            # 한국옵션이 트루이면 쿼리문에 국적 한국 추가             
        self.frist_down = 0
        self.nowset_cnt = 0  
        self.s_num = 1
        self.paper_cnt = 0
        self.exception_cnt = 0
        self.select_count = 0
        self.total_paper_count = 0
        self.error_count = []
        self.end_num = 0
        self.start_num = 0
        self.total_record = 0             # 선택목록에 담을 수 있는 논문수(최대100,000)
        self.total_select_count = 0       # 논문을 선택목록에 담을때 몇번 담는지 최소1번 최대 2번(한번에 5만개씩 받을수 있고 최대 10만개 담을 수 있다)          
        self.temp = {}
        self.max_set_cnt = 0
        self.last_check = 0               # No need


#######################################################################################################################################
    '''
    @ Method Name     : check_file
    @ Method explain  : 파일 생성 확인 --> 마지막 폴더&파일 전체 삭제
    '''
    def check_file(self):
        check_file_list = os.listdir(self.path)
        if check_file_list:
            for i in range(len(check_file_list)):
                check_file = check_file_list[i]
                check_file_path = (self.path + '/' + check_file)
                os.remove(check_file_path)
            print("file 리스트 전체 삭제(초기화)")

        else:
            print("file 리스트 PASS(NULL)")
            pass
        return


    '''
    @ Method Name     : WOS_crawl_end
    @ Method explain  : 크롤링 종료 --> 파일 생성
    '''
    def WOS_crawl_end(self):
        print('========================  Crawling을 종료 합니다.  ========================')
        if self.last_check == 0:
            self.last_check = 1
            time.sleep(2)
            #self.num_data.value = self.num_parse.value     #The good one
            self.num_data = self.num_parse                  #The wrong one
            with open(self.path + "\crawler_end.txt", 'w') as f:
                f.write("--end--")
            print('마지막 데이터 다운로드 실패 ===> 종료 파일을 생성합니다. ')
        return


    '''
    @ Method Name     : WOS_checkbox
    @ Method explain  : 파일 다운로드 목록 선택
    '''
    def WOS_checkbox(self):
        self.driver.find_element_by_xpath('//*[@id="snRecListTop"]/app-export-menu/div/button').click()
        time.sleep(1)
        self.driver.find_element_by_xpath('//*[@id="exportToExcelButton"]').click()
        time.sleep(1)
        self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route[1]/app-export-overlay/div/div[3]/div[2]/app-export-out-details/div/div[2]/form/div/div[1]/wos-select/button').click()
        time.sleep(1)
        self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route[1]/app-export-overlay/div/div[3]/div[2]/app-export-out-details/div/div[2]/form/div/div[1]/wos-select/div/div/div[2]/div[4]').click()
        time.sleep(1)         

        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[1]/mat-checkbox/label/span[1]').click()
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[1]/mat-checkbox/label/span[1]').click()
        time.sleep(1)
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[2]/mat-checkbox/label/span[1]').click()
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[2]/mat-checkbox/label/span[1]').click()
        time.sleep(1)
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[3]/mat-checkbox/label/span[1]').click()
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[3]/mat-checkbox/label/span[1]').click()
        time.sleep(1)

        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[1]/div[5]/mat-checkbox/label/span[1]').click()  # 학회정보 해제     
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[1]/div[6]/mat-checkbox/label/span[1]').click()  # 인용횟수 해제     
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[1]/div[8]/mat-checkbox/label/span[1]').click()  # 저자식별자 해제
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[1]/div[9]/mat-checkbox/label/span[1]').click()  # ISSN해제
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[1]/div[10]/mat-checkbox/label/span[1]').click()  # PMID 해제
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[2]/div[2]/mat-checkbox/label/span[1]').click()  # 초록 체크
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[2]/div[3]/mat-checkbox/label/span[1]').click()  # 연구기관명및주소 체크
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[2]/div[5]/mat-checkbox/label/span[1]').click()  # 문서유형 체크
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[2]/div[6]/mat-checkbox/label/span[1]').click()  # 키워드 체크
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[2]/div[7]/mat-checkbox/label/span[1]').click()  # WOS범주 체크
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[2]/div[8]/mat-checkbox/label/span[1]').click()  # 연구분야 체크
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[3]/div[3]/mat-checkbox/label/span[1]').click()  # 인용문헌수 체크
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[3]/div[4]/mat-checkbox/label/span[1]').click()  # 이용횟수 체크
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[4]/div[3]/mat-checkbox/label/span[1]').click()  # 출판사정보 체크
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[4]/div[5]/mat-checkbox/label/span[1]').click()  # 페이지수 체크
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[4]/div[6]/mat-checkbox/label/span[1]').click() # 원본 약어 체크
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[2]/div/div[4]/div[8]/mat-checkbox/label/span[1]').click()  # 언어 체크
        time.sleep(1)
        self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[4]/div[2]/button[2]').click()  # 선택 저장
        time.sleep(1)
        self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route[1]/app-export-overlay/div/div[3]/div[2]/app-export-out-details/div/div[2]/form/div/div[2]/button[2]').click() #취소 버턴
        time.sleep(1)
        return


    '''
    @ Method Name     : check_403_error
    @ Method explain  : 403 에러 확인 (파일을 많이 OR 오래 받으면 사이트에서 차단)
    '''
    def check_403_error(self): #403 에러 확인 (파일을 많이 OR 오래 받으면 사이트에서 차단)
        url = self.url

        try:
            resq = requests.get(url, timeout = 30)
            rescode = resq.status_code

        except Exception as e:
            print(e)

        print("사이트 Request 코드 확인 : ", rescode) # 403 에러 확인


        if not rescode == 200:
            print('=================', rescode,'사이트 에러 입니다.','=================')
            #self.is_not_active.value = 1
            self.is_not_active = 1

        time.sleep(3)
        return


    '''
    @ Method Name     : like_human
    @ Method explain  : 사람인척하기 (랜덤하게 스크롤 하기)
    '''
    def like_human(self):
        print("### 사람인척하기 ###")
        for i in range(1, random.randrange(10,30)):
            self.driver.execute_script('window.scrollTo(0, %d00);' %i)
            time.sleep(0.1)
        print("================= 사람인척 종료 =================")


########################################################################################################################################
    '''
    @ Method Name     : WOS
    @ Method explain  : 사이트 접속후 크롤링
    '''
    def WOS(self):
        now = time.localtime()
        time_a = time.gmtime(time.time()) 
        url = self.url

        if self.korea_option == 0:
            self.korea_search = ' AND CU = SOUTH KOREA'

        try:
            try:
                self.driver.get(url)  # WOS 사이트접속
                self.driver.implicitly_wait(10)
                self.driver.delete_all_cookies()
                print("사이트 접속 완료 ===> 쿠키 삭제")
                time.sleep(3)
                print('고급 검색 창 이동')

            except:
                self.chrome_failed = 1
                raise Exception('==============================Chrome 접속 실패==============================')


            #Advanced research
            self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').send_keys(self.query_keyword)
            
            print('검색어 입력')
            time.sleep(1)
            self.driver.find_element_by_xpath('/html/body/div[4]/div/div[1]/button').click()
            self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-search-home/div[2]/div/app-input-route/app-search-advanced/app-advanced-search-form/form/div[3]/div[1]/div[1]/div/button[2]').click()
            print('검색 클릭')
            time.sleep(2)
            #Advanced research

            #Custom the export selection
            self.WOS_checkbox()
            #Custom the export selection

            #Second advanced research
            try:
                year_difference = now.tm_year - int(self.year)
                year_div = list(divmod(year_difference, 5))
                #0 < year_difference <= 5
                if year_difference <= 5 and year_difference > 0:
                    time.sleep(2)
                    self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-base-summary-component/app-search-friendly-display/div[1]/app-general-search-friendly-display/div/button').click() 
                    self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').clear()
                    self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').send_keys(self.query_keyword + ' AND PY =' + str(self.year) + '-' + str(now.tm_year) + self.korea_search)
                    print(self.year,' 부터 ', now.tm_year, ' 까지 검색')
                    time.sleep(2)
                    self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-base-summary-component/app-search-friendly-display/div[1]/app-general-search-friendly-display/div[4]/div[2]/app-advanced-search-form/form/div[2]/div[1]/div/div/button[2]').click()
                    print("검색 click")
                    time.sleep(4)
                    self.nowset_cnt += 1
                #year_difference = 0
                elif year_difference == 0:
                    time.sleep(2)
                    self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-base-summary-component/app-search-friendly-display/div[1]/app-general-search-friendly-display/div/button').click() 
                    self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').clear()
                    self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').send_keys(self.query_keyword + ' AND PY =' + str(self.year) + self.korea_search)
                    print(self.year,' 년도 논문 검색')
                    time.sleep(2)
                    self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-base-summary-component/app-search-friendly-display/div[1]/app-general-search-friendly-display/div[4]/div[2]/app-advanced-search-form/form/div[2]/div[1]/div/div/button[2]').click()                                
                    print("검색 click")
                    time.sleep(4)
                    self.nowset_cnt += 1
                #year_difference > 5
                else:
                    i = 1 #Why ?
                    start_year = int(self.year) - 5
                    plus_year = int(self.year)
                    for i in range(int(year_div[0])):    #5 나눠서 나머지 까지 +1 ``
                        start_year += 5
                        plus_year += 5

                        time.sleep(2)
                        self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-base-summary-component/app-search-friendly-display/div[1]/app-general-search-friendly-display/div/button').click() 
                        self.driver.execute_script('document.getElementById("advancedSearchInputArea").value="";')
                        print("고급 검색 초기화")
                        time.sleep(2)
                        if plus_year >= now.tm_year:
                            plus_year = now.tm_year
                        self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').clear()
                        self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').send_keys(self.query_keyword + ' AND PY =' + str(start_year) + '-' + str(plus_year) + self.korea_search)
                        print(start_year,' 부터 ', plus_year, ' 까지 검색')
                        time.sleep(2)
                        self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-base-summary-component/app-search-friendly-display/div[1]/app-general-search-friendly-display/div[4]/div[2]/app-advanced-search-form/form/div[2]/div[1]/div/div/button[2]').click()
                        print("검색 click")
                        start_year += 1
                        plus_year += 1
                        self.nowset_cnt += 1
                    if not year_difference % 5 == 0:
                        time.sleep(2)
                        self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-base-summary-component/app-search-friendly-display/div[1]/app-general-search-friendly-display/div/button').click() 
                        self.driver.execute_script('document.getElementById("advancedSearchInputArea").value="";')
                        print("고급 검색 초기화")
                        time.sleep(2)
                        if plus_year >= now.tm_year:
                            plus_year = now.tm_year
                            self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').clear()
                            self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').send_keys(self.query_keyword + ' AND PY =' + str(now.tm_year) + self.korea_search)
                            print(now.tm_year, '년도 검색')
                            time.sleep(2)
                            self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-base-summary-component/app-search-friendly-display/div[1]/app-general-search-friendly-display/div[4]/div[2]/app-advanced-search-form/form/div[2]/div[1]/div/div/button[2]').click()
                            print("검색 click")
                            self.nowset_cnt += 1

                        else:
                            self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').send_keys(self.query_keyword + ' AND PY =' + str(plus_year) + '-' + str(now.tm_year) + self.korea_search)
                            print(plus_year,' 부터 ', now.tm_year, ' 까지 검색')
                            time.sleep(2)
                            self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-base-summary-component/app-search-friendly-display/div[1]/app-general-search-friendly-display/div[4]/div[2]/app-advanced-search-form/form/div[2]/div[1]/div/div/button[2]').click()
                            print("검색 click")
                            self.nowset_cnt += 1
                    else:
                        pass
            except:
                raise Exception("########## 검색 결과가 없습니다. ##########")
            #Second advanced research

            #Paper count job
            try:
                self.driver.find_element_by_xpath('//*[@id="snHeaderLink"]').click()
                c = 0 #Why ?
                max_total_count_sum = 0
                for c in range(self.nowset_cnt):    # 총 PAPER 수 COUNT
                    c += 1
                    time.sleep(2)
                    print(max_total_count_sum)
                    max_total_count_info = self.driver.find_element_by_xpath('//*[@id="snHistoryTop"]/app-history-entries-list/app-history-search-entry[%s]/div/div[2]/a'%c)
                    max_total_count = int(max_total_count_info.text.replace(',',''))
                    max_total_count_sum += max_total_count

                #self.total_data.value = int(max_total_count_sum) Why do we put value ?
                self.total_data = int(max_total_count_sum)
                self.total_paper_count = int(max_total_count_sum)
                print('총 논문 수 : ', self.total_paper_count)

                if self.total_paper_count > 0:
                        pass

                else:
                    raise Exception("########## 검색 결과가 없습니다. ##########") # 한번 더 시도

            except:
                raise Exception("########## 검색 결과가 없습니다. ##########")
            #Paper count job
            
            #Take the papers and download them
            self.driver.find_element_by_xpath('/html/body/div[5]/div/div/button').click()  # POP UP 삭제
            if self.total_paper_count <= 100000:
                print('총 논문수 : 100000개 이하입니다.')

                #Create new request like #1 OR #3 & total paper count job
                if self.nowset_cnt > 1:
                    print('SET가 2개 이상입니다.')
                    for t in range(self.nowset_cnt):
                        t += 1
                        print('SET연산 조합')
                        self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-search-home/div[2]/div/app-input-route/app-search-advanced/app-advanced-search-form/form/div[4]/app-history-home/div/app-history-entries-list/app-history-search-entry[%d]/div/mat-checkbox/label/span[1]' %t).click()
                    self.driver.find_element_by_xpath('//*[@id="snSearchHistory"]/app-history-home/app-history-manager/div[3]/div[1]/button').click()
                    time.sleep(2)
                    self.driver.find_element_by_xpath('/html/body/div[4]/div[2]/div/div/div/div/div[2]/button').click()
                    #self.driver.find_element_by_xpath('/html/body/div[5]/div/div/button').click()
                    time.sleep(2)
                    self.nowset_cnt += 1
                    
                    hit_count_info = self.driver.find_element_by_xpath('//*[@id="snHistoryTop"]/app-history-entries-list/app-history-search-entry[1]/div/div[2]/a')
                    hit_count = hit_count_info.text
                    self.total_paper_count = int(hit_count.replace(',',''))
                    print('SET 연산 논문 결과 : ', self.total_paper_count)
                else:
                    pass
                #Create new request like #1 OR #3 & total paper count job

                #Download
                try:
                    self.driver.find_element_by_xpath('//*[@id="snHistoryTop"]/app-history-entries-list/app-history-search-entry[1]/div/div[2]/a').click()
                    print(self.nowset_cnt, '번째 SET 클릭(이동)')
                    time.sleep(2)

                    self.max_set_cnt = self.nowset_cnt

                    self.WOS_excel_download()

                    time_b = time.gmtime(time.time())
                    print('엑셀다운 시,분,초 : ', time_a.tm_hour, time_a.tm_min, time_a.tm_sec) #엑셀 다운 총 시간체크
                    print('엑셀다운 시,분,초 : ', time_b.tm_hour, time_b.tm_min, time_b.tm_sec) #WOS 작업 시간체크

                    if self.num_data == 0:
                        raise Exception("======================== Data download 실패  ========================")

                    print('========================  모든 Data download 완료  ========================')
                except:
                    raise Exception("Set 연산 검색 Exception 발생 ===> 종료전 403 check")
                #Download

            elif self.total_paper_count > 100000:
                self.nowset_cnt = 0
                time.sleep(1)
                self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-search-home/div[2]/div/app-input-route/app-search-advanced/app-advanced-search-form/form/div[4]/app-history-home/app-history-manager/div[3]/div[1]/mat-checkbox/label/span[1]').click()             # 총 PAPER 검색 목록 삭제
                time.sleep(3)
                self.like_human()
                self.driver.find_element_by_xpath('//*[@id="snSearchHistory"]/app-history-home/app-history-manager/div[3]/button').click()
                time.sleep(3)
                self.driver.find_element_by_xpath('/html/body/div[4]/div[2]/div/mat-dialog-container/app-clear-history/div/div/button[2]').click()
                time.sleep(3)
                set_cnt = 1 # 세트 수 세기

                #New session history
                for y in range(int(self.year), now.tm_year + 1):
                    time.sleep(2)
                    self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').clear()
                    print("고급 검색 초기화")
                    time.sleep(1)
                    self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').send_keys(self.query_keyword + ' AND PY = ', y , self.korea_search)
                    print("키워드 입력")
                    time.sleep(1)
                    self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-search-home/div[2]/div/app-input-route/app-search-advanced/app-advanced-search-form/form/div[3]/div[1]/div[1]/div/button[2]').click()
                    print('검색 클릭')
                    time.sleep(1)
                    self.like_human()

                    hit_count_info = self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-base-summary-component/app-search-friendly-display/div[1]/app-general-search-friendly-display/h1/span')
                    hit_count = hit_count_info.text
                    hit_count = hit_count.replace(',','')
                    hit_count = int(hit_count)

                    print(y, "년도 검색 수 : ", hit_count)

                    #If the search have more than 100000 papers
                    if hit_count > 100000:
                        if self.korea_option == 1:
                            country_list = [' AND CU = USA', ' AND CU = PEOPLES R CHINA', ' NOT CU = USA NOT CU = PEOPLES R CHINA']
                            a = ['미국','중국', '그 외']
                            print(y,'년도 논문이 10만개 이상입니다. 나라별로 Crawling 합니다.')
                            time.sleep(1)
                            self.driver.find_element_by_xpath('//*[@id="snHeaderLink"]').click()
                            time.sleep(1)
                            self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-search-home/div[2]/div/app-input-route/app-search-advanced/app-advanced-search-form/form/div[4]/app-history-home/div/app-history-entries-list/app-history-search-entry[1]/div/mat-checkbox').click()             # 총 PAPER 검색 목록 삭제
                            time.sleep(1)
                            self.like_human()
                            self.driver.find_element_by_xpath('//*[@id="snSearchHistory"]/app-history-home/app-history-manager/div[3]/button').click()
                            time.sleep(1)
                            self.driver.find_element_by_xpath('/html/body/div[4]/div[2]/div/mat-dialog-container/app-clear-history/div/div/button[2]').click()
                            time.sleep(1)

                            #New request                        
                            for i in range(len(country_list)):
                                time.sleep(3)
                                self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').clear()
                                print("고급 검색 초기화")
                                time.sleep(3)
                                self.driver.find_element_by_xpath('//*[@id="advancedSearchInputArea"]').send_keys(self.query_keyword + ' AND PY = ', y , country_list[i])
                                time.sleep(3)
                                print("키워드 입력")
                                self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-search-home/div[2]/div/app-input-route/app-search-advanced/app-advanced-search-form/form/div[3]/div[1]/div[1]/div/button[2]').click()
                                print("검색 click")
                                time.sleep(1)

                                hit_count_info = self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-base-summary-component/app-search-friendly-display/div[1]/app-general-search-friendly-display/h1/span')
                                hit_count = hit_count_info.text
                                hit_count = hit_count.replace(',','')
                                hit_count = int(hit_count)

                                print(a[i], " 검색 논문 수 : ", hit_count)
                                time.sleep(4)
                                set_cnt += 1
                                self.driver.find_element_by_xpath('//*[@id="snHeaderLink"]').click()
                            #New request 
                        
                        else:
                            set_cnt += 1
                            pass
                    else:
                        set_cnt += 1
                        pass
                    self.driver.find_element_by_xpath('//*[@id="snHeaderLink"]').click()
                    #If the search have more than 100000 papers
                       
                self.max_set_cnt = 1    # 최신 논문 부터 수집
                self.nowset_cnt = set_cnt
                for k in range(1, self.nowset_cnt):
                    self.select_count = 0
                    self.nowset_cnt -= 1
                    self.s_num = 1

                    #Download
                    try:
                        print(self.nowset_cnt,'번째 SET 클릭(이동)')
                        self.driver.find_element_by_xpath('//*[@id="snHistoryTop"]/app-history-entries-list/app-history-search-entry[%d]/div/div[2]' %k).click()
                        print(k, '번째 SET 클릭(이동)')
                        time.sleep(2)

                        self.WOS_excel_download()
                        time.sleep(5)

                        time_b = time.gmtime(time.time())
                        print('엑셀다운 시,분,초 : ', time_a.tm_hour, time_a.tm_min, time_a.tm_sec) #엑셀 다운 총 시간체크
                        print('엑셀다운 시,분,초 : ', time_b.tm_hour, time_b.tm_min, time_b.tm_sec) #WOS 작업 시간체크
                        print("예외 발생 수:  ", self.exception_cnt)

                    except:
                        #self.isPartial.value = 1   #The good one
                        self.isPartial = 1          #The wrong one
                        print(self.nowset_cnt, '번째 SET 검색 실패')
                        pass

                    if self.num_data == 0:
                        print('========================  모든 Data download 완료  ========================')

                    self.driver.find_element_by_xpath('//*[@id="snHeaderLink"]').click()
                    #Download
                #New session history
            else:
                print('Set 검색 갯수 Error')
            #Take the papers and download them
            
        except Exception as e:
            print(e)

            #if self.num_data.value == 0:
            if self.num_data == 0:
                print('========================   종료전 403 check   ========================')
                self.check_403_error()

            print("예외 발생 수:  ", self.exception_cnt)

        finally:
            print("예외 발생 수:  ", self.exception_cnt)
            self.WOS_crawl_end()

        return


########################################################################################################################################
    '''
    @ Method Name     : total_record_count
    @ Method explain  : 총 논문수 계산 (최대 100000개 담을 수 있음)
    '''
    def total_record_count(self):
        total_count_info = WebDriverWait(self.driver, 240).until(lambda x : x.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route/app-base-summary-component/app-search-friendly-display/div[1]/app-general-search-friendly-display/h1/span'))
        total_count = total_count_info.text
        total_count = total_count.replace(',', '')
        total_count = int(total_count)
        self.total_record = total_count

        if total_count > 100000:
            self.total_record = 100000
        print("총 논문 수 :    ", total_count)
        print("총 검색 최대 결과 수 :   ", self.total_record)
        self.total_select_count = self.total_record // 1000 + 1
        if (self.total_record % 1000 == 0):
            self.total_select_count -= 1
        return

    '''
    @ Method Name     : WOS_excel_download
    @ Method explain  : 파일 다운로드 액션 실행
    '''
    def WOS_excel_download(self):
        self.reset = Alert(self.driver)

        try:
            self.total_record_count()
        except:
            print("예외 발생 ===> 뒤로 돌아갑니다.")
            #self.isPartial.value = 1
            self.isPartial = 1
            time.sleep(3)
            self.driver.execute_script('history.back();')
            time.sleep(3)
            self.exception_cnt += 1
            return

        for record_select in range(0, self.total_select_count):
            self.select_count += 1
            e_num = self.s_num + 999
            #Excel로 레코드 내보내기
            try:
                self.driver.refresh()
                time.sleep(3)
                self.driver.find_element_by_xpath('//*[@id="snRecListTop"]/app-export-menu/div/button').click()
                time.sleep(3)
                self.driver.find_element_by_xpath('//*[@id="exportToExcelButton"]').click()
                time.sleep(3)                     
                self.driver.find_element_by_xpath('//*[@id="radio3"]/label/span[1]').click()
                time.sleep(3)
            except:
                self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route[1]/app-export-overlay/div/div[3]/div[2]/app-export-out-details/div/div[2]/form/div/div[2]/button[2]').click()
                time.sleep(3)
                self.driver.refresh()
                time.sleep(3)
                self.driver.find_element_by_xpath('//*[@id="snRecListTop"]/app-export-menu/div/button').click()
                time.sleep(3)
                self.driver.find_element_by_xpath('//*[@id="exportToExcelButton"]').click()
                time.sleep(3)
                self.driver.find_element_by_xpath('//*[@id="radio3"]/label/span[1]').click()
                time.sleep(2)               
            #Excel로 레코드 내보내기

            self.driver.find_element_by_xpath('//*[@id="mat-input-0"]').clear()
            self.driver.find_element_by_xpath('//*[@id="mat-input-1"]').clear()
            self.driver.find_element_by_xpath('//*[@id="mat-input-0"]').send_keys(self.s_num)
            print("다운라우드 담기 시작 넘버 :  ",self.s_num)
            time.sleep(1)
            if self.select_count == self.total_select_count:
                self.last_check += 1
                self.driver.find_element_by_xpath('//*[@id="mat-input-1"]').send_keys(self.total_record)
                print("다운라우드 담기 끝 넘버 :  ", self.total_record)
                with open(self.path + "\crawler_end.txt", 'w') as f:
                    f.write("--end--")
                print('마지막 데이터 다운로드 성공 ===> 종료 파일을 생성합니다. ')
                time.sleep(2)
            else:
                self.driver.find_element_by_xpath('//*[@id="mat-input-1"]').send_keys(e_num)
                print("다운라우드 담기 끝 넘버 :  ", e_num)
                print(self.select_count ," 번째 선택 목록 담기 완료")
                time.sleep(2)
            
            #self.num_data.value += 1
            self.num_data += 1
            time.sleep(1)

            #self.like_human()
            self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route[1]/app-export-overlay/div/div[3]/div[2]/app-export-out-details/div/div[2]/form/div/div[1]/wos-select/button').click()
            time.sleep(2)                      
            self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route[1]/app-export-overlay/div/div[3]/div[2]/app-export-out-details/div/div[2]/form/div/div[1]/wos-select/div/div/div[2]/div[4]').click()
            time.sleep(2)                      
            self.driver.find_element_by_xpath('/html/body/div[5]/div[2]/div/mat-dialog-container/app-custom-field-selection-dialog/div/div[4]/div[2]/button[1]').click()
            time.sleep(2)                      
            self.driver.find_element_by_xpath('/html/body/app-wos/div/div/main/div/div[2]/app-input-route[1]/app-export-overlay/div/div[3]/div[2]/app-export-out-details/div/div[2]/form/div/div[2]/button[1]').click()
            time.sleep(8)
            self.s_num += 1000                    


########################################################################################################################################
a = WOS_crawler('TS=(social network)',0, 0, 0, 5, 'TS=(social network)', 512, 2015, 0, "/home/search/apps/topher/WOS_test", 0, 0, 0, 0, "https://www.webofscience.com/wos/woscc/advanced-search", "/home/search/apps/product/etc") # a = WOS_crawler('TS=(social)', 2015, 0)    WOS_crawler('TS=(social network)', 2015, 0)
a.WOS()
